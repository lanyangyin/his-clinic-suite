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


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QDialog

    from his_client.config import load_config
    from his_client.ui.login import LoginDialog
    from his_client.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))

    if "--auto-login" in sys.argv:
        pair = _auto_login()
        if pair:
            window = MainWindow(pair[0], pair[1])
            window.show()
            return app.exec()

    dialog = LoginDialog(load_config())
    if dialog.exec() != QDialog.Accepted or not dialog.api or not dialog.user:
        return 0

    window = MainWindow(dialog.api, dialog.user)
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
        PharmacyWidget(client),
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
        f"tabs={window.centralWidget().count()}",
        f"widgets={len(widgets)}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
