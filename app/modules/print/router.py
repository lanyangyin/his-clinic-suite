from datetime import datetime
from html import escape
import hashlib

from fastapi import APIRouter, Depends, HTTPException

from app.modules.auth.security import require_login, require_print_access
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import settings
from app.modules.billing.service import get_payment
from app.modules.print.documents import (
    apply_print_profile,
    render_full_set,
    render_imaging_report,
    render_record,
    render_tcm,
    render_western,
)
from app.modules.print.barcode import code128_svg
from app.modules.print.models import PrintLog, PrintToken  # noqa: F401
from app.modules.print.profile import load as load_print_profile
from app.modules.pharmacy.models import PharmacyPickupCode
from app.modules.pharmacy.retail_service import get_retail_sale
from app.modules.pharmacy.service import build_dispense_slip, get_dispense
from app.modules.nursing.models import NursingOrder
from app.modules.charges.service import list_charges
from app.modules.encounter.models import Prescription
from app.modules.encounter.service import (
    get_encounter,
    get_medical_record,
    list_encounter_diagnoses,
    list_prescription_items,
)
from app.modules.lis.service import get_request
from app.modules.lis.models import LabRequest
from app.modules.pacs.models import ImagingRequest
from app.modules.patient.service import get_patient
from app.modules.staff.models import Department
from app.modules.tcm.models import TcmPrescription
from app.modules.registration.service import get_registration
from app.modules.staff.service import get_doctor

router = APIRouter(prefix="/print", tags=["print"], dependencies=[Depends(require_print_access)])


def _log_print(db: Session, user, document_type: str, ref_id: int | None) -> int:
    count = (
        db.query(PrintLog)
        .filter(PrintLog.document_type == document_type, PrintLog.ref_id == ref_id)
        .count()
        + 1
    )
    db.add(
        PrintLog(
            document_type=document_type,
            ref_id=ref_id,
            operator=getattr(user, "username", "") or "print-token",
        )
    )
    db.commit()
    return count


def _reprint_banner(count: int) -> str:
    label = "首次打印" if count <= 1 else f"补打 第{count}次"
    color = "#0f172a" if count <= 1 else "#b91c1c"
    return (
        f'<div style="margin:4px 0;padding:2px 6px;border:1px solid {color};'
        f'color:{color};font-size:11px;display:inline-block">{label}</div>'
    )


def _with_reprint_banner(html: str, count: int) -> str:
    return html.replace("<body>", f"<body>{_reprint_banner(count)}", 1)


def _clinic_meta() -> dict:
    return {
        "name": settings.CLINIC_NAME,
        "phone": settings.CLINIC_PHONE,
        "address": settings.CLINIC_ADDRESS,
    }


def _collect(db: Session, encounter_id: int, operator: str = "") -> dict:
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    registration = get_registration(db, encounter.registration_id)
    patient = get_patient(db, registration.patient_id)
    doctor = get_doctor(db, registration.doctor_id)
    record = get_medical_record(db, encounter_id)
    header = (
        db.query(Prescription)
        .filter(Prescription.encounter_id == encounter_id)
        .order_by(Prescription.id)
        .first()
    )

    lines = []
    total = 0.0
    for item in list_prescription_items(db, encounter_id):
        amount = round(item.quantity * item.unit_price, 2)
        total += amount
        usage = " ".join(
            part
            for part in (
                item.dosage,
                item.frequency,
                item.route,
                f"{item.days}天" if item.days else "",
            )
            if part
        )
        lines.append(
            {
                "name": item.drug_name,
                "spec": item.drug.spec if item.drug else "",
                "unit": item.drug.unit if item.drug else "",
                "qty": item.quantity,
                "price": item.unit_price,
                "amount": amount,
                "usage": usage or "—",
            }
        )
    return {
        "encounter": encounter,
        "patient_name": patient.name if patient else "（未知患者）",
        "patient_id_number": patient.id_number if patient else "",
        "patient_gender": {"male": "男", "female": "女"}.get(
            patient.gender if patient else "", "不详"
        ),
        "patient_age": patient.age if patient else None,
        "patient_address": patient.address if patient else "",
        "patient_phone": patient.phone if patient else "",
        "allergy": (
            patient.allergy_label.replace("过敏史", "", 1).strip()
            if patient
            else "不详"
        ),
        "special_history": patient.special_history if patient else "",
        "department_name": (
            db.get(Department, doctor.department_id).name
            if doctor and db.get(Department, doctor.department_id)
            else ""
        ),
        "doctor_name": doctor.name if doctor else "（未知医师）",
        "record": record,
        "diagnoses": [
            {
                "diagnosis_code": row.diagnosis_code,
                "diagnosis": row.diagnosis,
                "diagnosis_type": row.diagnosis_type,
                "sort_no": row.sort_no,
                "note": row.note,
            }
            for row in list_encounter_diagnoses(db, encounter_id)
        ],
        "record_no": f"BL{encounter.created_at:%Y%m%d}{encounter.id:04d}",
        "prescription_no": header.prescription_no if header else "",
        "prescription_status": header.status if header else "",
        "signature": (
            {
                "signed": True,
                "signed_by": record.signed_by or "",
                "signed_at": record.signed_at.strftime("%Y-%m-%d %H:%M") if record and record.signed_at else "",
                "verify_code": hashlib.sha256(
                    f"{encounter.id}:{record.signed_at.isoformat()}:{settings.SECRET_KEY}".encode()
                ).hexdigest()[:12].upper() if record and record.signed_at else "",
            }
            if record and record.signed_at
            else {"signed": False}
        ),
        "visit_date": encounter.created_at.strftime("%Y-%m-%d"),
        "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "printed_by": operator or "打印终端",
        "lines": lines,
        "total": round(total, 2),
        "tcm": _tcm_prescriptions(db, encounter_id),
        "aux_exams": _aux_exams(db, encounter_id),
    }


