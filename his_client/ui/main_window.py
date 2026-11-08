"""主窗口：按登录角色显示对应工作站页签。"""
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from his_client import CLIENT_VERSION
from his_client.api import ApiClient
from his_client.ui.cashier import CashierWidget
from his_client.ui.doctor import DoctorWidget
from his_client.ui.nurse import NurseWidget
from his_client.ui.pharmacy import PharmacyWidget


class MainWindow(QMainWindow):
    def __init__(self, api: ApiClient, user: dict, parent=None):
        super().__init__(parent)
        self.api = api
        self.user = user
        self.setWindowTitle("HIS 门诊部客户端")
        self.resize(1100, 720)

        role = user.get("role", "")
        tabs = QTabWidget()
        if role in ("cashier", "admin"):
            tabs.addTab(CashierWidget(api), "收费员工作站")
        if role in ("doctor", "admin"):
            tabs.addTab(DoctorWidget(api), "医生工作站")
        if role in ("pharmacist", "admin"):
            tabs.addTab(PharmacyWidget(api, role="pharmacist"), "药房工作站")
        if role in ("warehouse", "admin"):
            tabs.addTab(PharmacyWidget(api, role="warehouse"), "库房工作站")
        if role in ("nurse", "admin"):
            tabs.addTab(NurseWidget(api), "护士工作站")
        if tabs.count() == 0:
            tabs.addTab(_placeholder(f"角色 {role} 暂无工作站"), "提示")
        self.setCentralWidget(tabs)

        name = user.get("display_name") or user.get("username")
        self.statusBar().showMessage(
            f"服务器 {api.base_url} · 用户 {name}（{role}）· 客户端 v{CLIENT_VERSION}"
        )


def _placeholder(text: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    label = QLabel(text)
    label.setStyleSheet("font-size: 16px; color: #6b7280;")
    layout.addWidget(label)
    return widget
