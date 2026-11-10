from datetime import date, datetime, time
from sqlalchemy.orm import Session

from app.modules.billing.models import Payment
from app.modules.encounter.models import Encounter
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration

from .models import InvoiceBatch
from .operations import InvoiceOperation


def _get_payment(db: Session, payment_id: int) -> Payment:
    payment = db.get(Payment, payment_id)
    if not payment:
        raise ValueError("收费记录不存在")
    if not payment.invoice_no:
        raise ValueError("该收费没有发票号")
    return payment


def _check_owner(payment: Payment, operator: str, allow_all: bool) -> None:
    if not allow_all and payment.created_by and payment.created_by != operator:
        raise ValueError("只能操作本人收费的发票")


def print_invoice(db: Session, payment_id: int, operator: str, allow_all: bool = False) -> Payment:
    payment = _get_payment(db, payment_id)
    _check_owner(payment, operator, allow_all)
    if payment.invoice_status == "void":
        raise ValueError("发票已作废，不能重打")
    payment.invoice_print_count += 1
    payment.invoice_printed_at = datetime.now()
    db.add(
        InvoiceOperation(
            payment_id=payment.id,
            invoice_no=payment.invoice_no or "",
            action="print",
            operator=operator,
        )
    )
    db.commit()
    db.refresh(payment)
    return payment


def void_invoice(
    db: Session, payment_id: int, reason: str, operator: str, allow_all: bool = False
) -> Payment:
    payment = _get_payment(db, payment_id)
    _check_owner(payment, operator, allow_all)
    if payment.invoice_status == "void":
        raise ValueError("发票已作废")
    if not reason.strip():
        raise ValueError("请填写作废原因")
    payment.invoice_status = "void"
    payment.invoice_voided_at = datetime.now()
    payment.invoice_voided_by = operator
    payment.invoice_void_reason = reason.strip()
    db.add(
        InvoiceOperation(
            payment_id=payment.id,
            invoice_no=payment.invoice_no or "",
            action="void",
            operator=operator,
            reason=reason.strip(),
        )
    )
    db.commit()
    db.refresh(payment)
    return payment


def usage(db: Session, start_date: date | None = None, end_date: date | None = None) -> dict:
    start = datetime.combine(start_date, time.min) if start_date else None
    end = datetime.combine(end_date, time.max) if end_date else None
    query = (
        db.query(Payment, Patient)
        .join(Encounter, Payment.encounter_id == Encounter.id)
        .join(Registration, Encounter.registration_id == Registration.id)
        .join(Patient, Registration.patient_id == Patient.id)
        .filter(Payment.invoice_no.is_not(None))
    )
    if start:
        query = query.filter(Payment.created_at >= start)
    if end:
        query = query.filter(Payment.created_at <= end)
    rows = query.order_by(Payment.id.desc()).all()
    invoices = [
        {
            "payment_id": payment.id,
            "invoice_no": payment.invoice_no,
            "invoice_status": payment.invoice_status,
            "print_count": payment.invoice_print_count,
            "amount": payment.amount,
            "channel": payment.channel,
            "created_by": payment.created_by,
            "created_at": payment.created_at,
            "patient_name": patient.name,
            "void_reason": payment.invoice_void_reason,
        }
        for payment, patient in rows
    ]
    batches = []
    for batch in db.query(InvoiceBatch).order_by(InvoiceBatch.id.desc()).all():
        used = max(0, batch.next_no - batch.start_no)
        related = [row for row in invoices if batch.prefix in (row["invoice_no"] or "")]
        batches.append(
            {
                "id": batch.id,
                "prefix": batch.prefix,
                "start_no": batch.start_no,
                "end_no": batch.end_no,
                "next_no": batch.next_no,
                "used": used,
                "remaining": max(0, batch.end_no - batch.next_no + 1),
                "assigned_to": batch.assigned_to,
                "status": batch.status,
                "invoice_count": len(related),
                "void_count": sum(1 for row in related if row["invoice_status"] == "void"),
            }
        )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "invoices": invoices,
        "batches": batches,
        "total": len(invoices),
        "void_count": sum(1 for row in invoices if row["invoice_status"] == "void"),
        "printed_count": sum(row["print_count"] for row in invoices),
    }


def operations(db: Session, payment_id: int) -> list[InvoiceOperation]:
    return (
        db.query(InvoiceOperation)
        .filter(InvoiceOperation.payment_id == payment_id)
        .order_by(InvoiceOperation.id.desc())
        .all()
    )