def _aux_exams(db: Session, encounter_id: int) -> list[dict]:
    result = []
    labs = (
        db.query(LabRequest)
        .filter(LabRequest.encounter_id == encounter_id)
        .order_by(LabRequest.id)
        .all()
    )
    for row in labs:
        if row.status not in {"reported", "reviewed"} or not row.result_display:
            continue
        result.append(
            {
                "type": "检验",
                "name": row.item_name,
                "result": row.result_display,
                "date": row.reported_at.strftime("%Y-%m-%d") if row.reported_at else "",
                "critical": row.critical_flag,
            }
        )
    images = (
        db.query(ImagingRequest)
        .filter(ImagingRequest.encounter_id == encounter_id)
        .order_by(ImagingRequest.id)
        .all()
    )
    for row in images:
        if row.status != "reported" or not row.report:
            continue
        result.append(
            {
                "type": "影像",
                "name": row.item_name,
                "result": row.report,
                "date": row.reported_at.strftime("%Y-%m-%d") if row.reported_at else "",
                "critical": False,
            }
        )
    return result


def _tcm_prescriptions(db: Session, encounter_id: int) -> list[dict]:
    rows = (
        db.query(TcmPrescription)
        .filter(TcmPrescription.encounter_id == encounter_id)
        .order_by(TcmPrescription.id)
        .all()
    )
    result = []
    for rx in rows:
        result.append(
            {
                "id": rx.id,
                "prescription_no": rx.prescription_no,
                "formula_name": rx.formula_name,
                "packs": rx.packs,
                "decoct_service": rx.decoct_service,
                "decoction_method": rx.decoction_method,
                "total": rx.total_amount,
                "items": [
                    {
                        "name": item.herb_name,
                        "dose": item.dose_g,
                        "special": item.special,
                    }
                    for item in rx.items
                ],
            }
        )
    return result


PRESCRIPTION_CSS = """
    @page { size: A5; margin: 10mm; }
    body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 12px; color: #111; }
    h2 { text-align: center; margin: 4px 0; font-size: 15px; }
    .meta { display: flex; justify-content: space-between; margin: 6px 0; }
    .divider { border-top: 1px dashed #999; margin: 6px 0; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #bbb; padding: 4px 6px; font-size: 12px; }
    th { background: #f2f2f2; }
    .right { text-align: right; }
    .sign { margin-top: 18px; display: flex; justify-content: space-between; }
    @media print { .no-print { display: none; } }
"""

RECEIPT_CSS = """
    @page { size: 58mm auto; margin: 3mm; }
    body { font-family: "Microsoft YaHei", monospace; font-size: 11px; color: #000; width: 58mm; margin: 0 auto; }
    h2 { text-align: center; margin: 2px 0; font-size: 13px; }
    .center { text-align: center; }
    .divider { border-top: 1px dashed #000; margin: 4px 0; }
    table { width: 100%; border-collapse: collapse; }
    td { padding: 1px 0; font-size: 11px; }
    .right { text-align: right; }
    .big { font-size: 14px; font-weight: bold; }
"""


