from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from html import escape
from pathlib import Path
import uuid

from app.database import get_db
from app.modules.auth.security import require_role

from .schemas import (
    ArchiveCompleteRequest,
    ArchiveRecordCreate,
    ArchiveRecordResponse,
    BorrowCreate,
    BorrowResponse,
    CopyCompleteRequest,
    CopyCreate,
    CopyResponse,
    DestroyCreate,
    DestructionDecision,
    DestructionExecute,
    DestructionRequestCreate,
    DestructionRequestResponse,
    SealCreate,
    SealResponse,
)
from .service import (
    archive_record,
    borrow_record,
    complete_copy,
    create_copy,
    create_destruction_request,
    create_record,
    decide_destruction_request,
    destroy_record,
    execute_destruction_request,
    get_record,
    history,
    list_destruction_requests,
    list_records,
    return_borrowing,
    seal_record,
    unseal_record,
)

router = APIRouter(prefix="/archive", tags=["archive"])
DESTRUCTION_DIR = Path("data/archive_destructions")


@router.post("/records", response_model=ArchiveRecordResponse, status_code=201)
def new_record(
    data: ArchiveRecordCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return create_record(db, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/records", response_model=list[ArchiveRecordResponse])
def records(
    archive_no: str | None = None,
    patient_id: int | None = None,
    status: str | None = None,
    record_type: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive", "doctor")),
):
    return list_records(db, archive_no, patient_id, status, record_type)


@router.get("/records/{record_id}", response_model=ArchiveRecordResponse)
def record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive", "doctor")),
):
    record = get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="病案不存在")
    return record


