from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.settings import ADMIN_TEMPLATES_DIR
from app.modules.auth.schemas import UserCreate
from app.modules.labels import zh
from app.modules.materials.service import get_item as get_material_item
from app.modules.materials.service import list_items as list_material_items
from app.modules.materials.service import list_stocks as list_material_stocks
from app.modules.auth.service import (
    ROLES,
    create_user,
    get_user_by_username,
    list_audit_logs,
    list_users,
    list_recent_audit_logs,
    verify_password,
)
from app.modules.charges.schemas import ChargeItemCreate
from app.modules.charges.service import create_item as create_charge_item
from app.modules.charges.service import list_items as list_charge_items
from app.modules.drug.schemas import DrugCreate
from app.modules.drug.service import create_drug, list_drugs
from app.modules.insurance_catalog.schemas import CatalogSyncRequest
from app.modules.insurance_catalog.service import (
    import_bytes as catalog_import_bytes,
    list_matches as catalog_matches,
    list_versions as catalog_versions,
    match_all as catalog_match_all,
    search as catalog_search,
    sync_from_url as catalog_sync,
)
from app.modules.receiving.schemas import InboundCheckRequest
from app.modules.receiving.service import (
    cancel_order as inbound_cancel,
    check_order as inbound_check,
    get_order as get_inbound_order,
    list_orders as list_inbound_orders,
    stock_order as inbound_stock,
)
from app.modules.reports.service import department_revenue
from app.modules.review.service import summary as review_summary
from app.modules.stock_ledger.service import list_movements as list_stock_movements
from app.modules.traceability.service import (
    list_codes as list_trace_codes,
    summary as trace_summary,
)
from app.modules.linen.schemas import (
    CurtainCreate,
    DistributionCreate,
    LinenBatchCreate,
    RecallCreate,
)
from app.modules.linen.service import (
    create_batch as create_linen_batch,
    create_curtain,
    curtain_reminders,
    distribute as distribute_linen,
    list_batches as list_linen_batches,
    list_curtains,
    recall as recall_linen,
    summary as linen_summary,
)
from app.modules.cssd.schemas import (
    BatchCreate as CssdBatchCreate,
    IssueRequest,
    PackageCreate,
    PackageRecallRequest,
    RejectRequest,
    ReleaseRequest,
    SetCreate,
    UseRequest,
)
from app.modules.cssd.service import (
    create_batch as create_cssd_batch,
    create_package,
    create_set,
    expiry_alerts as cssd_expiry_alerts,
    issue_package,
    list_batches as list_cssd_batches,
    list_packages,
    list_sets,
    recall_package,
    reject_batch,
    release_batch,
    use_package,
)
from app.modules.lis.schemas import LabItemCreate
from app.modules.lis.service import (
    create_item as create_lab_item,
    list_items as list_lab_items,
)
from app.modules.archive.schemas import (
    ArchiveCompleteRequest,
    ArchiveRecordCreate,
    BorrowCreate,
    CopyCompleteRequest,
    CopyCreate,
    DestroyCreate,
    SealCreate,
)
from app.modules.archive.service import (
    archive_record,
    borrow_record,
    complete_copy,
    create_copy,
    create_record as create_archive_record,
    destroy_record,
    history as archive_history,
    list_records as list_archive_records,
    return_borrowing,
    seal_record,
    unseal_record,
)
from app.modules.archive.models import ArchiveCopyRequest
from app.modules.archive.service import get_record as get_archive_record
from app.modules.warehouse.schemas import (
    PurchaseOrderRequest,
    PurchaseReceiveItem,
    PurchaseReceiveRequest,
    PurchaseRejectRequest,
)
from app.modules.warehouse.service import (
    approve_purchase_request,
    get_purchase_request,
    list_purchase_requests,
    order_purchase_request,
    receive_purchase_request,
    reject_purchase_request,
)
from app.modules.supplier.service import list_suppliers
from app.modules.tcm.schemas import HerbCreate
from app.modules.tcm.service import (
    create_herb,
    list_herbs,
)
from app.modules.insurance.workbench import workbench as insurance_workbench
from app.modules.bi.executive import executive as executive_dashboard
from app.modules.treatment_room.service import (
    list_followups as treatment_followups,
    list_templates as treatment_templates,
    reconciliation as treatment_reconciliation,
    report as treatment_report,
    set_template_config,
)
from app.modules.treatment_room.schemas import TemplateConfigUpdate
from app.modules.charges.service import list_items as list_charge_items
from app.modules.materials.service import list_items as list_materials
from app.modules.cashier.service import daily as cashier_daily
from app.modules.gsp.schemas import (
    AcceptanceCreate,
    AcceptanceItemCreate,
    AdverseCreate,
    PersonnelCreate,
    RecallCreate,
    StorageLogCreate,
)
from app.modules.gsp.service import (
    alerts as gsp_alerts,
    complete_recall,
    create_acceptance,
    create_adverse,
    create_personnel,
    create_recall,
    create_storage_log,
    list_acceptances,
    list_adverse,
    list_personnel,
    list_recalls,
    list_storage_logs,
)
from app.modules.insurance_inventory.service import (
    create_upload as insurance_inventory_upload,
    get_upload as get_insurance_inventory_upload,
    list_uploads as list_insurance_inventory_uploads,
    preview as insurance_inventory_preview,
)
from app.modules.insurance_inventory.interface_service import (
    get_config as get_insurance_interface,
    is_configured as insurance_interface_configured,
    masked as mask_secret,
    save_config as save_insurance_interface,
)
from app.modules.insurance_materials.service import (
    import_bytes as material_catalog_import,
    search as material_catalog_search,
)
from app.modules.payment_gateway.service import (
    channel_rows as payment_channel_rows,
    save_config as save_payment_channel,
)
from app.modules.staff.schemas import DepartmentCreate, DoctorCreate
from app.modules.staff.service import (
    create_department,
    create_doctor,
    list_departments,
    list_doctors,
)
from app.modules.warehouse.service import (
    approve_outbound as warehouse_approve,
    cancel_outbound as warehouse_cancel,
    expiry_alerts as warehouse_expiry_alerts,
    get_outbound as get_warehouse_outbound,
    issue_outbound as warehouse_issue,
    list_adjustments as list_stock_adjustments,
    list_outbounds as list_warehouse_outbounds,
    list_stocks as list_warehouse_stocks,
)

from .service import dashboard_stats

router = APIRouter(prefix="/admin", tags=["admin-console"])

templates = Jinja2Templates(directory=str(ADMIN_TEMPLATES_DIR))
templates.env.globals["roles"] = sorted(ROLES)
templates.env.globals["today"] = lambda: date.today().isoformat()
templates.env.filters["zh"] = lambda value, group: zh(group, value)


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    """管理台页面守卫：会话存在且账号仍是管理员，否则回登录页。"""
    username = request.session.get("admin_user")
    if not username:
        return RedirectResponse("/admin/login", status_code=302)
    user = get_user_by_username(db, username)
    if not user or user.role != "admin":
        request.session.clear()
        return RedirectResponse("/admin/login", status_code=302)
    return None