def _print_button() -> str:
    return '<p class="no-print" style="text-align:center"><button onclick="window.print()">打印</button></p>'


def render_prescription(data: dict) -> str:
    meta = _clinic_meta()
    record = data["record"]
    rows = "".join(
        f"<tr><td>{i + 1}</td><td>{escape(line['name'])}</td>"
        f"<td>{escape(line['usage'])}</td>"
        f"<td class=\"right\">{line['qty']}</td>"
        f"<td class=\"right\">{line['price']:.2f}</td>"
        f"<td class=\"right\">{line['amount']:.2f}</td></tr>"
        for i, line in enumerate(data["lines"])
    )
    diagnosis = escape(data["encounter"].diagnosis or "")
    complaint = escape(record.chief_complaint) if record else ""
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>处方单</title>
<style>{PRESCRIPTION_CSS}</style></head>
<body>
{_print_button()}
<h2>{escape(meta['name'])} · 处方笺</h2>
<div class="meta">
  <span>患者：{escape(data['patient_name'])}　{escape(data['patient_id_number'])}</span>
  <span>日期：{today}</span>
</div>
<div class="meta">
  <span>诊断：{diagnosis}</span><span>医师：{escape(data['doctor_name'])}</span>
</div>
<div class="divider"></div>
<p>主诉：{complaint or '—'}</p>
<table>
  <tr><th>#</th><th>药品</th><th>用法</th><th class="right">数量</th><th class="right">单价</th><th class="right">金额</th></tr>
  {rows or '<tr><td colspan="6">（无处方明细）</td></tr>'}
