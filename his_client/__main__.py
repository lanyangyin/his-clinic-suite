"""客户端入口：python -m his_client；--self-test 做无界面冒烟检查。

演示用：--auto-login 配合环境变量 HIS_CLIENT_USER / HIS_CLIENT_PASSWORD 直接进入工作站。
"""
import os
import sys


def _auto_login():
    """演示自动登录：成功返回 (api, user)，失败返回 None（回退到登录框）。"""
    user = os.environ.get("HIS_CLIENT_USER")
    password = os.environ.get("HIS_CLIENT_PASSWORD")
    if not user or not password:
        return None

    from his_client.api import ApiClient, ApiError
    from his_client.config import load_config

    config = load_config()
    api = ApiClient(config.server_url, user, password, timeout=config.timeout)
    try:
        return api, api.me()
    except ApiError:
        return None


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for part in str(value or "").replace("-", ".").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts)


def _check_update(api) -> None:
    """最低版本检查：客户端过旧时提示，并打开配置的下载地址。"""
    from his_client import CLIENT_VERSION
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox

    try:
        info = api.version()
    except Exception:
        return
    minimum = str(info.get("client_min_version") or "")
    if not minimum or _version_tuple(CLIENT_VERSION) >= _version_tuple(minimum):
        return
    box = QMessageBox()
    box.setWindowTitle("客户端需要升级")
    box.setIcon(QMessageBox.Warning)
    box.setText(
        f"当前客户端版本 {CLIENT_VERSION}，服务器要求至少 {minimum}。\n"
        "请下载新客户端后再使用。"
    )
    download = QMessageBox()
    open_button = box.addButton("打开下载页", QMessageBox.AcceptRole)
    box.addButton("稍后", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() is open_button:
        url = str(info.get("download_url") or "").strip()
        if not url:
            url = api.base_url.rstrip("/") + "/download/client"
        QDesktopServices.openUrl(QUrl(url))


def _open_main_window(app, api, user):
    """显示加载提示后再构造主窗口，避免认证成功后出现空白/像闪退。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox, QProgressDialog

    from his_client.ui.main_window import MainWindow

    progress = QProgressDialog("登录成功，正在加载工作站…", "", 0, 0)
    progress.setWindowTitle("HIS 客户端")
    progress.setCancelButton(None)
    progress.setWindowModality(Qt.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.show()
    app.processEvents()
    try:
        return MainWindow(api, user)
    except Exception as exc:
        progress.close()
        QMessageBox.critical(None, "启动失败", f"加载工作站失败：{exc}")
        return None
    finally:
        progress.close()


def main() -> int:
    from his_client.crashlog import install_crash_logging

    log_path = install_crash_logging()
    print(f"客户端日志: {log_path}")
    if "--self-test" in sys.argv:
        return _self_test()

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QDialog

    from his_client.config import load_config
    from his_client.ui.login import LoginDialog
    from his_client.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    from his_client.ui.window_theme import install_light_titlebars
    from his_client.ui.table_policy import install_readonly_table_policy
    install_readonly_table_policy(app)
    install_light_titlebars(app)

    if "--auto-login" in sys.argv:
        pair = _auto_login()
        if pair:
            _check_update(pair[0])
            window = _open_main_window(app, pair[0], pair[1])
            if window is None:
                return 1
            window.show()
            return app.exec()

    dialog = LoginDialog(load_config())
    if dialog.exec() != QDialog.Accepted or not dialog.api or not dialog.user:
        return 0
    _check_update(dialog.api)

    window = _open_main_window(app, dialog.api, dialog.user)
    if window is None:
        return 1
    window.show()
    return app.exec()


def _self_test() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from his_client import CLIENT_VERSION
    from his_client.api import ApiClient
    from his_client.config import load_config
    from his_client.ui.cashier import CashierWidget
    from his_client.ui.doctor import DoctorWidget
    from his_client.ui.login import LoginDialog
    from his_client.ui.main_window import MainWindow
    from his_client.ui.nurse import NurseWidget
    from his_client.ui.pharmacy import PharmacyWidget

    app = QApplication(sys.argv)
    dialog = LoginDialog(load_config())
    client = ApiClient("http://127.0.0.1:1")
    widgets = [
        CashierWidget(client),
        DoctorWidget(client),
        PharmacyWidget(client, role="pharmacist"),
        PharmacyWidget(client, role="warehouse"),
        NurseWidget(client),
    ]
    window = MainWindow(
        ApiClient("http://127.0.0.1:1"),
        {"username": "admin", "display_name": "管理员", "role": "admin"},
    )
    print(
        "SELF-TEST OK",
        f"version={CLIENT_VERSION}",
        f"login={dialog.windowTitle()}",
        f"tabs={window.tabs.count()}",
        f"widgets={len(widgets)}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
