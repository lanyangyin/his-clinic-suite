from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.database import get_db

from .models import User
from .service import get_user_by_username, verify_password

basic = HTTPBasic(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(basic),
    db: Session = Depends(get_db),
) -> User | None:
    """解析 HTTP Basic 凭据；未提供时返回 None（留给 require_role 决定）。"""
    request.state.user = None
    if credentials is None:
        return None

    user = get_user_by_username(db, credentials.username)
    if not user or not verify_password(user, credentials.password):
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Basic"},
        )

    request.state.user = user
    # 审计中间件在会话关闭后写日志，使用字符串避免 ORM 对象过期问题
    request.state.user_name = user.username
    request.state.user_role = user.role
    return user


def require_login(request: Request, user: User | None = Depends(get_current_user)) -> User:
    """要求已登录（任意角色），客户端登录校验用。"""
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="需要登录",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def require_role(*roles: str):
    """要求已登录且角色在允许集合（admin 恒允许）。"""

    def checker(request: Request, user: User | None = Depends(get_current_user)):
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="需要登录",
                headers={"WWW-Authenticate": "Basic"},
            )
        if user.role not in roles and user.role != "admin":
            raise HTTPException(
                status_code=403, detail=f"需要角色：{'/'.join(roles)}"
            )
        return user

    return checker