</table>
<div class="divider"></div>
<p class="right">合计：<b>{data['total']:.2f}</b> 元</p>
<div class="sign"><span>药师：__________</span><span>医师签名：__________</span></div>
</body></html>"""


def render_receipt(data: dict) -> str:
    meta = _clinic_meta()
    payment = data["payment"]
    p = data["patient"]
    lines = "".join(
        f"<tr><td>{escape(line['name'])}</td><td class=\"right\">{line['qty']}×{line['price']:.2f}</td>"
        f"<td class=\"right\">{line['amount']:.2f}</td></tr>"
        for line in data["lines"]
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>收费收据</title>
<style>{RECEIPT_CSS}</style></head>
<body>
{_print_button()}
<h2>{escape(meta['name'])}</h2>
<p class="center">收费收据</p>
<div class="divider"></div>
<p>患者：{escape(p.name)}</p>
<p>单号：{payment.id}　票据号：{payment.invoice_no or '—'}</p>
{f'<p class="center">取药码：{escape(data["pickup_code"])}</p>' if data.get("pickup_code") else ''}
<p>日期：{payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else ''}</p>
<div class="divider"></div>
<table>
{lines or '<tr><td colspan="3">（无明细）</td></tr>'}
</table>
<div class="divider"></div>
<p class="right big">应收：{payment.amount:.2f} 元</p>
{f'<p class="right">医保支付：{payment.insurance_amount:.2f} 元</p>' if settings.INSURANCE_ENABLED else ''}
{f'<p class="right">优惠/减免：{payment.discount_amount:.2f} 元（{escape(payment.discount_reason or "")}）</p>' if payment.discount_amount else ''}
<p class="right">自费：{payment.self_pay_amount:.2f} 元</p>
{f'<p class="right">分渠道：{ " / ".join(f"{escape(a.channel)} {a.amount:.2f}" for a in payment.allocations) }</p>' if payment.allocations else ''}
{f'<p class="right">累计已退：{payment.refunded_amount:.2f} 元</p>' if payment.refunded_amount else ''}
<p class="right">实收（扣除退款）：{payment.net_amount:.2f} 元</p>
<p class="right">支付方式：{ {'cash':'现金','wechat':'微信支付','alipay':'支付宝','pos':'POS 刷卡','insurance_card':'医保卡','mixed':'混合支付'}.get(payment.channel, payment.channel) }</p>
<p class="right">状态：{ {'paid':'已支付','partially_refunded':'部分退费','refunded':'已退费'}.get(payment.status, payment.status) }</p>
<div class="divider"></div>
<p class="center"><b>下一步指引</b></p>
<p class="center">{data.get('next_step') or '请按导诊单前往相应科室'}</p>
<div class="divider"></div>
<p class="center">打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""


@router.post("/tokens")
def create_print_token(
    kind: str = "",
    ref_id: int | None = None,
    ttl_seconds: int = 120,
    db: Session = Depends(get_db),
    user=Depends(require_login),
) -> dict:
    import hashlib
    import secrets
    from datetime import datetime, timedelta

    from .models import PrintToken

    raw = secrets.token_urlsafe(24)
    db.add(
        PrintToken(
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            kind=kind,
            ref_id=ref_id,
            expires_at=datetime.now() + timedelta(seconds=min(max(ttl_seconds, 10), 600)),
            created_by=user.username,
        )
    )
    db.commit()
    return {"token": raw, "expires_in": min(max(ttl_seconds, 10), 600)}


@router.get("/verify-medical-record/{encounter_id}")
def verify_medical_record(
    encounter_id: int,
    code: str,
    db: Session = Depends(get_db),
    _=Depends(require_print_access),
):
    record = get_medical_record(db, encounter_id)
    if not record or not record.signed_at:
        return {"valid": False, "reason": "病历未签名"}
    expected = hashlib.sha256(
        f"{encounter_id}:{record.signed_at.isoformat()}:{settings.SECRET_KEY}".encode()
    ).hexdigest()[:12].upper()
    return {
        "valid": code.strip().upper() == expected,
        "signed_by": record.signed_by,
        "signed_at": record.signed_at,
        "verify_code": expected,
    }


@router.get("/logs")
def logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: None = Depends(require_login),
):
    rows = db.query(PrintLog).order_by(PrintLog.id.desc()).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "id": row.id,
            "document_type": row.document_type,
            "ref_id": row.ref_id,
            "operator": row.operator,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/barcode/{code}.svg")
def barcode_svg(code: str):
    try:
        svg = code128_svg(code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/prescription-header/{prescription_id}", response_class=HTMLResponse)
def print_prescription_header(prescription_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "prescription-header", prescription_id)
    from app.modules.encounter.models import PrescriptionItem

    header = db.get(Prescription, prescription_id)
    if not header:
        raise HTTPException(status_code=404, detail="处方不存在")
    encounter = get_encounter(db, header.encounter_id)
    registration = get_registration(db, encounter.registration_id) if encounter else None
    patient = get_patient(db, registration.patient_id) if registration else None
    doctor = get_doctor(db, registration.doctor_id) if registration else None
    items = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.prescription_id == prescription_id)
        .order_by(PrescriptionItem.id)
        .all()
    )
    rows = "".join(
        f"<tr><td>{escape(item.drug_name)}</td><td>{escape(item.drug.spec if item.drug else '')}</td>"
        f"<td>{item.quantity}</td><td>{escape(item.dosage)} {escape(item.frequency)} {escape(item.route)}</td>"
        f"<td>{item.quantity * item.unit_price:.2f}</td></tr>"
        for item in items
    )
    meta = _clinic_meta()
    status = {
        "pending_review": "待药师审核",
        "approved": "已审核",
        "rejected": "已退回",
        "dispensing": "调配中",
        "dispensed": "已发药",
        "cancelled": "已作废",
    }.get(header.status, header.status)
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>处方 {escape(header.prescription_no)}</title><style>{PRESCRIPTION_CSS}</style></head><body>
{_print_button()}
<h2>{escape(meta['name'])}</h2>
<p class="center big">门诊处方</p>
<p>处方号：{escape(header.prescription_no)}　类型：{escape(header.type)}　状态：{escape(status)}</p>
<p>患者：{escape(patient.name if patient else '—')}　
   性别：{escape({'male':'男','female':'女'}.get(patient.gender if patient else '', '不详'))}　
   年龄：{patient.age if patient and patient.age is not None else '年龄不详'}</p>
<p>科室/医生：{escape(doctor.name if doctor else '—')}　开方：{escape(header.prescribed_by or '—')}</p>
<div class="divider"></div>
<table><tr><th>药品</th><th>规格</th><th>数量</th><th>用法</th><th>金额</th></tr>
{rows or '<tr><td colspan="5">无明细</td></tr>'}</table>
<div class="divider"></div>
<p>审核药师：{escape(header.reviewed_by or '—')}　审核意见：{escape(header.review_note or '—')}</p>
<p>医师签名：__________　日期：{header.created_at:%Y-%m-%d}</p>
</body></html>"""
    html = apply_print_profile(html, load_print_profile(db))
    return HTMLResponse(_with_reprint_banner(html, print_count))


