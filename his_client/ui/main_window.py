"""主窗口：按登录角色显示对应工作站页签。"""
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from his_client import CLIENT_VERSION
from his_client.api import ApiClient
from his_client.ui.cashier import CashierWidget
from his_client.ui.doctor import DoctorWidget
from his_client.labels import zh
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.archive import ArchiveWidget
from his_client.ui.director import DirectorWidget
from his_client.ui.lab import LabWidget
from his_client.ui.nurse import NurseWidget
from his_client.ui.patient360 import Patient360Widget
from his_client.ui.tcm import TcmWidget
from his_client.ui.treatment_room import TreatmentRoomWidget
from his_client.ui.pharmacy import PharmacyWidget


class MainWindow(QMainWindow):
    def __init__(self, api: ApiClient, user: dict, parent=None):
        super().__init__(parent)
        self.api = api
        self.user = user
        self.setWindowTitle("HIS 门诊部客户端")
        self.resize(1366, 768)
        self.setMinimumSize(1200, 700)

        role = user.get("role", "")
        tabs = SidebarTabs()
        if role in ("cashier", "admin"):
            tabs.addTab(CashierWidget(api, role=role), "收费员工作站")
        if role in ("doctor", "admin"):
            tabs.addTab(DoctorWidget(api), "医生工作站")
        if role in ("doctor", "admin"):
            tabs.addTab(Patient360Widget(api), "患者 360")
        if role in ("pharmacist", "admin"):
            tabs.addTab(PharmacyWidget(api, role="pharmacist"), "药房工作站")
        if role in ("warehouse", "admin"):
            tabs.addTab(PharmacyWidget(api, role="warehouse"), "库房工作站")
        if role in ("nurse", "admin"):
            tabs.addTab(NurseWidget(api), "护士工作站")
        if role in ("lab", "admin"):
            tabs.addTab(LabWidget(api), "检验工作站")
        if role in ("archive", "admin"):
            tabs.addTab(ArchiveWidget(api), "病案档案工作站")
        if role in ("director", "admin"):
            tabs.addTab(DirectorWidget(api), "院长审批工作站")
        if role == "doctor":
            tabs.addTab(TcmWidget(api, role="doctor"), "中药处方")
        if role == "pharmacist":
            tabs.addTab(TcmWidget(api, role="pharmacist"), "中药房 / 煎药室")
        if role == "decoction":
            tabs.addTab(TcmWidget(api, role="decoction"), "煎药室")
        if role == "admin":
            tabs.addTab(TcmWidget(api, role="admin"), "中药 / 煎药")
        if role in ("treatment", "admin"):
            tabs.addTab(TreatmentRoomWidget(api), "治疗室工作站")
        if tabs.count() == 0:
            tabs.addTab(_placeholder(f"角色「{zh('role', role)}」暂无工作站"), "提示")
        self.setCentralWidget(tabs)

        name = user.get("display_name") or user.get("username")
        self.statusBar().showMessage(
            f"服务器 {api.base_url} · 用户 {name}（{zh('role', role)}）· 客户端 v{CLIENT_VERSION}"
        )


def _placeholder(text: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    label = QLabel(text)
    label.setStyleSheet("font-size: 16px; color: #6b7280;")
    layout.addWidget(label)
    return widget
