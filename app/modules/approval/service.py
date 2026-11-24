from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (
    ApprovalEvent,
    ApprovalFlowStep,
    ApprovalRequest,
    ApprovalStep,
)


def _row(kind, item_id, title, applicant, status, created_at, action):
    return {
        "kind": kind,
        "id": item_id,
        "title": title,
        "applicant": applicant or "",
        "status": status,
        "created_at": created_at,
        "action": action,
    }


def inbox(db: Session, role: str) -> list[dict]:
    """统一待办视图：不改变各业务表自己的状态，只聚合待处理项。"""
    items: list[dict] = []
    if role in ("admin", "pharmacist"):
        from app.modules.encounter.models import Prescription
        from app.modules.patient.models import Patient
        from app.modules.registration.models import Registration
        from app.modules.encounter.models import Encounter

        rows = (
            db.query(Prescription, Encounter, Registration, Patient)
            .join(Encounter, Prescription.encounter_id == Encounter.id)
            .join(Registration, Encounter.registration_id == Registration.id)
            .join(Patient, Registration.patient_id == Patient.id)
            .filter(
                Prescription.status == "pending_review",
                Prescription.type != "tcm_herb",
            )
            .order_by(Prescription.id)
            .all()
        )
        for rx, encounter, registration, patient in rows:
            items.append(
                _row(
                    "prescription_review",
                    rx.id,
                    f"{rx.prescription_no} {patient.name}",
                    rx.prescribed_by,
                    rx.status,
                    rx.created_at,
                    f"/encounters/{encounter.id}/prescriptions/{rx.id}/review",
                )
            )
    if role in ("admin", "pharmacist", "warehouse"):
        from app.modules.catalog_proposal.models import CatalogProposal

        rows = db.query(CatalogProposal).filter(
            CatalogProposal.status.in_(("pending_pharmacy", "pending_warehouse"))
        ).order_by(CatalogProposal.id).all()
        for row in rows:
            if role == "pharmacist" and row.status != "pending_pharmacy":
                continue
            if role == "warehouse" and row.status != "pending_warehouse":
                continue
            items.append(
                _row(
                    "catalog_proposal",
                    row.id,
                    f"{row.kind} {row.name}",
                    row.requested_by,
                    row.status,
                    row.created_at,
                    f"/catalog-proposals/{row.id}/review",
                )
            )
    if role in ("admin", "warehouse"):
        from app.modules.warehouse.models import OutboundOrder

        rows = db.query(OutboundOrder).filter(
            OutboundOrder.status == "submitted"
        ).order_by(OutboundOrder.id).all()
        for row in rows:
            items.append(
                _row(
                    "warehouse_outbound",
                    row.id,
                    row.outbound_no,
                    row.applicant,
                    row.status,
                    getattr(row, "created_at", None),
                    f"/warehouse/outbound-orders/{row.id}/approve",
                )
            )
    if role in ("admin", "director"):
        from app.modules.warehouse.models import PurchaseRequest

        rows = db.query(PurchaseRequest).filter(
            PurchaseRequest.status == "submitted"
        ).order_by(PurchaseRequest.id).all()
        for row in rows:
            items.append(
                _row(
                    "purchase_request",
                    row.id,
                    row.request_no,
                    row.requester,
                    row.status,
                    getattr(row, "created_at", None),
                    f"/warehouse/purchase-requests/{row.id}/approve",
                )
            )
        from app.modules.archive.models import ArchiveDestructionRequest

        rows = db.query(ArchiveDestructionRequest).filter(
            ArchiveDestructionRequest.status == "pending"
        ).order_by(ArchiveDestructionRequest.id).all()
        for row in rows:
            items.append(
                _row(
                    "archive_destruction",
                    row.id,
                    f"病案销毁申请 {row.id}",
                    row.requested_by,
                    row.status,
                    row.requested_at,
                    f"/archive/destruction-requests/{row.id}/approve",
                )
            )
        from app.modules.catalog_proposal.models import CatalogProposal

        rows = db.query(CatalogProposal).filter(
            CatalogProposal.kind == "treatment",
            CatalogProposal.status == "pending_director",
        ).order_by(CatalogProposal.id).all()
        for row in rows:
            items.append(
                _row(
                    "treatment_proposal",
                    row.id,
                    row.name,
                    row.requested_by,
                    row.status,
                    row.created_at,
                    f"/catalog-proposals/{row.id}/review",
                )
            )
    if role in ("admin", "hr", "director"):
        from app.modules.hr.models import SalaryRequest

        rows = db.query(SalaryRequest).filter(
            SalaryRequest.status == "pending"
        ).order_by(SalaryRequest.id).all()
        for row in rows:
            items.append(
                _row(
                    "salary_request",
                    row.id,
                    f"薪资申请 {row.id}",
                    row.requested_by,
                    row.status,
                    row.requested_at,
                    f"/hr/salary-requests/{row.id}/approve",
                )
            )
    items.sort(
        key=lambda x: x["created_at"].timestamp() if x["created_at"] else 0,
        reverse=True,
    )
    return items