@router.get("/prescription/{encounter_id}", response_class=HTMLResponse)
def print_prescription(encounter_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "prescription", encounter_id)
    try:
        data = _collect(db, encounter_id, getattr(user, "username", "") or "")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(_with_reprint_banner(render_full_set(data, load_print_profile(db)), print_count))


@router.get("/medical-record/{encounter_id}", response_class=HTMLResponse)
def print_medical_record(encounter_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "medical-record", encounter_id)
    try:
        data = _collect(db, encounter_id, getattr(user, "username", "") or "")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(_with_reprint_banner(render_record(data, load_print_profile(db)), print_count))


@router.get("/western-prescription/{encounter_id}", response_class=HTMLResponse)
def print_western(encounter_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "western-prescription", encounter_id)
    try:
        data = _collect(db, encounter_id, getattr(user, "username", "") or "")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(_with_reprint_banner(render_western(data, load_print_profile(db)), print_count))


@router.get("/tcm-prescription/{encounter_id}", response_class=HTMLResponse)
def print_tcm(encounter_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "tcm-prescription", encounter_id)
    try:
        data = _collect(db, encounter_id, getattr(user, "username", "") or "")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(_with_reprint_banner(render_tcm(data, load_print_profile(db)), print_count))


@router.get("/receipt/{payment_id}", response_class=HTMLResponse)
def print_receipt(payment_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "receipt", payment_id)
    payment = get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="收费记录不存在")
    encounter = get_encounter(db, payment.encounter_id)
    if not encounter:
        raise HTTPException(status_code=404, detail="就诊记录不存在")
    registration = get_registration(db, encounter.registration_id)
    patient = get_patient(db, registration.patient_id)

    lines = []
    for charge in list_charges(db, encounter.id):
        lines.append(
            {
                "name": charge.item_name,
                "qty": charge.quantity,
                "price": charge.unit_price,
                "amount": charge.amount,
                "type": charge.charge_type,
            }
        )
    types = {line.get("type") for line in lines}
    steps = []
    if "drug" in types:
        steps.append("药房取药")
    if "lab" in types:
        steps.append("检验科采样/取报告")
    if "imaging" in types:
        steps.append("影像/检查科")
    if "treatment" in types:
        steps.append("治疗室")
    data = {
        "payment": payment, "patient": patient, "lines": lines,
        "next_step": " → ".join(steps) if steps else "可直接离院",
    }
    pickup = (
        db.query(PharmacyPickupCode)
        .filter(PharmacyPickupCode.encounter_id == encounter.id)
        .first()
    )
    data["pickup_code"] = pickup.code if pickup else ""
    html = apply_print_profile(render_receipt(data), load_print_profile(db))
    return HTMLResponse(_with_reprint_banner(html, print_count))

