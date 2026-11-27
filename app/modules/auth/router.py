from fastapi import APIRouter, Depends, HTTPException

from app.modules.auth.security import require_read_login
from sqlalchemy.orm import Session

from app.database import get_db

from .schemas import (
    AuditLogResponse, NarcoticRightUpdate, PasswordReset, UserActiveUpdate,
    UserCreate, UserResponse,
)
from .security import require_login, require_role
from .service import (
    create_user, get_user, list_recent_audit_logs, reset_password, set_user_active,
)

router = APIRouter(tags=["auth"], dependencies=[Depends(require_read_login)])


@router.get("/auth/me", response_model=UserResponse)
def me(user=Depends(require_login)):
    """当前登录用户（客户端登录校验）。"""
    return user


@router.post("/users/", response_model=UserResponse, status_code=201)
def new_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "hr")),
):
    if user.role == "hr" and data.role in ("admin", "director"):
        raise HTTPException(status_code=403, detail="人事不能创建管理员/院长账号")
    try:
        return create_user(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/users/{user_id}/active", response_model=UserResponse)
def change_user_active(
    user_id: int,
    data: UserActiveUpdate,
    db: Session = Depends(get_db),
    current=Depends(require_role("admin", "hr")),
):
    target = get_user(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == current.id and not data.active:
        raise HTTPException(status_code=400, detail="不能停用当前登录账号")
    if current.role == "hr" and target.role in ("admin", "director"):
        raise HTTPException(status_code=403, detail="人事不能停用管理员/院长账号")
    try:
        return set_user_active(db, user_id, data.active)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/users/{user_id}/reset-password", response_model=UserResponse)
def reset_user_password(
    user_id: int,
    data: PasswordReset,
    db: Session = Depends(get_db),
    current=Depends(require_role("admin", "hr")),
):
    target = get_user(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if current.role == "hr" and target.role in ("admin", "director"):
        raise HTTPException(status_code=403, detail="人事不能重置管理员/院长密码")
    try:
        return reset_password(db, user_id, data.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/", response_model=list[UserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin", "hr")),
):
    from .service import list_users

    return list_users(db)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user_one(user_id: int, db: Session = Depends(get_db)):
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/users/{user_id}/narcotic-right", response_model=UserResponse)
def set_narcotic_right(
    user_id: int,
    data: NarcoticRightUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_role("admin")),
):
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.narcotic_right = data.enabled
    db.commit()
    db.refresh(user)
    return user


@router.get("/audit/logs", response_model=list[AuditLogResponse])
def audit_logs(
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin", "director")),
):
    return list_recent_audit_logs(db)