def summary(db: Session, role: str) -> dict:
    rows = inbox(db, role)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    return {"total": len(rows), "counts": counts}


def record_event(
    db: Session,
    biz_type: str,
    biz_id: int,
    action: str,
    actor: str,
    note: str = "",
    step: str = "review",
) -> None:
    db.add(
        ApprovalEvent(
            biz_type=biz_type,
            biz_id=biz_id,
            step=step,
            action=action,
            actor=actor,
            note=note,
        )
    )
    db.commit()


def history(db: Session, biz_type: str, biz_id: int) -> list[dict]:
    rows = (
        db.query(ApprovalEvent)
        .filter(ApprovalEvent.biz_type == biz_type, ApprovalEvent.biz_id == biz_id)
        .order_by(ApprovalEvent.id)
        .all()
    )
    return [
        {
            "id": row.id,
            "step": row.step,
            "action": row.action,
            "actor": row.actor,
            "note": row.note,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def _configured_steps(db: Session, biz_type: str) -> list[tuple[int, str, int]]:
    rows = (
        db.query(ApprovalFlowStep)
        .filter(
            ApprovalFlowStep.biz_type == biz_type,
            ApprovalFlowStep.active.is_(True),
        )
        .order_by(ApprovalFlowStep.step_no)
        .all()
    )
    return [(row.step_no, row.role_required, row.due_hours or 24) for row in rows]


def ensure_request(
    db: Session,
    biz_type: str,
    biz_id: int,
    title: str,
    role_required: str = "pharmacist",
    applicant: str = "",
    steps_override: list[tuple[str, int]] | None = None,
) -> ApprovalRequest:
    existing = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.biz_type == biz_type,
            ApprovalRequest.biz_id == biz_id,
        )
        .first()
    )
    if existing:
        return existing
    configured = _configured_steps(db, biz_type)
    if configured:
        steps = configured
    elif steps_override:
        steps = [(index, role, hours) for index, (role, hours) in enumerate(steps_override, start=1)]
    else:
        steps = [(1, role_required, 24)]
    now = datetime.now()
    request = ApprovalRequest(
        biz_type=biz_type,
        biz_id=biz_id,
        title=title,
        status="pending",
        current_step=steps[0][0],
        applicant=applicant,
        due_at=now + timedelta(hours=steps[0][2]),
    )
    db.add(request)
    db.flush()
    for step_no, role, hours in steps:
        db.add(
            ApprovalStep(
                request_id=request.id,
                step_no=step_no,
                role_required=role,
                status="pending",
                due_at=now + timedelta(hours=hours),
            )
        )
    db.flush()
    from app.modules.notify.service import notify_role

    notify_role(
        db,
        steps[0][1],
        f"待审批：{title}",
        f"{applicant or '系统'} 提交，当前步骤 {steps[0][0]}。",
        biz_type=biz_type,
        biz_id=biz_id,
        template_code="approval_pending",
        template_vars={"title": title, "applicant": applicant or "系统", "step": steps[0][0]},
    )
    return request


def set_flow(db: Session, biz_type: str, steps: list[dict]) -> list[ApprovalFlowStep]:
    db.query(ApprovalFlowStep).filter(ApprovalFlowStep.biz_type == biz_type).delete()
    rows = []
    for index, item in enumerate(steps, start=1):
        row = ApprovalFlowStep(
            biz_type=biz_type,
            step_no=index,
            role_required=item["role_required"],
            due_hours=int(item.get("due_hours") or 24),
            active=bool(item.get("active", True)),
        )
        db.add(row)
        rows.append(row)
    db.commit()
    return rows