@router.get("/retail/{sale_id}", response_class=HTMLResponse)
def print_retail(sale_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "retail", sale_id)
    sale = get_retail_sale(db, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="零售单不存在")
    rows = "".join(
        f"<tr><td>{escape(item.name)}</td>"
        f"<td class=\"right\">{item.quantity}×{item.unit_price:.2f}</td>"
        f"<td class=\"right\">{item.amount:.2f}</td></tr>"
        for item in sale.items
    )
    channel = {"cash": "现金", "wechat": "微信", "alipay": "支付宝"}.get(
        sale.channel, sale.channel
    )
    meta = _clinic_meta()
    status = "已退货" if sale.status == "refunded" else "已完成"
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>零售小票</title><style>{RECEIPT_CSS}</style></head><body>{_reprint_banner(print_count)}
{_print_button()}
<h2>{escape(meta['name'])}</h2>
<p class="center">零售小票</p>
<div class="divider"></div>
<p>单号：{escape(sale.sale_no)}</p>
<p>日期：{sale.created_at:%Y-%m-%d %H:%M}</p>
<p>顾客：{escape(sale.customer_name or "散客")}</p>
<div class="divider"></div>
<table>{rows}</table>
<div class="divider"></div>
<p class="right big">合计：{sale.total_amount:.2f} 元</p>
<p class="right">支付方式：{channel}</p>
<p class="right">状态：{status}</p>
<p class="right">销售员：{escape(sale.sold_by or "—")}</p>
<div class="divider"></div>
<p class="center">非医保零售，请保留小票</p>
<p class="center">打印时间：{datetime.now():%Y-%m-%d %H:%M}</p>
</body></html>"""
    return HTMLResponse(
        _with_reprint_banner(apply_print_profile(html, load_print_profile(db)), print_count)
    )


@router.get("/dispense-slip/{encounter_id}", response_class=HTMLResponse)
def print_dispense_slip(encounter_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "dispense-slip", encounter_id)
    try:
        data = build_dispense_slip(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    meta = _clinic_meta()
    rows = "".join(
        f"<tr><td>{escape(item['drug_name'])}<br><span class='small'>"
        f"{escape(item['spec'] or '')} {escape(item['dosage_form'] or '')}"
        + (
            f"　批号 {escape(item.get('batch_no'))}　效期 {escape(item.get('expiry'))}"
            if item.get("batch_no")
            else ""
        )
        + "</span></td>"
        f"<td>{item['quantity']}{escape(item['unit'] or '')}</td>"
        f"<td>{item['amount']:.2f}</td>"
        f"<td>{escape(item['usage'])}</td></tr>"
        for item in data["items"]
    )
    tcm = "".join(
        f"<p>中药处方 {escape(rx['prescription_no'])}：{escape(rx['formula_name'] or '')}，"
        f"{rx['packs']} 剂，{escape(rx['decoction_method'] or '')}</p>"
        for rx in data["tcm_prescriptions"]
    )
    total = sum(item["amount"] for item in data["items"])
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>取药凭证</title><style>{RECEIPT_CSS}
.small {{ color:#555; font-size:10px; }}
</style></head><body>{_reprint_banner(print_count)}
{_print_button()}
<h2>{escape(meta['name'])}</h2>
<p class="center big">取药凭证</p>
<p class="center small">执行指引 + 用药核对清单</p>
<div class="divider"></div>
<p>患者：{escape(data['patient']['name'])}　
   {escape(data['patient']['gender'])}　
   {data['patient']['age'] if data['patient']['age'] is not None else '—'}岁</p>
<p>就诊卡/患者号：{escape(str(data['patient']['patient_no'] or '—'))}　
   就诊：{data['encounter_id']}</p>
<p>科室：{escape(data['department'] or '—')}　医生：{escape(data['doctor_name'] or '—')}</p>
<p>结算时间：{escape((data['settled_at'] or '—').replace('T', ' '))}　
   仅限当日有效：{escape(data['valid_until'] or '—')}</p>
<div class="divider"></div>
<p class="big">取药指引</p>
<p>药房：{escape(data['pharmacy_name'])}　窗口：{escape(data['window_no'] or '—')}</p>
<p>取药号：<b>{escape(data['queue_no'] or '—')}</b>　
   当前等待：{data['waiting_count']} 人　共 {data['prescription_count']} 张处方</p>
<div class="divider"></div>
<p>临床诊断：{escape(data['diagnosis'] or '—')}</p>
<div class="divider"></div>
<table><tr><th>药品</th><th>数量</th><th>金额</th><th>用法用量</th></tr>
{rows or '<tr><td colspan="4">（无药品明细）</td></tr>'}
</table>
{tcm}
<p class="right big">药品合计：{total:.2f} 元</p>
<div class="divider"></div>
<p>医师：{escape(data['signatures']['doctor'] or '—')}　
   调配药师：{escape(data['signatures']['dispenser'] or '—')}　
   核对药师：{escape(data['signatures']['checker'] or '—')}</p>
<p>取药人：{escape(data['signatures']['receiver'] or '—')}　
   发药时间：{escape((data['dispensed_at'] or '—').replace('T', ' '))}</p>
<div class="divider"></div>
{''.join(f'<p class="small">{escape(tip)}</p>' for tip in data['tips'])}
<p class="center small">打印时间：{escape(data['printed_at'].replace('T', ' '))}</p>
</body></html>"""
    return HTMLResponse(
        _with_reprint_banner(apply_print_profile(html, load_print_profile(db)), print_count)
    )