def _ctx(request: Request, **kwargs) -> dict:
    return {
        "request": request,
        "admin_name": request.session.get("admin_name") or request.session.get("admin_user"),
        **kwargs,
    }


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("admin_user"):
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user_by_username(db, username)
    if not user or not verify_password(user, password) or user.role != "admin":
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "账号或密码错误，或该账号不是管理员"},
            status_code=400,
        )
    request.session["admin_user"] = user.username
    request.session["admin_name"] = user.display_name or user.username
    return RedirectResponse("/admin", status_code=302)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _ctx(
            request,
            stats=dashboard_stats(db),
            recent_logs=list_recent_audit_logs(db, 5),
        ),
    )


@router.get("/master/departments", response_class=HTMLResponse)
def departments_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "departments.html", _ctx(request, departments=list_departments(db))
    )


@router.post("/master/departments", response_class=HTMLResponse)
def departments_create(
    request: Request, name: str = Form(...), db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    create_department(db, DepartmentCreate(name=name.strip()))
    return RedirectResponse("/admin/master/departments?ok=1", status_code=302)


@router.get("/master/doctors", response_class=HTMLResponse)
def doctors_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "doctors.html",
        _ctx(
            request,
            doctors=list_doctors(db),
            departments=list_departments(db),
        ),
    )


@router.post("/master/doctors", response_class=HTMLResponse)
def doctors_create(
    request: Request,
    name: str = Form(...),
    department_id: int = Form(...),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        create_doctor(db, DoctorCreate(name=name.strip(), department_id=department_id))
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "doctors.html",
            _ctx(
                request,
                doctors=list_doctors(db),
                departments=list_departments(db),
                error=str(e),
            ),
            status_code=400,
        )
    return RedirectResponse("/admin/master/doctors?ok=1", status_code=302)


@router.get("/master/drugs", response_class=HTMLResponse)
def drugs_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "drugs.html", _ctx(request, drugs=list_drugs(db))
    )


@router.post("/master/drugs", response_class=HTMLResponse)
def drugs_create(
    request: Request,
    name: str = Form(...),
    spec: str = Form(""),
    unit: str = Form(""),
    base_price: float = Form(...),
    insurance_ratio: float = Form(0.7),
    antibiotic_level: int = Form(0),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        create_drug(
            db,
            DrugCreate(
                name=name.strip(),
                spec=spec.strip(),
                unit=unit.strip(),
                base_price=base_price,
                insurance_ratio=insurance_ratio,
                antibiotic_level=antibiotic_level,
            ),
        )
    except (ValueError, IntegrityError) as e:
        return templates.TemplateResponse(
            request,
            "drugs.html",
            _ctx(request, drugs=list_drugs(db), error=str(e)),
            status_code=400,
        )
    return RedirectResponse("/admin/master/drugs?ok=1", status_code=302)


@router.get("/master/charge-items", response_class=HTMLResponse)
def charge_items_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "charge_items.html", _ctx(request, items=list_charge_items(db))
    )


@router.post("/master/charge-items", response_class=HTMLResponse)
def charge_items_create(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    category: str = Form("other"),
    price: float = Form(...),
    insurance_ratio: float = Form(0.7),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        create_charge_item(
            db,
            ChargeItemCreate(
                code=code.strip(),
                name=name.strip(),
                category=category,
                price=price,
                insurance_ratio=insurance_ratio,
            ),
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "charge_items.html",
            _ctx(request, items=list_charge_items(db), error=str(e)),
            status_code=400,
        )
    return RedirectResponse("/admin/master/charge-items?ok=1", status_code=302)


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "users.html", _ctx(request, users=list_users(db))
    )


@router.post("/users", response_class=HTMLResponse)
def users_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    display_name: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        create_user(
            db,
            UserCreate(
                username=username.strip(),
                password=password,
                role=role,
                display_name=display_name.strip(),
            ),
        )
    except (ValueError, IntegrityError) as e:
        return templates.TemplateResponse(
            request,
            "users.html",
            _ctx(request, users=list_users(db), error=str(e)),
            status_code=400,
        )
    return RedirectResponse("/admin/users?ok=1", status_code=302)


@router.get("/audit", response_class=HTMLResponse)
def audit_page(
    request: Request, username: str | None = None, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "audit.html",
        _ctx(request, logs=list_audit_logs(db, username, 100), username=username or ""),
    )


@router.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "reports.html",
        _ctx(
            request,
            revenue=department_revenue(db, start_date, end_date),
            review=review_summary(db, start_date, end_date),
            start_date=start_date.isoformat() if start_date else "",
            end_date=end_date.isoformat() if end_date else "",
        ),
    )


# ---------- 入库单 ----------
@router.get("/inbound", response_class=HTMLResponse)
def inbound_page(
    request: Request, status: str | None = None, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "inbound.html",
        _ctx(
            request,
            orders=list_inbound_orders(db, status, None),
            status=status or "",
            message=request.query_params.get("msg", ""),
        ),
    )


@router.get("/inbound/{order_id}", response_class=HTMLResponse)
def inbound_detail(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    order = get_inbound_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="入库单不存在")
    return templates.TemplateResponse(
        request,
        "inbound_detail.html",
        _ctx(
            request,
            order=order,
            message=request.query_params.get("msg", ""),
        ),
    )