def get_flow(db: Session, biz_type: str) -> list[dict]:
    rows = (
        db.query(ApprovalFlowStep)
        .filter(ApprovalFlowStep.biz_type == biz_type)
        .order_by(ApprovalFlowStep.step_no)
        .all()
    )
    return [
        {
            "step_no": row.step_no,
            "role_required": row.role_required,
            "due_hours": row.due_hours,
            "active": row.active,
        }
        for row in rows
    ]


def _current_step(db: Session, request: ApprovalRequest) -> ApprovalStep | None:
    return (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.request_id == request.id,
            ApprovalStep.step_no == request.current_step,
        )
        .first()
    )


def advance_request(
    db: Session,
    biz_type: str,
    biz_id: int,
    action: str,
    actor: str,
    note: str = "",
    target_role: str = "",
    assignee: str = "",
) -> str:
    """推进审批步骤，返回 pending / approved / rejected / cancelled / transferred / missing。"""
    request = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.biz_type == biz_type,
            ApprovalRequest.biz_id == biz_id,
        )
        .first()
    )
    if not request:
        return "missing"
    if request.status != "pending":
        return request.status
    step = _current_step(db, request)
    if not step:
        return "missing"

    if action == "withdraw":
        request.status = "cancelled"
        request.updated_at = datetime.now()
        step.status = "cancelled"
        step.approver = actor
        step.note = note or "申请人撤回"
        step.acted_at = datetime.now()
        db.flush()
        return "cancelled"

    if action == "transfer":
        step.role_required = target_role or step.role_required
        step.assignee = assignee or ""
        step.note = note or ""
        step.due_at = datetime.now() + timedelta(hours=24)
        request.due_at = step.due_at
        request.updated_at = datetime.now()
        db.flush()
        from app.modules.notify.service import notify_role

        notify_role(
            db,
            step.role_required,
            f"转交审批：{request.title}",
            f"{actor} 转交给 {step.assignee or step.role_required}。{note or ''}",
            biz_type=biz_type,
            biz_id=biz_id,
            template_code="approval_transfer",
            template_vars={"title": request.title, "actor": actor, "target": step.assignee or step.role_required, "note": note or ""},
        )
        return "transferred"

    if action == "reject":
        step.status = "rejected"
        step.approver = actor
        step.note = note or ""
        step.acted_at = datetime.now()
        request.status = "rejected"
        request.updated_at = datetime.now()
        db.flush()
        if request.applicant:
            from app.modules.notify.service import enqueue

            enqueue(
                db,
                recipient=request.applicant,
                title=f"审批驳回：{request.title}",
                body=note or "审批被驳回",
                biz_type=biz_type,
                biz_id=biz_id,
                template_code="approval_result",
                template_vars={"title": request.title, "result": "审批驳回", "note": note or "审批被驳回"},
            )
        return "rejected"

    if action != "approve":
        raise ValueError("不支持的审批动作")

    step.status = "approved"
    step.approver = actor
    step.note = note or ""
    step.acted_at = datetime.now()
    next_step = (
        db.query(ApprovalStep)
        .filter(
            ApprovalStep.request_id == request.id,
            ApprovalStep.step_no > request.current_step,
            ApprovalStep.status == "pending",
        )
        .order_by(ApprovalStep.step_no)
        .first()
    )
    if next_step:
        request.current_step = next_step.step_no
        request.due_at = next_step.due_at
        request.updated_at = datetime.now()
        db.flush()
        from app.modules.notify.service import notify_role

        notify_role(
            db,
            next_step.role_required,
            f"待审批：{request.title}",
            f"上一环节 {actor} 已通过，进入第 {next_step.step_no} 步。",
            biz_type=biz_type,
            biz_id=biz_id,
            template_code="approval_pending",
            template_vars={"title": request.title, "applicant": actor, "step": next_step.step_no},
        )
        return "pending"
    request.status = "approved"
    request.updated_at = datetime.now()
    db.flush()
    if request.applicant:
        from app.modules.notify.service import enqueue

        enqueue(
            db,
            recipient=request.applicant,
            title=f"审批通过：{request.title}",
            body=note or "审批已通过",
            biz_type=biz_type,
            biz_id=biz_id,
            template_code="approval_result",
            template_vars={"title": request.title, "result": "审批通过", "note": note or "审批已通过"},
        )
    return "approved"