@router.get("/dispense-label/{dispense_id}", response_class=HTMLResponse)
def print_dispense_label(dispense_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "dispense-label", dispense_id)
    dispense = get_dispense(db, dispense_id)
    if not dispense:
        raise HTTPException(status_code=404, detail="发药记录不存在")
    encounter = get_encounter(db, dispense.encounter_id)
    registration = get_registration(db, encounter.registration_id) if encounter else None
    patient = get_patient(db, registration.patient_id) if registration else None
    items = list_prescription_items(db, dispense.encounter_id) if encounter else []
    rows = "".join(
        f"<tr><td>{escape(item.drug_name)}</td><td>{item.quantity}</td>"
        f"<td>{escape(' '.join(x for x in (item.dosage, item.frequency, item.route) if x))}</td></tr>"
        for item in items
    )
    meta = _clinic_meta()
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>发药袋标签</title><style>{RECEIPT_CSS}</style></head><body>{_reprint_banner(print_count)}
{_print_button()}
<h2>{escape(meta['name'])}</h2>
<p class="center big">发药袋标签</p>
<div class="divider"></div>
<p>患者：{escape(patient.name if patient else '—')}　
   {escape({'male':'男','female':'女'}.get(patient.gender if patient else '', '不详'))} /
   {patient.age if patient and patient.age is not None else '—'}岁</p>
<p>就诊：{dispense.encounter_id}　取药人：{escape(dispense.receiver_name or '—')}</p>
<div class="divider"></div>
<table><tr><th>药品</th><th>数量</th><th>用法</th></tr>{rows}</table>
<div class="divider"></div>
<p>发药人：{escape(dispense.verified_by or '—')}　
   时间：{dispense.verified_at.strftime('%Y-%m-%d %H:%M') if dispense.verified_at else '—'}</p>
<p class="center">请核对姓名、药名、用法；有疑问请咨询药师</p>
</body></html>"""
    return HTMLResponse(
        _with_reprint_banner(apply_print_profile(html, load_print_profile(db)), print_count)
    )


@router.get("/nursing-label/{order_id}", response_class=HTMLResponse)
def print_nursing_label(order_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "nursing-label", order_id)
    order = db.get(NursingOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="护理执行单不存在")
    encounter = get_encounter(db, order.encounter_id)
    registration = get_registration(db, encounter.registration_id) if encounter else None
    patient = get_patient(db, registration.patient_id) if registration else None
    preparation = order.preparations[-1] if order.preparations else None
    meta = _clinic_meta()
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>输液瓶签</title><style>{RECEIPT_CSS}</style></head><body>{_reprint_banner(print_count)}
{_print_button()}
<h2>{escape(meta['name'])}</h2>
<p class="center big">输液 / 注射瓶签</p>
<div class="divider"></div>
<p>患者：{escape(patient.name if patient else '—')}　
   {escape({'male':'男','female':'女'}.get(patient.gender if patient else '', '不详'))} /
   {patient.age if patient and patient.age is not None else '—'}岁</p>
<p>座位：{escape(order.seat_no or '—')}　执行单：{order.id}</p>
<div class="divider"></div>
<p class="big">药品：{escape(order.item_name)}</p>
<p>剂量：{escape(order.dosage or '—')}　途径：{escape(order.route or '—')}　
   频次：{escape(order.frequency or '—')}</p>
<p>溶媒：{escape(preparation.solvent if preparation else '—')}　
   批号：{escape(preparation.batch_no if preparation else '—')}</p>
<p>配药：{escape(preparation.prepared_by if preparation else '—')}　
   核对：{escape(preparation.checked_by if preparation else '—')}</p>
<div class="divider"></div>
<p class="center">执行前请核对患者姓名、药名、剂量、途径、时间</p>
</body></html>"""
    return HTMLResponse(
        _with_reprint_banner(apply_print_profile(html, load_print_profile(db)), print_count)
    )


LAB_CSS = """
    @page { size: A5; margin: 10mm; }
    body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 12px; color: #111; }
    h2 { text-align: center; margin: 4px 0; font-size: 16px; }
    .meta { display: flex; justify-content: space-between; margin: 6px 0; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th, td { border: 1px solid #888; padding: 6px; font-size: 12px; }
    th { background: #f2f2f2; }
    .right { text-align: right; }
    .flag { font-weight: bold; color: #b91c1c; }
    .critical { border: 1px solid #b91c1c; color: #b91c1c; padding: 6px; margin-top: 8px; }
    .sign { margin-top: 16px; display: flex; justify-content: space-between; }
    @media print { .no-print { display: none; } }
"""


