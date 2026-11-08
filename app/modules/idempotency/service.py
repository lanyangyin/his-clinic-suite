import time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db

from .models import IdempotencyKey

PROCESSING = "processing"
DONE = "done"


def _session() -> Session:
    return next(get_db())


def reserve(key: str, endpoint: str) -> bool:
    """原子占位：同 key+endpoint 只有第一个请求能占到（唯一约束兜底）。"""
    db = _session()
    try:
        db.add(IdempotencyKey(key=key, endpoint=endpoint, status=PROCESSING))
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False
    finally:
        db.close()


def get_cached(key: str, endpoint: str) -> tuple[int, str] | None:
    """查询已完成的响应；不存在或仍在处理中返回 None。"""
    db = _session()
    try:
        row = (
            db.query(IdempotencyKey)
            .filter(
                IdempotencyKey.key == key,
                IdempotencyKey.endpoint == endpoint,
                IdempotencyKey.status == DONE,
            )
            .first()
        )
        if row and row.response_status is not None and row.response_body is not None:
            return row.response_status, row.response_body
        return None
    finally:
        db.close()


def wait_for_cached(key: str, endpoint: str, timeout: float = 2.0) -> tuple[int, str] | None:
    """并发同 key：短暂等待首个请求完成，超时返回 None（调用方返回 409）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        cached = get_cached(key, endpoint)
        if cached is not None:
            return cached
        time.sleep(0.05)
    return None


def store_response(key: str, endpoint: str, status_code: int, body: str) -> None:
    """保存首次响应（重放时原样返回）。"""
    db = _session()
    try:
        row = (
            db.query(IdempotencyKey)
            .filter(IdempotencyKey.key == key, IdempotencyKey.endpoint == endpoint)
            .first()
        )
        if row:
            row.status = DONE
            row.response_status = status_code
            row.response_body = body
            db.commit()
    finally:
        db.close()


def release(key: str, endpoint: str) -> None:
    """释放占位：5xx 或异常时允许客户端重试。"""
    db = _session()
    try:
        row = (
            db.query(IdempotencyKey)
            .filter(IdempotencyKey.key == key, IdempotencyKey.endpoint == endpoint)
            .first()
        )
        if row:
            db.delete(row)
            db.commit()
    finally:
        db.close()
