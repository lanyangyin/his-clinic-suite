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
    list_versions as catalog_versions,
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
    get_outbound as get_warehouse_outbound,
    issue_outbound as warehouse_issue,
    list_outbounds as list_warehouse_outbounds,
    list_stocks as list_warehouse_stocks,
)

from .service import dashboard_stats

router = APIRouter(prefix="/admin", tags=["admin-console"])

templates = Jinja2Templates(directory=str(ADMIN_TEMPLATES_DIR))
templates.env.globals["roles"] = sorted(ROLES)
templates.env.globals["today"] = lambda: date.today().isoformat()


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
            q=q or "",
            category=category or "",
            message=request.query_params.get("msg", ""),
        ),
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
def warehouse_outbound_issue(
    request: Request, order_id: int, db: Session = Depends(get_db)
):
    redirect = _guard(request, db)
    if redirect:
        return redirect
    try:
        warehouse_issue(db, order_id, issuer=request.session.get("admin_user", "admin"))
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


