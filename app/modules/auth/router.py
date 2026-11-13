from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db

from .schemas import AuditLogResponse, UserCreate, UserResponse
from .security import require_login, require_role
from .service import create_user, get_user, list_recent_audit_logs

router = APIRouter(tags=["auth"])


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


@router.get("/audit/logs", response_model=list[AuditLogResponse])
def audit_logs(db: Session = Depends(get_db)):
    return list_recent_audit_logs(db)