def overdue(db: Session) -> list[dict]:
    rows = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.status == "pending",
            ApprovalRequest.due_at.isnot(None),
            ApprovalRequest.due_at < datetime.now(),
        )
        .order_by(ApprovalRequest.due_at)
        .all()
    )
    result = []
    for request in rows:
        step = _current_step(db, request)
        result.append(
            {
                "id": request.id,
                "biz_type": request.biz_type,
                "biz_id": request.biz_id,
                "title": request.title,
                "due_at": request.due_at,
                "role_required": step.role_required if step else "",
            }
        )
    return result


def escalate_due(db: Session, actor: str) -> int:
    rows = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.status == "pending",
            ApprovalRequest.due_at.isnot(None),
            ApprovalRequest.due_at < datetime.now(),
        )
        .all()
    )
    for request in rows:
        step = _current_step(db, request)
        if not step:
            continue
        step.role_required = "director"
        step.assignee = ""
        step.due_at = datetime.now() + timedelta(hours=24)
        request.due_at = step.due_at
        request.updated_at = datetime.now()
        db.add(
            ApprovalEvent(
                biz_type=request.biz_type,
                biz_id=request.biz_id,
                step=f"step_{request.current_step}",
                action="escalate",
                actor=actor,
                note="超时升级至院长",
            )
        )
        from app.modules.notify.service import notify_role

        notify_role(
            db,
            "director",
            f"审批超时升级：{request.title}",
            f"已超过审批时限，升级至院长处理。",
            biz_type=request.biz_type,
            biz_id=request.biz_id,
            template_code="approval_escalate",
            template_vars={"title": request.title},
        )
    db.commit()
    return len(rows)



def act_request(
    db: Session,
    biz_type: str,
    biz_id: int,
    action: str,
    actor: str,
    note: str = "",
) -> str:
    result = advance_request(db, biz_type, biz_id, action, actor, note)
    db.flush()
    return result



def get_request(db: Session, biz_type: str, biz_id: int) -> dict | None:
    request = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.biz_type == biz_type,
            ApprovalRequest.biz_id == biz_id,
        )
        .first()
    )
    if not request:
        return None
    steps = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.request_id == request.id)
        .order_by(ApprovalStep.step_no)
        .all()
    )
    return {
        "id": request.id,
        "biz_type": request.biz_type,
        "biz_id": request.biz_id,
        "title": request.title,
        "status": request.status,
        "current_step": request.current_step,
        "applicant": request.applicant,
        "due_at": request.due_at,
        "created_at": request.created_at,
        "steps": [
            {
                "step_no": row.step_no,
                "role_required": row.role_required,
                "status": row.status,
                "approver": row.approver,
                "assignee": row.assignee,
                "note": row.note,
                "due_at": row.due_at,
                "acted_at": row.acted_at,
            }
            for row in steps
        ],
    }


def apply_business_result(
    db: Session,
    biz_type: str,
    biz_id: int,
    result: str,
    actor: str,
    note: str = "",
) -> None:
    """审批引擎最终结果回写业务表；未完成步骤不动业务状态。"""
    if result not in ("approved", "rejected"):
        return
    if biz_type == "purchase_request":
        from app.modules.warehouse.models import PurchaseRequest

        row = db.get(PurchaseRequest, biz_id)
        if row and row.status == "submitted":
            row.status = result
            row.approver = actor
            row.approved_at = datetime.now()
            if result == "rejected":
                row.rejected_reason = note
    elif biz_type == "archive_destruction":
        from app.modules.archive.models import ArchiveDestructionRequest

        row = db.get(ArchiveDestructionRequest, biz_id)
        if row and row.status == "pending":
            row.status = result
            row.approver = actor
            row.approved_at = datetime.now()
            row.approval_note = note
    elif biz_type == "salary_request":
        from app.modules.hr.models import SalaryRequest

        row = db.get(SalaryRequest, biz_id)
        if row and row.status == "pending":
            row.status = result
            row.reviewed_by = actor
            row.reviewed_at = datetime.now()
            row.review_note = note
    db.flush()
