from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.settings import ADMIN_TEMPLATES_DIR
from app.modules.auth.schemas import UserCreate
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
from app.modules.reports.service import department_revenue
from app.modules.review.service import summary as review_summary
from app.modules.staff.schemas import DepartmentCreate, DoctorCreate
from app.modules.staff.service import (
    create_department,
    create_doctor,
    list_departments,
    list_doctors,
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
