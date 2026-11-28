"""客户端崩溃日志：闪退时至少留下 Python 栈和 Qt 异常。"""
import faulthandler
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _log_path() -> Path:
    override = os.environ.get("HIS_CLIENT_LOG")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "HIS"
    else:
        base = Path.home() / ".his"
    return base / "client_crash.log"


def install_crash_logging() -> Path:
    path = _log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = open(path, "a", encoding="utf-8", buffering=1)
    except OSError:
        return path
    try:
        from his_client import CLIENT_VERSION
    except Exception:  # noqa: BLE001
        CLIENT_VERSION = "unknown"
    stream.write(
        f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} "
        f"client={CLIENT_VERSION} pid={os.getpid()} cwd={Path.cwd()} ===\n"
    )
    stream.flush()
    faulthandler.enable(file=stream, all_threads=True)

    def hook(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb, file=stream)
        stream.flush()
        try:
            from PySide6.QtCore import QThread
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance()
            if app is not None and QThread.currentThread() == app.thread():
                QMessageBox.critical(
                    None,
                    "程序错误",
                    f"操作失败，已写入日志：\n{path}\n\n{exc_type.__name__}: {exc_value}",
                )
        except Exception:  # noqa: BLE001
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = hook
    return path
