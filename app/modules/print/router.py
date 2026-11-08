from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.billing.service import get_payment
from app.modules.charges.service import list_charges
from app.modules.encounter.service import get_encounter, get_medical_record, list_prescription_items
from app.modules.patient.service import get_patient
from app.modules.registration.service import get_registration
from app.modules.staff.service import get_doctor

router = APIRouter(prefix="/print", tags=["print"])


def _clinic_meta() -> dict:
    return {"name": "社区卫生服务中心（演示）", "phone": "0571-12345678", "address": "演示地址"}


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
        "doctor_name": doctor.name if doctor else "（未知医师）",
        "record": record,
        "lines": lines,
        "total": round(total, 2),
    }


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
<p>日期：{payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else ''}</p>
<div class="divider"></div>
<table>
{lines or '<tr><td colspan="3">（无明细）</td></tr>'}
</table>
<div class="divider"></div>
<p class="right big">应收：{payment.amount:.2f} 元</p>
<p class="right">医保支付：{payment.insurance_amount:.2f} 元</p>
<p class="right">自费：{payment.self_pay_amount:.2f} 元</p>
<p class="right">状态：{('已支付' if payment.status == 'paid' else '已退费')}</p>
<div class="divider"></div>
<p class="center">打印时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""


@router.get("/prescription/{encounter_id}", response_class=HTMLResponse)
def print_prescription(encounter_id: int, db: Session = Depends(get_db)):
    try:
        data = _collect(db, encounter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return HTMLResponse(render_prescription(data))


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
    return HTMLResponse(render_receipt(data))
