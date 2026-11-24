"""通知 outbox 自动派发线程：仅当配置开启时启动。"""
from __future__ import annotations

import threading

from app import settings
from app.database import SessionLocal

from .service import dispatch_pending

_thread: threading.Thread | None = None
_stop = threading.Event()


def _run() -> None:
    while not _stop.is_set():
        db = SessionLocal()
        try:
            dispatch_pending(db)
        except Exception:
            db.rollback()
        finally:
            db.close()
        _stop.wait(max(5, settings.NOTIFY_DISPATCH_INTERVAL))


def start() -> bool:
    """启动后台派发；配置关闭或已启动时返回 False。"""
    global _thread
    if not settings.NOTIFY_AUTO_DISPATCH:
        return False
    if _thread and _thread.is_alive():
        return False
    _stop.clear()
    _thread = threading.Thread(target=_run, name="notify-dispatcher", daemon=True)
    _thread.start()
    return True


def stop() -> None:
    _stop.set()
    if _thread:
        _thread.join(timeout=2)