@router.get("/records/{record_id}/history")
def record_history(
    record_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive")),
):
    try:
        return history(db, record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/records/{record_id}/archive", response_model=ArchiveRecordResponse)
def archive(
    record_id: int,
    data: ArchiveCompleteRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return archive_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/borrow", response_model=BorrowResponse, status_code=201)
def borrow(
    record_id: int,
    data: BorrowCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return borrow_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/borrowings/{borrowing_id}/return", response_model=BorrowResponse)
def do_return(
    borrowing_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return return_borrowing(db, borrowing_id, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/copy", response_model=CopyResponse, status_code=201)
def copy(
    record_id: int,
    data: CopyCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive")),
):
    try:
        return create_copy(db, record_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/copies/{copy_id}/complete", response_model=CopyResponse)
def copy_complete(
    copy_id: int,
    data: CopyCompleteRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return complete_copy(db, copy_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/seal", response_model=SealResponse, status_code=201)
def seal(
    record_id: int,
    data: SealCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return seal_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/unseal", response_model=SealResponse, status_code=201)
def unseal(
    record_id: int,
    data: SealCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return unseal_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/records/{record_id}/destroy")
def destroy(
    record_id: int,
    data: DestroyCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        row = destroy_record(db, record_id, data, user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": row.id, "record_id": row.record_id, "destroyed_at": row.destroyed_at}


@router.post(
    "/records/{record_id}/destruction-requests",
    response_model=DestructionRequestResponse,
    status_code=201,
)
def request_destruction(
    record_id: int,
    data: DestructionRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return create_destruction_request(db, record_id, data, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/destruction-requests", response_model=list[DestructionRequestResponse]
)
def destruction_requests(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive", "director", "admin")),
):
    return list_destruction_requests(db, status)


@router.post(
    "/destruction-requests/{request_id}/approve",
    response_model=DestructionRequestResponse,
)
def approve_destruction(
    request_id: int,
    data: DestructionDecision,
    db: Session = Depends(get_db),
    user=Depends(require_role("director")),
):
    try:
        return decide_destruction_request(db, request_id, True, data, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/destruction-requests/{request_id}/reject",
    response_model=DestructionRequestResponse,
)
def reject_destruction(
    request_id: int,
    data: DestructionDecision,
    db: Session = Depends(get_db),
    user=Depends(require_role("director")),
):
    try:
        return decide_destruction_request(db, request_id, False, data, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/destruction-requests/{request_id}/execute",
    response_model=DestructionRequestResponse,
)
def execute_destruction(
    request_id: int,
    data: DestructionExecute,
    db: Session = Depends(get_db),
    user=Depends(require_role("archive")),
):
    try:
        return execute_destruction_request(db, request_id, data, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/destruction-requests/{request_id}/attachment",
    response_model=DestructionRequestResponse,
)
async def upload_destruction_attachment(
    request_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_role("archive")),
):
    from .models import ArchiveDestructionRequest

    row = db.get(ArchiveDestructionRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="销毁申请不存在")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="仅支持 PDF/JPG/PNG 附件")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="附件不能超过 10MB")
    DESTRUCTION_DIR.mkdir(parents=True, exist_ok=True)
    path = DESTRUCTION_DIR / f"destroy_{request_id}_{uuid.uuid4().hex}{suffix}"
    path.write_bytes(content)
    row.attachment_path = str(path).replace("\\", "/")
    row.attachment_name = file.filename or path.name
    db.commit()
    db.refresh(row)
    return row


@router.get("/destruction-requests/{request_id}/attachment")
def download_destruction_attachment(
    request_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive", "director", "admin")),
):
    from .models import ArchiveDestructionRequest

    row = db.get(ArchiveDestructionRequest, request_id)
    if not row or not row.attachment_path:
        raise HTTPException(status_code=404, detail="没有附件")
    path = Path(row.attachment_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="附件文件不存在")
    return FileResponse(path, filename=row.attachment_name or path.name)


@router.get("/destruction-requests/{request_id}/print", response_class=HTMLResponse)
def print_destruction_list(
    request_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("archive", "director", "admin")),
):
    from .models import ArchiveDestructionRequest

    row = db.get(ArchiveDestructionRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="销毁申请不存在")
    print_btn = '<button onclick="window.print()" style="padding:8px 16px">打印</button>'
    return HTMLResponse(f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>病案销毁清册</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;max-width:760px;margin:32px auto;color:#111}}
h2{{text-align:center}}table{{width:100%;border-collapse:collapse;margin:18px 0}}
td,th{{border:1px solid #999;padding:8px;text-align:left}}
.small{{color:#555;font-size:13px}}@media print{{button{{display:none}}}}
</style></head><body>
{print_btn}
<h2>病案销毁清册</h2>
<table>
<tr><th>销毁申请号</th><td>{row.id}</td></tr>
<tr><th>病案号</th><td>{escape(row.archive_no or "—")}</td></tr>
<tr><th>患者</th><td>{escape(row.patient_name or "—")}</td></tr>
<tr><th>销毁原因</th><td>{escape(row.reason)}</td></tr>
<tr><th>备注</th><td>{escape(row.note or "—")}</td></tr>
<tr><th>申请人</th><td>{escape(row.requested_by or "—")}</td></tr>
<tr><th>申请时间</th><td>{row.requested_at:%Y-%m-%d %H:%M}</td></tr>
<tr><th>审批人</th><td>{escape(row.approver or "—")}</td></tr>
<tr><th>审批意见</th><td>{escape(row.approval_note or "—")}</td></tr>
<tr><th>审批时间</th><td>{row.approved_at.strftime("%Y-%m-%d %H:%M") if row.approved_at else "—"}</td></tr>
<tr><th>执行人</th><td>{escape(row.executed_by or "—")}</td></tr>
<tr><th>见证人</th><td>{escape(row.witness or "—")}</td></tr>
<tr><th>执行时间</th><td>{row.executed_at.strftime("%Y-%m-%d %H:%M") if row.executed_at else "—"}</td></tr>
<tr><th>附件</th><td>{escape(row.attachment_name or "无")}</td></tr>
<tr><th>状态</th><td>{escape(row.status)}</td></tr>
</table>
<p class="small">本清册由 HIS 生成。纸质病案销毁需双人现场核对并签字。</p>
</body></html>""")
