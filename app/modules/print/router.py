from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import settings
from app.modules.billing.service import get_payment
from app.modules.print.documents import (
    render_full_set,
    render_record,
    render_tcm,
    render_western,
)
from app.modules.print.barcode import code128_svg
from app.modules.pharmacy.models import PharmacyPickupCode
from app.modules.charges.service import list_charges
from app.modules.encounter.service import get_encounter, get_medical_record, list_prescription_items
from app.modules.lis.service import get_request
from app.modules.lis.models import LabRequest
from app.modules.pacs.models import ImagingRequest
from app.modules.patient.service import get_patient
from app.modules.staff.models import Department
from app.modules.tcm.models import TcmPrescription
from app.modules.registration.service import get_registration
from app.modules.staff.service import get_doctor

router = APIRouter(prefix="/print", tags=["print"])


def _clinic_meta() -> dict:
    return {
        "name": settings.CLINIC_NAME,
        "phone": settings.CLINIC_PHONE,
        "address": settings.CLINIC_ADDRESS,
    }


def _collect(db: Session, encounter_id: int) -> dict:
    encounter = get_encounter(db, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    registration = get_registration(db, encounter.registration_id)
    patient = get_patient(db, registration.patient_id)
    doctor = get_doctor(db, registration.doctor_id)
    record = get_medical_record(db, encounter_id)

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
        "department_name": (
            db.get(Department, doctor.department_id).name
            if doctor and db.get(Department, doctor.department_id)
            else ""
        ),
        "doctor_name": doctor.name if doctor else "（未知医师）",
        "record": record,
        "record_no": f"BL{encounter.created_at:%Y%m%d}{encounter.id:04d}",
        "visit_date": encounter.created_at.strftime("%Y-%m-%d"),
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
<p class="right">自费：{payment.self_pay_amount:.2f} 元</p>
{f'<p class="right">累计已退：{payment.refunded_amount:.2f} 元</p>' if payment.refunded_amount else ''}
<p class="right">实收（扣除退款）：{payment.net_amount:.2f} 元</p>
<p class="right">支付方式：{ {'cash':'现金','wechat':'微信支付','alipay':'支付宝','pos':'POS 刷卡','insurance_card':'医保卡'}.get(payment.channel, payment.channel) }</p>
<p class="right">状态：{ {'paid':'已支付','partially_refunded':'部分退费','refunded':'已退费'}.get(payment.status, payment.status) }</p>
<div class="divider"></div>
<p class="center">打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""


@router.get("/barcode/{code}.svg")
def barcode_svg(code: str):
    try:
        svg = code128_svg(code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/prescription/{encounter_id}", response_class=HTMLResponse)
def print_prescription(encounter_id: int, db: Session = Depends(get_db)):
    try:
        data = _collect(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(render_full_set(data))


@router.get("/medical-record/{encounter_id}", response_class=HTMLResponse)
def print_medical_record(encounter_id: int, db: Session = Depends(get_db)):
    try:
        data = _collect(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(render_record(data))


@router.get("/western-prescription/{encounter_id}", response_class=HTMLResponse)
def print_western(encounter_id: int, db: Session = Depends(get_db)):
    try:
        data = _collect(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(render_western(data))


@router.get("/tcm-prescription/{encounter_id}", response_class=HTMLResponse)
def print_tcm(encounter_id: int, db: Session = Depends(get_db)):
    try:
        data = _collect(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(render_tcm(data))


@router.get("/receipt/{payment_id}", response_class=HTMLResponse)
def print_receipt(payment_id: int, db: Session = Depends(get_db)):
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
            }
        )
    data = {"payment": payment, "patient": patient, "lines": lines}
    pickup = (
        db.query(PharmacyPickupCode)
        .filter(PharmacyPickupCode.encounter_id == encounter.id)
        .first()
    )
    data["pickup_code"] = pickup.code if pickup else ""
    return HTMLResponse(render_receipt(data))

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


@router.get("/lab-report/{request_id}", response_class=HTMLResponse)
def print_lab_report(request_id: int, db: Session = Depends(get_db)):
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
    return HTMLResponse(
        f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>检验报告单</title><style>{LAB_CSS}</style></head><body>
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
    )