@router.post("/inbound/{order_id}/check")
async def inbound_check_submit(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    items = []
    for key, value in form.items():
        if not key.startswith("rejected_"):
            continue
        item_id = key.removeprefix("rejected_")
        try:
            quantity = int(value or 0)
        except ValueError:
            quantity = 0
        if quantity > 0:
            items.append(
                {
                    "item_id": int(item_id),
                    "rejected_qty": quantity,
                    "reject_reason": str(form.get(f"reason_{item_id}", "")),
                }
            )
    try:
        inbound_check(db, order_id, InboundCheckRequest(items=items), checked_by=request.session.get("admin_user", "admin"))
    except ValueError as e:
        return RedirectResponse(f"/admin/inbound/{order_id}?msg={quote(str(e))}", status_code=302)
    return RedirectResponse(f"/admin/inbound/{order_id}?msg={quote('验收完成')}", status_code=302)


@router.post("/inbound/{order_id}/stock")
def inbound_stock_submit(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        inbound_stock(db, order_id)
    except ValueError as e:
        return RedirectResponse(f"/admin/inbound/{order_id}?msg={quote(str(e))}", status_code=302)
    return RedirectResponse(f"/admin/inbound/{order_id}?msg={quote('入库完成')}", status_code=302)


@router.post("/inbound/{order_id}/cancel")
def inbound_cancel_submit(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        inbound_cancel(db, order_id)
    except ValueError as e:
        return RedirectResponse(f"/admin/inbound/{order_id}?msg={quote(str(e))}", status_code=302)
    return RedirectResponse(f"/admin/inbound/{order_id}?msg={quote('已取消')}", status_code=302)


# ---------- 医保药品目录 ----------
@router.get("/insurance-catalog", response_class=HTMLResponse)
def insurance_catalog_page(
    request: Request,
    q: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "insurance_catalog.html",
        _ctx(
            request,
            rows=catalog_search(db, q, category, 100, 0),
            versions=catalog_versions(db, 10),
            matches=catalog_matches(db),
            q=q or "",
            category=category or "",
            message=request.query_params.get("msg", ""),
        ),
    )


@router.post("/insurance-catalog/match")
def insurance_catalog_match(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    stats = catalog_match_all(db, only_unmatched=True)
    msg = (
        f"对码完成：共 {stats['total']}，匹配 {stats['matched']}，"
        f"歧义 {stats['ambiguous']}，未匹配 {stats['unmatched']}"
    )
    return RedirectResponse(
        f"/admin/insurance-catalog?msg={quote(msg)}", status_code=302
    )


@router.post("/insurance-catalog/import")
async def insurance_catalog_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    data = await file.read()
    try:
        result = catalog_import_bytes(
            db,
            data,
            file_name=file.filename or "catalog.csv",
            source="manual",
            imported_by=request.session.get("admin_user", "admin"),
        )
        msg = f"导入 {result['status']}：版本 {result.get('version')}，新增 {result['inserted']}，更新 {result['updated']}"
    except ValueError as e:
        msg = f"导入失败：{e}"
    return RedirectResponse(
        f"/admin/insurance-catalog?msg={quote(msg)}", status_code=302
    )


@router.post("/insurance-catalog/sync")
def insurance_catalog_sync(
    request: Request,
    url: str = Form(...),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        result = catalog_sync(db, CatalogSyncRequest(url=url).url, imported_by=request.session.get("admin_user", "admin"))
        msg = f"同步 {result['status']}：版本 {result.get('version')}，新增 {result['inserted']}，更新 {result['updated']}"
    except ValueError as e:
        msg = f"同步失败：{e}"
    return RedirectResponse(
        f"/admin/insurance-catalog?msg={quote(msg)}", status_code=302
    )


# ---------- 库存流水台账 ----------
@router.get("/stock-ledger", response_class=HTMLResponse)
def stock_ledger_page(
    request: Request,
    kind: str | None = None,
    warehouse: str | None = None,
    direction: str | None = None,
    ref_type: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "stock_ledger.html",
        _ctx(
            request,
            movements=list_stock_movements(
                db,
                kind=kind,
                warehouse=warehouse,
                direction=direction,
                ref_type=ref_type,
                limit=200,
            ),
            kind=kind or "",
            warehouse=warehouse or "",
            direction=direction or "",
            ref_type=ref_type or "",
            message=request.query_params.get("msg", ""),
        ),
    )


# ---------- 效期预警 ----------
@router.get("/expiry-alerts", response_class=HTMLResponse)
def expiry_alerts_page(
    request: Request, days: int = 90, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    days = min(max(days, 1), 3650)
    return templates.TemplateResponse(
        request,
        "expiry_alerts.html",
        _ctx(request, alerts=warehouse_expiry_alerts(db, days), days=days),
    )


# ---------- 追溯码 ----------
@router.get("/trace-codes", response_class=HTMLResponse)
def trace_codes_page(
    request: Request,
    trace_code: str | None = None,
    drug_id: int | None = None,
    batch_no: str | None = None,
    status: str | None = None,
    warehouse: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "trace_codes.html",
        _ctx(
            request,
            rows=list_trace_codes(
                db, trace_code, drug_id, batch_no, status, warehouse
            ),
            summary=trace_summary(db, drug_id, batch_no),
            trace_code=trace_code or "",
            drug_id=drug_id or "",
            batch_no=batch_no or "",
            status=status or "",
            warehouse=warehouse or "",
        ),
    )


# ---------- 医保进销存 ----------
@router.get("/insurance-inventory", response_class=HTMLResponse)
def insurance_inventory_page(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    today = date.today()
    start = start_date or today.replace(day=1)
    end = end_date or today
    try:
        preview = insurance_inventory_preview(db, start, end)
        error = ""
    except ValueError as e:
        preview = None
        error = str(e)
    return templates.TemplateResponse(
        request,
        "insurance_inventory.html",
        _ctx(
            request,
            preview=preview,
            error=error,
            uploads=list_insurance_inventory_uploads(db),
            start_date=start,
            end_date=end,
            message=request.query_params.get("msg", ""),
        ),
    )


@router.post("/insurance-inventory/upload")
def insurance_inventory_do_upload(
    request: Request,
    start_date: date = Form(...),
    end_date: date = Form(...),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        upload = insurance_inventory_upload(
            db, start_date, end_date,
            created_by=request.session.get("admin_user", "admin"),
        )
        msg = f"上传完成：{upload.upload_no}，{upload.record_count} 条，{upload.status}"
    except ValueError as e:
        msg = f"上传失败：{e}"
    return RedirectResponse(
        f"/admin/insurance-inventory?start_date={start_date}&end_date={end_date}&msg={quote(msg)}",
        status_code=302,
    )


@router.get("/insurance-inventory/{upload_id}", response_class=HTMLResponse)
def insurance_inventory_detail(
    request: Request, upload_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    upload = get_insurance_inventory_upload(db, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="上传记录不存在")
    return templates.TemplateResponse(
        request,
        "insurance_inventory_detail.html",
        _ctx(request, upload=upload),
    )


# ---------- 医用耗材目录 ----------
@router.get("/insurance-materials", response_class=HTMLResponse)
def insurance_materials_page(
    request: Request,
    q: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "insurance_materials.html",
        _ctx(
            request,
            rows=material_catalog_search(db, q, category, 100, 0),
            q=q or "",
            category=category or "",
            message=request.query_params.get("msg", ""),
        ),
    )


@router.post("/insurance-materials/import")
async def insurance_materials_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    data = await file.read()
    try:
        result = material_catalog_import(
            db, data, file.filename or "materials.csv",
            imported_by=request.session.get("admin_user", "admin"),
        )
        msg = (
            f"耗材目录导入完成：共 {result['total']}，"
            f"新增 {result['inserted']}，更新 {result['updated']}"
        )
    except ValueError as e:
        msg = f"导入失败：{e}"
    return RedirectResponse(
        f"/admin/insurance-materials?msg={quote(msg)}", status_code=302
    )


# ---------- 医保接口配置 ----------
@router.get("/insurance-interface", response_class=HTMLResponse)
def insurance_interface_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    config = get_insurance_interface(db)
    return templates.TemplateResponse(
        request,
        "insurance_interface.html",
        _ctx(
            request,
            config=config,
            configured=insurance_interface_configured(config),
            secret_mask=mask_secret(config.app_secret) if config else "",
            private_mask=mask_secret(config.private_key) if config else "",
            public_mask=mask_secret(config.public_key) if config else "",
            message=request.query_params.get("msg", ""),
        ),
    )


@router.post("/insurance-interface")
def insurance_interface_save(
    request: Request,
    enabled: str | None = Form(None),
    base_url: str = Form(""),
    upload_path: str = Form("/api/inventory/upload"),
    org_code: str = Form(""),
    org_name: str = Form(""),
    app_id: str = Form(""),
    app_secret: str = Form(""),
    sign_type: str = Form("NONE"),
    private_key: str = Form(""),
    public_key: str = Form(""),
    timeout: int = Form(30),
    remark: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        save_insurance_interface(
            db,
            enabled=bool(enabled),
            base_url=base_url,
            upload_path=upload_path,
            org_code=org_code,
            org_name=org_name,
            app_id=app_id,
            app_secret=app_secret,
            sign_type=sign_type,
            private_key=private_key,
            public_key=public_key,
            timeout=timeout,
            remark=remark,
            updated_by=request.session.get("admin_user", "admin"),
        )
        msg = "医保接口配置已保存（字段留空=保持原值；未配置完整时上传走 Mock）"
    except Exception as e:  # 配置保存失败不阻断页面
        msg = f"保存失败：{e}"
    return RedirectResponse(
        f"/admin/insurance-interface?msg={quote(msg)}", status_code=302
    )


# ---------- 支付通道配置 ----------
@router.get("/payment-channels", response_class=HTMLResponse)
def payment_channels_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "payment_channels.html",
        _ctx(
            request,
            rows=payment_channel_rows(db),
            message=request.query_params.get("msg", ""),
        ),
    )


@router.post("/payment-channels")
def payment_channels_save(
    request: Request,
    channel: str = Form(...),
    enabled: str | None = Form(None),
    gateway_url: str = Form(""),
    merchant_id: str = Form(""),
    app_id: str = Form(""),
    api_secret: str = Form(""),
    terminal_id: str = Form(""),
    cert_path: str = Form(""),
    remark: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        save_payment_channel(
            db,
            channel,
            enabled=bool(enabled),
            gateway_url=gateway_url,
            merchant_id=merchant_id,
            app_id=app_id,
            api_secret=api_secret,
            terminal_id=terminal_id,
            cert_path=cert_path,
            remark=remark,
            updated_by=request.session.get("admin_user", "admin"),
        )
        msg = "支付通道配置已保存（密钥留空=保持原值；未配置完整时收费走模拟）"
    except ValueError as e:
        msg = f"保存失败：{e}"
    return RedirectResponse(
        f"/admin/payment-channels?msg={quote(msg)}", status_code=302
    )


# ---------- 库房（总库 + 出库单）----------
@router.get("/warehouse", response_class=HTMLResponse)
def warehouse_page(
    request: Request, status: str | None = None, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    materials = [
        stock for stock in list_material_stocks(db) if stock.warehouse == "总库"
    ]
    return templates.TemplateResponse(
        request,
        "warehouse.html",
        _ctx(
            request,
            drug_stocks=list_warehouse_stocks(db),
            material_stocks=materials,
            outbounds=list_warehouse_outbounds(db, status, None),
            adjustments=list_stock_adjustments(db),
            status=status or "",
            message=request.query_params.get("msg", ""),
        ),
    )


@router.get("/warehouse/outbound/{order_id}", response_class=HTMLResponse)
def warehouse_outbound_detail(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    order = get_warehouse_outbound(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="出库单不存在")
    return templates.TemplateResponse(
        request,
        "warehouse_outbound.html",
        _ctx(request, order=order, message=request.query_params.get("msg", "")),
    )


@router.post("/warehouse/outbound/{order_id}/approve")
def warehouse_outbound_approve(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        warehouse_approve(db, order_id, approver=request.session.get("admin_user", "admin"))
        msg = "已审核"
    except ValueError as e:
        msg = f"审核失败：{e}"
    return RedirectResponse(
        f"/admin/warehouse/outbound/{order_id}?msg={quote(msg)}", status_code=302
    )


@router.post("/warehouse/outbound/{order_id}/issue")
async def warehouse_outbound_issue(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    items = []
    for key, value in form.items():
        if not key.startswith("qty_"):
            continue
        try:
            quantity = int(value or 0)
        except ValueError:
            quantity = 0
        if quantity > 0:
            items.append({"item_id": int(key.removeprefix("qty_")), "quantity": quantity})
    try:
        warehouse_issue(
            db,
            order_id,
            issuer=request.session.get("admin_user", "admin"),
            items=items or None,
        )
        msg = "已出库"
    except ValueError as e:
        msg = f"出库失败：{e}"
    return RedirectResponse(
        f"/admin/warehouse/outbound/{order_id}?msg={quote(msg)}", status_code=302
    )


@router.post("/warehouse/outbound/{order_id}/cancel")
def warehouse_outbound_cancel(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        warehouse_cancel(db, order_id)
        msg = "已取消"
    except ValueError as e:
        msg = f"取消失败：{e}"
    return RedirectResponse(
        f"/admin/warehouse/outbound/{order_id}?msg={quote(msg)}", status_code=302
    )



# ---------- 被服洗涤（与器械灭菌分开） ----------

def _form_float(form, key: str):
    value = form.get(key)
    return float(value) if value not in (None, "") else None


def _form_int(form, key: str):
    value = form.get(key)
    return int(value) if value not in (None, "") else None


@router.get("/linen", response_class=HTMLResponse)
def linen_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    batches = list_linen_batches(db)
    curtains = list_curtains(db)
    reminders = curtain_reminders(db, 30)
    return templates.TemplateResponse(
        request,
        "linen.html",
        _ctx(
            request,
            batches=batches,
            curtains=curtains,
            reminders=reminders,
            msg=request.query_params.get("msg", ""),
            category_labels={"bedding": "床品", "uniform": "工作服", "curtain": "窗帘/隔帘", "other": "其他织物"},
            soil_labels={"normal": "普通", "contaminated": "污染", "infectious": "感染性"},
            linen_status={"completed": "已完成", "recalled": "已召回"},
            event_labels={"remove": "拆下", "wash": "洗涤消毒", "reinstall": "安装"},
        ),
    )


@router.post("/linen/batches")
async def linen_batch_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        data = LinenBatchCreate(
            batch_no=(form.get("batch_no") or "").strip() or None,
            category=form.get("category") or "bedding",
            item_name=(form.get("item_name") or "").strip(),
            quantity=_form_int(form, "quantity") or 0,
            unit=(form.get("unit") or "件").strip(),
            source_department=(form.get("source_department") or "").strip(),
            soil_level=form.get("soil_level") or "normal",
            wash_method=form.get("wash_method") or "thermal",
            temperature=_form_float(form, "temperature"),
            duration_min=_form_int(form, "duration_min"),
            detergent=(form.get("detergent") or "").strip(),
            operator=(form.get("operator") or "").strip(),
            note=(form.get("note") or "").strip(),
        )
        batch = create_linen_batch(db, data, request.session.get("admin_user", "admin"))
        msg = f"已创建被服批次 {batch.batch_no}"
    except Exception as e:  # noqa: BLE001
        msg = f"创建失败：{e}"
    return RedirectResponse(f"/admin/linen?msg={quote(msg)}", status_code=302)


@router.post("/linen/batches/{batch_id}/distribute")
async def linen_distribute_submit(
    request: Request, batch_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        distribute_linen(
            db,
            batch_id,
            DistributionCreate(
                department=(form.get("department") or "").strip(),
                quantity=_form_int(form, "quantity") or 0,
                note=(form.get("note") or "").strip(),
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "已发放"
    except Exception as e:  # noqa: BLE001
        msg = f"发放失败：{e}"
    return RedirectResponse(f"/admin/linen?msg={quote(msg)}", status_code=302)


@router.post("/linen/batches/{batch_id}/recall")
def linen_recall_submit(
    request: Request, batch_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        recall_linen(db, batch_id, "批次召回", request.session.get("admin_user", "admin"))
        msg = "已召回"
    except Exception as e:  # noqa: BLE001
        msg = f"召回失败：{e}"
    return RedirectResponse(f"/admin/linen?msg={quote(msg)}", status_code=302)


@router.post("/linen/curtains")
async def linen_curtain_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        due = (form.get("next_due") or "").strip()
        create_curtain(
            db,
            CurtainCreate(
                department=(form.get("department") or "").strip(),
                room=(form.get("room") or "").strip(),
                curtain_no=(form.get("curtain_no") or "").strip(),
                event=form.get("event") or "wash",
                method=(form.get("method") or "").strip(),
                operator=(form.get("operator") or "").strip(),
                next_due=date.fromisoformat(due) if due else None,
                note=(form.get("note") or "").strip(),
            ),
        )
        msg = "已登记窗帘拆洗"
    except Exception as e:  # noqa: BLE001
        msg = f"登记失败：{e}"
    return RedirectResponse(f"/admin/linen?msg={quote(msg)}", status_code=302)


# ---------- 器械灭菌（CSSD） ----------

@router.get("/cssd", response_class=HTMLResponse)
def cssd_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "cssd.html",
        _ctx(
            request,
            sets=list_sets(db),
            batches=list_cssd_batches(db),
            packages=list_packages(db),
            alerts=cssd_expiry_alerts(db, 30),
            msg=request.query_params.get("msg", ""),
            method_labels={"steam": "高压蒸汽", "plasma": "低温等离子", "chemical": "化学浸泡"},
            indicator_labels={"pending": "待判定", "pass": "合格", "fail": "不合格"},
            release_labels={"pending": "待放行", "released": "已放行", "rejected": "不合格"},
            package_status={"sterilized": "已灭菌", "issued": "已发放", "used": "已使用", "recalled": "已召回"},
        ),
    )


@router.post("/cssd/sets")
async def cssd_set_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        row = create_set(
            db,
            SetCreate(
                code=(form.get("code") or "").strip(),
                name=(form.get("name") or "").strip(),
                department=(form.get("department") or "").strip(),
                note=(form.get("note") or "").strip(),
            ),
        )
        msg = f"已创建器械包 {row.code}"
    except Exception as e:  # noqa: BLE001
        msg = f"创建失败：{e}"
    return RedirectResponse(f"/admin/cssd?msg={quote(msg)}", status_code=302)


@router.post("/cssd/batches")
async def cssd_batch_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        row = create_cssd_batch(
            db,
            CssdBatchCreate(
                batch_no=(form.get("batch_no") or "").strip() or None,
                sterilizer=(form.get("sterilizer") or "").strip(),
                method=form.get("method") or "steam",
                cycle=(form.get("cycle") or "").strip(),
                temperature=_form_float(form, "temperature"),
                pressure=_form_float(form, "pressure"),
                duration_min=_form_int(form, "duration_min"),
                operator=(form.get("operator") or "").strip(),
                chemical_indicator=form.get("chemical_indicator") or "pending",
                biological_indicator=form.get("biological_indicator") or "pending",
                note=(form.get("note") or "").strip(),
            ),
        )
        msg = f"已创建灭菌批次 {row.batch_no}"
    except Exception as e:  # noqa: BLE001
        msg = f"创建失败：{e}"
    return RedirectResponse(f"/admin/cssd?msg={quote(msg)}", status_code=302)


@router.post("/cssd/batches/{batch_id}/release")
def cssd_release_submit(
    request: Request, batch_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        release_batch(db, batch_id, request.session.get("admin_user", "admin"))
        msg = "已放行"
    except Exception as e:  # noqa: BLE001
        msg = f"放行失败：{e}"
    return RedirectResponse(f"/admin/cssd?msg={quote(msg)}", status_code=302)


@router.post("/cssd/batches/{batch_id}/reject")
def cssd_reject_submit(
    request: Request, batch_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        reject_batch(db, batch_id, "监测不合格", request.session.get("admin_user", "admin"))
        msg = "已判定不合格并召回相关包"
    except Exception as e:  # noqa: BLE001
        msg = f"操作失败：{e}"
    return RedirectResponse(f"/admin/cssd?msg={quote(msg)}", status_code=302)


@router.post("/cssd/packages")
async def cssd_package_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        row = create_package(
            db,
            PackageCreate(
                package_code=(form.get("package_code") or "").strip(),
                set_id=_form_int(form, "set_id") or 0,
                batch_id=_form_int(form, "batch_id") or 0,
                expiry=date.fromisoformat((form.get("expiry") or "").strip()),
                location=(form.get("location") or "无菌间").strip(),
                note=(form.get("note") or "").strip(),
            ),
        )
        msg = f"已创建包码 {row.package_code}"
    except Exception as e:  # noqa: BLE001
        msg = f"创建失败：{e}"
    return RedirectResponse(f"/admin/cssd?msg={quote(msg)}", status_code=302)


@router.post("/cssd/packages/{package_id}/issue")
async def cssd_issue_submit(
    request: Request, package_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        issue_package(
            db,
            package_id,
            IssueRequest(department=(form.get("department") or "").strip()),
            request.session.get("admin_user", "admin"),
        )
        msg = "已发放"
    except Exception as e:  # noqa: BLE001
        msg = f"发放失败：{e}"
    return RedirectResponse(f"/admin/cssd?msg={quote(msg)}", status_code=302)


@router.post("/cssd/packages/{package_id}/use")
async def cssd_use_submit(
    request: Request, package_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        use_package(
            db,
            package_id,
            UseRequest(
                department=(form.get("department") or "").strip(),
                patient_id=_form_int(form, "patient_id"),
                encounter_id=_form_int(form, "encounter_id"),
                note=(form.get("note") or "").strip(),
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "已登记使用"
    except Exception as e:  # noqa: BLE001
        msg = f"使用登记失败：{e}"
    return RedirectResponse(f"/admin/cssd?msg={quote(msg)}", status_code=302)


@router.post("/cssd/packages/{package_id}/recall")
def cssd_recall_submit(
    request: Request, package_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        recall_package(db, package_id, "单包召回", request.session.get("admin_user", "admin"))
        msg = "已召回"
    except Exception as e:  # noqa: BLE001
        msg = f"召回失败：{e}"
    return RedirectResponse(f"/admin/cssd?msg={quote(msg)}", status_code=302)

# ---------- 检验项目字典 ----------

@router.get("/lab-items", response_class=HTMLResponse)
def lab_items_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "lab_items.html",
        _ctx(
            request,
            items=list_lab_items(db),
            msg=request.query_params.get("msg", ""),
        ),
    )


@router.post("/lab-items")
async def lab_item_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        create_lab_item(
            db,
            LabItemCreate(
                code=(form.get("code") or "").strip(),
                name=(form.get("name") or "").strip(),
                price=float(form.get("price") or 0),
                specimen_type=(form.get("specimen_type") or "血液").strip(),
                unit=(form.get("unit") or "").strip(),
                reference_low=_form_float(form, "reference_low"),
                reference_high=_form_float(form, "reference_high"),
                method=(form.get("method") or "").strip(),
                tat_minutes=_form_int(form, "tat_minutes") or 60,
                insurance_ratio=float(form.get("insurance_ratio") or 0.7),
            ),
        )
        msg = "检验项目已创建"
    except Exception as e:  # noqa: BLE001
        msg = f"创建失败：{e}"
    return RedirectResponse(f"/admin/lab-items?msg={quote(msg)}", status_code=302)

# ---------- 病案档案 ----------

@router.get("/archive", response_class=HTMLResponse)
def archive_page(
    request: Request,
    archive_no: str | None = None,
    status: str | None = None,
    patient_id: int | None = None,
    record_id: int | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    records = list_archive_records(db, archive_no, patient_id, status)
    pending_copies = (
        db.query(ArchiveCopyRequest)
        .filter(ArchiveCopyRequest.status == "pending")
        .order_by(ArchiveCopyRequest.id.desc())
        .all()
    )
    selected = get_archive_record(db, record_id) if record_id else None
    detail = archive_history(db, record_id) if record_id else None
    return templates.TemplateResponse(
        request,
        "archive.html",
        _ctx(
            request,
            records=records,
            pending_copies=pending_copies,
            selected=selected,
            detail=detail,
            msg=request.query_params.get("msg", ""),
            archive_status={
                "draft": "已建档",
                "archived": "已归档",
                "borrowed": "已借出",
                "sealed": "已封存",
                "destroyed": "已销毁",
            },
            record_types={"outpatient": "门诊", "inpatient": "住院", "emergency": "急诊"},
        ),
    )


@router.post("/archive/records")
async def archive_record_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        record = create_archive_record(
            db,
            ArchiveRecordCreate(
                patient_id=_form_int(form, "patient_id") or 0,
                encounter_id=_form_int(form, "encounter_id"),
                record_type=form.get("record_type") or "outpatient",
                note=(form.get("note") or "").strip(),
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = f"已建档 {record.archive_no}"
    except Exception as e:  # noqa: BLE001
        msg = f"建档失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)


@router.post("/archive/records/{record_id}/archive")
async def archive_record_confirm(
    request: Request, record_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        archive_record(
            db,
            record_id,
            ArchiveCompleteRequest(
                storage_location=(form.get("storage_location") or "").strip(),
                page_count=_form_int(form, "page_count") or 0,
                completeness=form.get("completeness") or "complete",
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "已归档上架"
    except Exception as e:  # noqa: BLE001
        msg = f"归档失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)


@router.post("/archive/records/{record_id}/borrow")
async def archive_borrow_submit(
    request: Request, record_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        borrow_record(
            db,
            record_id,
            BorrowCreate(
                borrower=(form.get("borrower") or "").strip(),
                department=(form.get("department") or "").strip(),
                purpose=(form.get("purpose") or "").strip(),
                due_days=_form_int(form, "due_days") or 7,
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "已借出"
    except Exception as e:  # noqa: BLE001
        msg = f"借阅失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)


@router.post("/archive/borrowings/{borrowing_id}/return")
def archive_return_submit(
    request: Request, borrowing_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        return_borrowing(db, borrowing_id, request.session.get("admin_user", "admin"))
        msg = "已归还"
    except Exception as e:  # noqa: BLE001
        msg = f"归还失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)


@router.post("/archive/records/{record_id}/copy")
async def archive_copy_submit(
    request: Request, record_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        create_copy(
            db,
            record_id,
            CopyCreate(
                applicant=(form.get("applicant") or "").strip(),
                id_number=(form.get("id_number") or "").strip(),
                relationship=(form.get("relationship") or "本人").strip(),
                purpose=(form.get("purpose") or "").strip(),
                contents=(form.get("contents") or "").strip(),
                copies=_form_int(form, "copies") or 1,
            ),
        )
        msg = "复印申请已登记"
    except Exception as e:  # noqa: BLE001
        msg = f"复印登记失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)


@router.post("/archive/copies/{copy_id}/complete")
async def archive_copy_complete(
    request: Request, copy_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        complete_copy(
            db,
            copy_id,
            CopyCompleteRequest(fee=float(form.get("fee") or 0)),
            request.session.get("admin_user", "admin"),
        )
        msg = "复印已完成"
    except Exception as e:  # noqa: BLE001
        msg = f"复印完成失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)


@router.post("/archive/records/{record_id}/seal")
async def archive_seal_submit(
    request: Request, record_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        seal_record(
            db,
            record_id,
            SealCreate(
                reason=(form.get("reason") or "").strip(),
                witness=(form.get("witness") or "").strip(),
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "已封存"
    except Exception as e:  # noqa: BLE001
        msg = f"封存失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)


@router.post("/archive/records/{record_id}/unseal")
async def archive_unseal_submit(
    request: Request, record_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        unseal_record(
            db,
            record_id,
            SealCreate(
                reason=(form.get("reason") or "").strip(),
                witness=(form.get("witness") or "").strip(),
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "已启封"
    except Exception as e:  # noqa: BLE001
        msg = f"启封失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)


@router.post("/archive/records/{record_id}/destroy")
async def archive_destroy_submit(
    request: Request, record_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        destroy_record(
            db,
            record_id,
            DestroyCreate(
                reason=(form.get("reason") or "").strip(),
                approved_by=(form.get("approved_by") or "").strip(),
                note=(form.get("note") or "").strip(),
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "已销毁"
    except Exception as e:  # noqa: BLE001
        msg = f"销毁失败：{e}"
    return RedirectResponse(f"/admin/archive?msg={quote(msg)}", status_code=302)

# ---------- 采购申请（机构审核） ----------

@router.get("/purchase-requests", response_class=HTMLResponse)
def purchase_requests_page(
    request: Request,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "purchase_requests.html",
        _ctx(
            request,
            requests=list_purchase_requests(db, status),
            suppliers=list_suppliers(db),
            msg=request.query_params.get("msg", ""),
            status_labels={
                "submitted": "待审核",
                "approved": "已批准",
                "ordered": "已下单",
                "partially_received": "部分到货",
                "received": "已入库",
                "rejected": "已驳回",
                "cancelled": "已取消",
            },
        ),
    )


@router.get("/purchase-requests/{request_id}", response_class=HTMLResponse)
def purchase_request_detail_page(
    request: Request, request_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    row = get_purchase_request(db, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="采购申请不存在")
    return templates.TemplateResponse(
        request,
        "purchase_request_detail.html",
        _ctx(
            request,
            row=row,
            suppliers=list_suppliers(db),
            msg=request.query_params.get("msg", ""),
            status_labels={
                "submitted": "待审核",
                "approved": "已批准",
                "ordered": "已下单",
                "partially_received": "部分到货",
                "received": "已入库",
                "rejected": "已驳回",
            },
        ),
    )


@router.post("/purchase-requests/{request_id}/approve")
def purchase_request_approve(
    request: Request, request_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        approve_purchase_request(
            db, request_id, request.session.get("admin_user", "admin")
        )
        msg = "已批准"
    except Exception as e:  # noqa: BLE001
        msg = f"批准失败：{e}"
    return RedirectResponse(
        f"/admin/purchase-requests/{request_id}?msg={quote(msg)}", status_code=302
    )


@router.post("/purchase-requests/{request_id}/reject")
async def purchase_request_reject(
    request: Request, request_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        reject_purchase_request(
            db,
            request_id,
            PurchaseRejectRequest(reason=(form.get("reason") or "").strip()),
            request.session.get("admin_user", "admin"),
        )
        msg = "已驳回"
    except Exception as e:  # noqa: BLE001
        msg = f"驳回失败：{e}"
    return RedirectResponse(
        f"/admin/purchase-requests/{request_id}?msg={quote(msg)}", status_code=302
    )


@router.post("/purchase-requests/{request_id}/order")
async def purchase_request_order(
    request: Request, request_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        order_purchase_request(
            db,
            request_id,
            PurchaseOrderRequest(
                supplier_id=_form_int(form, "supplier_id"),
                note=(form.get("note") or "").strip(),
            ),
        )
        msg = "已下单"
    except Exception as e:  # noqa: BLE001
        msg = f"下单失败：{e}"
    return RedirectResponse(
        f"/admin/purchase-requests/{request_id}?msg={quote(msg)}", status_code=302
    )


@router.post("/purchase-requests/{request_id}/receive")
async def purchase_request_receive(
    request: Request, request_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    row = get_purchase_request(db, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="采购申请不存在")
    form = await request.form()
    items = []
    for item in row.items:
        qty = _form_int(form, f"qty_{item.id}")
        if not qty:
            continue
        items.append(
            PurchaseReceiveItem(
                item_id=item.id,
                quantity=qty,
                batch_no=(form.get(f"batch_{item.id}") or "").strip(),
                expiry=(
                    date.fromisoformat(form.get(f"expiry_{item.id}"))
                    if form.get(f"expiry_{item.id}")
                    else None
                ),
                unit_price=_form_float(form, f"price_{item.id}"),
            )
        )
    try:
        receive_purchase_request(
            db,
            request_id,
            PurchaseReceiveRequest(
                supplier_id=_form_int(form, "supplier_id"),
                items=items,
                note=(form.get("note") or "").strip(),
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "已到货入库"
    except Exception as e:  # noqa: BLE001
        msg = f"入库失败：{e}"
    return RedirectResponse(
        f"/admin/purchase-requests/{request_id}?msg={quote(msg)}", status_code=302
    )

# ---------- 中药饮片目录 ----------

@router.get("/tcm-herbs", response_class=HTMLResponse)
def tcm_herbs_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "tcm_herbs.html",
        _ctx(
            request,
            herbs=list_herbs(db, active_only=False),
            msg=request.query_params.get("msg", ""),
        ),
    )


@router.post("/tcm-herbs")
async def tcm_herb_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        create_herb(
            db,
            HerbCreate(
                code=(form.get("code") or "").strip(),
                name=(form.get("name") or "").strip(),
                spec=(form.get("spec") or "").strip(),
                unit=(form.get("unit") or "g").strip(),
                price_per_g=float(form.get("price_per_g") or 0),
                insurance_code=(form.get("insurance_code") or "").strip(),
                toxicity=form.get("toxicity") or "none",
                note=(form.get("note") or "").strip(),
            ),
        )
        msg = "饮片已创建"
    except Exception as e:  # noqa: BLE001
        msg = f"创建失败：{e}"
    return RedirectResponse(f"/admin/tcm-herbs?msg={quote(msg)}", status_code=302)

# ---------- 医保工作台 ----------

@router.get("/insurance-workbench", response_class=HTMLResponse)
def insurance_workbench_page(
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        start, end = None, None
    data = insurance_workbench(db, start, end)
    return templates.TemplateResponse(
        request,
        "insurance_workbench.html",
        _ctx(
            request,
            data=data,
            msg=request.query_params.get("msg", ""),
            channel_labels={
                "cash": "现金",
                "wechat": "微信",
                "alipay": "支付宝",
                "pos": "POS",
                "insurance_card": "医保卡",
            },
        ),
    )

# ---------- GSP ----------

@router.get("/gsp", response_class=HTMLResponse)
def gsp_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "gsp.html",
        _ctx(
            request,
            acceptances=list_acceptances(db),
            storage_logs=list_storage_logs(db),
            adverse=list_adverse(db),
            recalls=list_recalls(db),
            personnel=list_personnel(db),
            alerts={key: len(value) for key, value in gsp_alerts(db).items()},
            msg=request.query_params.get("msg", ""),
        ),
    )


@router.post("/gsp/acceptances")
async def gsp_acceptance_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        create_acceptance(
            db,
            AcceptanceCreate(
                supplier_name=(form.get("supplier_name") or "").strip(),
                delivery_no=(form.get("delivery_no") or "").strip(),
                transport_temp=_form_float(form, "transport_temp"),
                transport_ok=form.get("transport_ok") == "on",
                items=[
                    AcceptanceItemCreate(
                        name=(form.get("item_name") or "").strip(),
                        batch_no=(form.get("batch_no") or "").strip(),
                        expiry=(
                            date.fromisoformat(form.get("expiry"))
                            if form.get("expiry")
                            else None
                        ),
                        quantity=_form_int(form, "quantity") or 0,
                    )
                ],
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "验收记录已保存"
    except Exception as e:  # noqa: BLE001
        msg = f"保存失败：{e}"
    return RedirectResponse(f"/admin/gsp?msg={quote(msg)}", status_code=302)


@router.post("/gsp/storage-logs")
async def gsp_storage_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        create_storage_log(
            db,
            StorageLogCreate(
                area=(form.get("area") or "药房").strip(),
                temperature=_form_float(form, "temperature"),
                humidity=_form_float(form, "humidity"),
                note=(form.get("note") or "").strip(),
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "温湿度记录已保存"
    except Exception as e:  # noqa: BLE001
        msg = f"保存失败：{e}"
    return RedirectResponse(f"/admin/gsp?msg={quote(msg)}", status_code=302)


@router.post("/gsp/adverse-reactions")
async def gsp_adverse_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        create_adverse(
            db,
            AdverseCreate(
                patient_name=(form.get("patient_name") or "").strip(),
                drug_name=(form.get("drug_name") or "").strip(),
                batch_no=(form.get("batch_no") or "").strip(),
                reaction=(form.get("reaction") or "").strip(),
                severity=form.get("severity") or "mild",
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "不良反应已报告"
    except Exception as e:  # noqa: BLE001
        msg = f"报告失败：{e}"
    return RedirectResponse(f"/admin/gsp?msg={quote(msg)}", status_code=302)


@router.post("/gsp/recalls")
async def gsp_recall_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        create_recall(
            db,
            RecallCreate(
                drug_name=(form.get("drug_name") or "").strip(),
                batch_no=(form.get("batch_no") or "").strip(),
                reason=(form.get("reason") or "").strip(),
                level=form.get("level") or "3",
            ),
            request.session.get("admin_user", "admin"),
        )
        msg = "召回已启动"
    except Exception as e:  # noqa: BLE001
        msg = f"召回失败：{e}"
    return RedirectResponse(f"/admin/gsp?msg={quote(msg)}", status_code=302)


@router.post("/gsp/recalls/{recall_id}/complete")
def gsp_recall_complete(request: Request, recall_id: int, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        complete_recall(db, recall_id, request.session.get("admin_user", "admin"))
        msg = "召回已完成"
    except Exception as e:  # noqa: BLE001
        msg = f"操作失败：{e}"
    return RedirectResponse(f"/admin/gsp?msg={quote(msg)}", status_code=302)


@router.post("/gsp/personnel")
async def gsp_personnel_submit(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        create_personnel(
            db,
            PersonnelCreate(
                name=(form.get("name") or "").strip(),
                role=(form.get("role") or "").strip(),
                certificate_no=(form.get("certificate_no") or "").strip(),
                valid_until=(
                    date.fromisoformat(form.get("valid_until"))
                    if form.get("valid_until")
                    else None
                ),
            ),
        )
        msg = "人员资质已保存"
    except Exception as e:  # noqa: BLE001
        msg = f"保存失败：{e}"
    return RedirectResponse(f"/admin/gsp?msg={quote(msg)}", status_code=302)

# ---------- 院长驾驶舱 ----------

@router.get("/executive", response_class=HTMLResponse)
def executive_page(
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        start, end = None, None
    data = executive_dashboard(db, start, end)
    trend_max = max([row["paid_amount"] for row in data["trend"]] or [1]) or 1
    return templates.TemplateResponse(
        request,
        "executive.html",
        _ctx(request, data=data, trend_max=trend_max),
    )

# ---------- 治疗室日报 ----------

@router.get("/treatment-report", response_class=HTMLResponse)
def treatment_report_page(
    request: Request,
    report_date: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        day = date.fromisoformat(report_date) if report_date else date.today()
    except ValueError:
        day = date.today()
    data = treatment_report(db, day)
    return templates.TemplateResponse(
        request,
        "treatment_report.html",
        _ctx(
            request,
            data=data,
            followups=treatment_followups(db, status="pending", due_before=day),
        ),
    )

# ---------- 治疗室模板配置 ----------

@router.get("/treatment-templates", response_class=HTMLResponse)
def treatment_templates_page(request: Request, db: Session = Depends(get_db)):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "treatment_templates.html",
        _ctx(
            request,
            templates_list=treatment_templates(db),
            charge_items=list_charge_items(db, "treatment"),
            materials=list_materials(db),
            msg=request.query_params.get("msg", ""),
        ),
    )


@router.post("/treatment-templates/{template_code}")
async def treatment_template_config(
    request: Request, template_code: str, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    form = await request.form()
    try:
        material_ids = form.getlist("material_id")
        quantities = form.getlist("material_quantity")
        warehouses = form.getlist("warehouse")
        materials = []
        for index, material_id in enumerate(material_ids):
            if not material_id:
                continue
            materials.append(
                {
                    "material_id": int(material_id),
                    "quantity": int(quantities[index] or 1) if index < len(quantities) else 1,
                    "warehouse": (warehouses[index] if index < len(warehouses) else "总库") or "总库",
                }
            )
        set_template_config(
            db,
            template_code,
            TemplateConfigUpdate(
                charge_item_id=int(form.get("charge_item_id")) if form.get("charge_item_id") else None,
                price=float(form.get("price") or 0),
                materials=materials,
                active=form.get("active") == "on",
            ),
        )
        msg = "模板配置已保存"
    except Exception as e:  # noqa: BLE001
        msg = f"保存失败：{e}"
    return RedirectResponse(f"/admin/treatment-templates?msg={quote(msg)}", status_code=302)

# ---------- 治疗室收费对账 ----------

@router.get("/treatment-reconciliation", response_class=HTMLResponse)
def treatment_reconciliation_page(
    request: Request,
    report_date: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        day = date.fromisoformat(report_date) if report_date else date.today()
    except ValueError:
        day = date.today()
    return templates.TemplateResponse(
        request,
        "treatment_reconciliation.html",
        _ctx(request, data=treatment_reconciliation(db, day)),
    )

# ---------- 门诊收费日结 ----------

@router.get("/cashier-daily", response_class=HTMLResponse)
def cashier_daily_page(
    request: Request,
    report_date: str | None = None,
    db: Session = Depends(get_db),
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        day = date.fromisoformat(report_date) if report_date else date.today()
    except ValueError:
        day = date.today()
    return templates.TemplateResponse(
        request,
        "cashier_daily.html",
        _ctx(request, data=cashier_daily(db, day)),
    )
