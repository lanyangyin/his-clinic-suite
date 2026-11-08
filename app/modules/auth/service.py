import hashlib
import os
import secrets

from sqlalchemy.orm import Session

from .models import AuditLog, User
from .schemas import UserCreate

ROLES = {"admin", "doctor", "nurse", "cashier", "pharmacist", "warehouse", "lab", "radiology"}
_ITERATIONS = 100_000


def hash_password(password: str) -> tuple[str, str]:
    """返回 (口令摘要, 盐)。PBKDF2-HMAC-SHA256，标准库实现，无外部依赖。"""
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    return digest, salt


def verify_password(user: User, password: str) -> bool:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(user.salt), _ITERATIONS
    ).hex()
    return secrets.compare_digest(digest, user.password_hash)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, data: UserCreate) -> User:
    """创建用户：角色合法且用户名不重复。"""
    if data.role not in ROLES:
        raise ValueError(f"非法角色：{data.role}")

    if get_user_by_username(db, data.username):
        raise ValueError("用户名已存在")

    digest, salt = hash_password(data.password)
    user = User(
        username=data.username,
        password_hash=digest,
        salt=salt,
        role=data.role,
        display_name=data.display_name or data.username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    """全部用户（按 ID 排序）。"""
    return db.query(User).order_by(User.id).all()


def list_audit_logs(
    db: Session, username: str | None = None, limit: int = 100
) -> list[AuditLog]:
    """审计日志（可按用户名过滤，最新在前）。"""
    query = db.query(AuditLog)
    if username:
        query = query.filter(AuditLog.username == username)
    return query.order_by(AuditLog.id.desc()).limit(limit).all()


def list_recent_audit_logs(db: Session, limit: int = 100) -> list[AuditLog]:
    """最近的操作日志（追加式，只读最新 limit 条）。"""
    return (
        db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    )


def log_action(
    db: Session,
    username: str,
    role: str,
    method: str,
    path: str,
    status_code: int,
) -> None:
    """写操作日志：由调用方传入会话并提交，业务失败也照记。"""
    db.add(
        AuditLog(
            username=username,
            role=role,
            method=method,
            path=path,
            status_code=status_code,
        )
    )
    db.commit()