@router.get("/imaging-report/{request_id}", response_class=HTMLResponse)
def print_imaging_report(request_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "imaging-report", request_id)
    request = db.get(ImagingRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="检查申请不存在")
    encounter = get_encounter(db, request.encounter_id)
    registration = get_registration(db, encounter.registration_id) if encounter else None
    patient = get_patient(db, registration.patient_id) if registration else None
    doctor = get_doctor(db, registration.doctor_id) if registration else None
    data = {
        "patient_name": patient.name if patient else "",
        "report_no": request.accession_no,
        "encounter_id": request.encounter_id,
        "item_name": request.item_name,
        "body_part": request.item.body_part if request.item else "",
        "diagnosis": encounter.diagnosis if encounter else "",
        "doctor_name": doctor.name if doctor else "",
        "status": request.status,
        "findings": request.findings or request.report or "",
        "impression": request.impression or "",
        "image_url": request.image_url,
        "reported_by": request.reported_by or "",
        "reviewed_by": request.reviewed_by or "",
        "reported_at": request.reported_at.strftime("%Y-%m-%d %H:%M") if request.reported_at else "",
    }
    html = apply_print_profile(render_imaging_report(data, load_print_profile(db)), load_print_profile(db))
    return HTMLResponse(_with_reprint_banner(html, print_count))


@router.get("/lab-report/{request_id}", response_class=HTMLResponse)
def print_lab_report(request_id: int, db: Session = Depends(get_db), user=Depends(require_print_access)):
    print_count = _log_print(db, user, "lab-report", request_id)
    request = get_request(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="检验申请不存在")
    encounter = get_encounter(db, request.encounter_id)
    registration = get_registration(db, encounter.registration_id) if encounter else None
    patient = get_patient(db, registration.patient_id) if registration else None
    doctor = get_doctor(db, registration.doctor_id) if registration else None
    meta = _clinic_meta()
    flag_text = {"H": "↑ 偏高", "L": "↓ 偏低", "N": "正常", "": "—"}.get(
        request.abnormal_flag, request.abnormal_flag
    )
    reference = "—"
    if request.reference_low is not None and request.reference_high is not None:
        reference = f"{request.reference_low:g} – {request.reference_high:g}"
    critical = ""
    if request.critical_flag:
        critical = (
            '<div class="critical">危急值：'
            + escape(request.critical_note or "")
            + "　已通知："
            + escape(request.critical_notified_to or "未登记")
            + "</div>"
        )
    status = {
        "reported": "已报告（待审核）",
        "reviewed": "已审核",
        "pending": "待采样",
        "collected": "已采样",
        "received": "已签收",
        "testing": "检验中",
        "rejected": "标本拒收",
    }.get(request.status, request.status)
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>检验报告单</title><style>{LAB_CSS}</style></head><body>{_reprint_banner(print_count)}
{_print_button()}
<h2>{escape(meta['name'])} · 检验报告单</h2>
<div class="meta">
  <span>患者：{escape(patient.name if patient else '—')}　
        {escape(patient.id_number if patient else '')}</span>
  <span>报告号：{escape(request.report_no or '—')}</span>
</div>
<div class="meta">
  <span>就诊：{request.encounter_id}　诊断：{escape(encounter.diagnosis if encounter else '')}　
        医生：{escape(doctor.name if doctor else '')}</span>
  <span>标本号：{escape(request.specimen_no or '—')}　
        标本：{escape(request.specimen_type)}</span>
</div>
<table>
  <tr><th>项目</th><th>结果</th><th>单位</th><th>参考范围</th><th>异常</th></tr>
  <tr>
    <td>{escape(request.item_name)}</td>
    <td>{escape(request.result_display or '—')}</td>
    <td>{escape(request.result_unit or '')}</td>
    <td>{escape(reference)}</td>
    <td class="flag">{escape(flag_text)}</td>
  </tr>
</table>
{critical}
<div class="sign">
  <span>检验者：{escape(request.testing_by or '—')}</span>
  <span>审核者：{escape(request.reviewed_by or '—')}</span>
  <span>状态：{escape(status)}</span>
</div>
<p class="right">报告时间：{request.reported_at.strftime('%Y-%m-%d %H:%M') if request.reported_at else '—'}</p>
<p class="right">审核时间：{request.reviewed_at.strftime('%Y-%m-%d %H:%M') if request.reviewed_at else '—'}</p>
<p class="center">本报告仅对送检标本负责，如有疑问请及时联系检验科。</p>
</body></html>"""
    return HTMLResponse(
        _with_reprint_banner(apply_print_profile(html, load_print_profile(db)), print_count)
    )
