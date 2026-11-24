from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.security import require_read_login, require_role

from .service import (
    advance_request,
    escalate_due,
    get_flow,
    get_request,
    history,
    inbox,
    overdue,
    record_event,
    set_flow,
    summary,
)


class FlowStepIn(BaseModel):
    role_required: str = Field(pattern="^(pharmacist|warehouse|director|hr|admin)$")
    due_hours: int = Field(default=24, ge=1, le=720)
    active: bool = True


class FlowIn(BaseModel):
    steps: list[FlowStepIn] = Field(min_length=1, max_length=8)


class ApprovalAction(BaseModel):
    biz_type: str
    biz_id: int
    action: str = Field(pattern="^(approve|reject|transfer|withdraw)$")
    note: str = Field(default="", max_length=300)
    target_role: str = Field(default="", pattern="^(|pharmacist|warehouse|director|hr|admin)$")
    assignee: str = Field(default="", max_length=50)

router = APIRouter(prefix="/approvals", tags=["approvals"], dependencies=[Depends(require_read_login)])


@router.get("/inbox")
def get_inbox(
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse", "director", "hr", "admin")),
):
    return inbox(db, user.role)


@router.get("/history/{biz_type}/{biz_id}")
def approval_history(
    biz_type: str,
    biz_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse", "director", "hr", "admin")),
):
    return history(db, biz_type, biz_id)


@router.get("/requests/{biz_type}/{biz_id}")
def approval_request(
    biz_type: str,
    biz_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("pharmacist", "warehouse", "director", "hr", "admin")),
):
    return get_request(db, biz_type, biz_id)


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse", "director", "hr", "admin")),
):
    return summary(db, user.role)


@router.get("/flows/{biz_type}")
def get_approval_flow(
    biz_type: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    rows = get_flow(db, biz_type)
    if not rows:
        default_role = {
            "prescription": "pharmacist",
            "catalog_proposal": "pharmacist",
            "purchase_request": "director",
            "archive_destruction": "director",
            "salary_request": "admin",
        }.get(biz_type, "admin")
        return [{"step_no": 1, "role_required": default_role, "due_hours": 24, "active": True}]
    return rows


@router.put("/flows/{biz_type}")
def put_approval_flow(
    biz_type: str,
    data: FlowIn,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    if biz_type == "prescription" and data.steps[0].role_required != "pharmacist":
        raise HTTPException(status_code=400, detail="处方审批第一步必须是药师")
    set_flow(
        db,
        biz_type,
        [step.model_dump() for step in data.steps],
    )
    return get_flow(db, biz_type)


@router.post("/requests/action")
def approval_action(
    data: ApprovalAction,
    db: Session = Depends(get_db),
    user=Depends(require_role("pharmacist", "warehouse", "director", "hr", "admin")),
):
    request = get_request(db, data.biz_type, data.biz_id)
    if not request:
        raise HTTPException(status_code=404, detail="审批请求不存在")
    if data.action == "withdraw":
        if user.role != "admin" and user.username != request.get("applicant"):
            raise HTTPException(status_code=403, detail="只有申请人可以撤回")
    else:
        step = next(
            (
                row
                for row in request["steps"]
                if row["step_no"] == request["current_step"]
            ),
            None,
        )
        if user.role != "admin" and step:
            if step["role_required"] != user.role:
                raise HTTPException(status_code=403, detail="当前步骤无审批权限")
            if step.get("assignee") and step["assignee"] != user.username:
                raise HTTPException(status_code=403, detail="该审批已指派给其他人员")
    try:
        result = advance_request(
            db,
            data.biz_type,
            data.biz_id,
            data.action,
            user.username,
            data.note,
            data.target_role,
            data.assignee,
        )
        if result == "cancelled" and data.biz_type == "prescription":
            from app.modules.encounter.models import Prescription
            from app.modules.encounter.service import finalize_prescription_approval

            row = db.get(Prescription, data.biz_id)
            if row:
                finalize_prescription_approval(db, row, False, user.username, "申请人撤回")
                row.status = "cancelled"
                db.commit()
        if result in ("approved", "rejected") and data.biz_type in (
            "purchase_request",
            "archive_destruction",
            "salary_request",
        ):
            from app.modules.approval.service import apply_business_result

            apply_business_result(
                db, data.biz_type, data.biz_id, result, user.username, data.note
            )
            db.commit()
        if result in ("approved", "rejected") and data.biz_type == "prescription":
            from app.modules.encounter.models import Prescription
            from app.modules.encounter.service import finalize_prescription_approval

            row = db.get(Prescription, data.biz_id)
            if row:
                finalize_prescription_approval(
                    db,
                    row,
                    result == "approved",
                    user.username,
                    data.note,
                )
                record_event(
                    db,
                    "prescription",
                    row.id,
                    "approve" if result == "approved" else "reject",
                    user.username,
                    data.note,
                    step=f"step_{request['current_step']}",
                )
        elif result in ("transferred", "withdrawn", "cancelled"):
            record_event(
                db,
                data.biz_type,
                data.biz_id,
                result,
                user.username,
                data.note,
                step=f"step_{request['current_step']}",
            )
        # 统一提交：通用 action 路径此前只 flush，catalog 等业务会随会话关闭回滚
        db.commit()
        return {"result": result, "request": get_request(db, data.biz_type, data.biz_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/overdue")
def overdue_requests(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "director")),
):
    return overdue(db)


@router.post("/escalate-due")
def escalate_overdue(
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "director")),
):
    return {"escalated": escalate_due(db, user.username)}
