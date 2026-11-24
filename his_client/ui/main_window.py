"""主窗口：按登录角色显示对应工作站页签。"""
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

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
from his_client.ui.hr import HrWidget
from his_client.ui.catalog_proposal import CatalogReviewWidget
from his_client.ui.prescription_review import PrescriptionReviewWidget
from his_client.ui.approval_inbox import ApprovalInboxWidget
from his_client.ui.approval_flow import ApprovalFlowWidget
from his_client.ui.notifications import NotificationWidget
from his_client.ui.integration_config import IntegrationConfigWidget
from his_client.ui.audit_center import AuditCenterWidget
from his_client.ui.narcotic import NarcoticWidget
from his_client.ui.radiology import RadiologyWidget
from his_client.ui.surgery import SurgeryWidget
from his_client.ui.purchase_receive import PurchaseReceiveWidget
from his_client.ui.theme import apply_theme, refresh_theme
from his_client.ui.window_theme import apply_light_titlebar


class MainWindow(QMainWindow):
    def __init__(self, api: ApiClient, user: dict, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.user = user
        self.setWindowTitle("HIS 门诊部客户端")
        self.resize(1366, 768)
        self.setMinimumSize(1200, 700)
        self._build_menu()

        self._light_title_done = False
        role = user.get("role", "")
        tabs = SidebarTabs()
        if role in ("hr", "admin"):
            tabs.add_lazy_tab("人事工作站", lambda: HrWidget(api))
            tabs.add_lazy_tab("审批待办", lambda: ApprovalInboxWidget(api))
        if role == "admin":
            tabs.add_lazy_tab("审批流程配置", lambda: ApprovalFlowWidget(api))
            tabs.add_lazy_tab("集成配置", lambda: IntegrationConfigWidget(api))
        if role in ("admin", "director", "pharmacist", "warehouse", "hr"):
            tabs.add_lazy_tab(
                "通知中心", lambda: NotificationWidget(api, can_dispatch=(role == "admin"))
            )
        if role in ("cashier", "admin"):
            tabs.add_lazy_tab("收费员工作站", lambda: CashierWidget(api, role=role))
        if role in ("doctor", "admin"):
            tabs.add_lazy_tab("门诊工作站", lambda: DoctorWidget(api))
        if role in ("doctor", "admin"):
            tabs.add_lazy_tab("患者 360", lambda: Patient360Widget(api))
        if role in ("pharmacist", "admin"):
            tabs.add_lazy_tab("药房工作站", lambda: PharmacyWidget(api, role="pharmacist"))
            tabs.add_lazy_tab("药事审核工作站", lambda: CatalogReviewWidget(api, "pharmacy"))
            tabs.add_lazy_tab("处方审方", lambda: PrescriptionReviewWidget(api))
        if role in ("warehouse", "admin"):
            tabs.add_lazy_tab("库房工作站", lambda: PharmacyWidget(api, role="warehouse"))
            tabs.add_lazy_tab("库房审核工作站", lambda: CatalogReviewWidget(api, "warehouse"))
            tabs.add_lazy_tab("采购到货", lambda: PurchaseReceiveWidget(api))
        if role in ("nurse", "admin"):
            tabs.add_lazy_tab("护士工作站", lambda: NurseWidget(api))
        if role in ("lab", "admin"):
            tabs.add_lazy_tab("检验工作站", lambda: LabWidget(api))
        if role in ("radiology", "admin"):
            tabs.add_lazy_tab("影像工作站", lambda: RadiologyWidget(api))
        if role in ("surgery", "admin"):
            tabs.add_lazy_tab("手术室工作站", lambda: SurgeryWidget(api))
        if role in ("archive", "admin"):
            tabs.add_lazy_tab("病案档案工作站", lambda: ArchiveWidget(api))
        if role in ("pharmacist", "director", "admin"):
            tabs.add_lazy_tab("麻精账册", lambda: NarcoticWidget(api))
        if role in ("director", "admin"):
            tabs.add_lazy_tab("审计中心", lambda: AuditCenterWidget(api))
        if role in ("director", "admin"):
            tabs.add_lazy_tab("院长审批工作站", lambda: DirectorWidget(api))
            tabs.add_lazy_tab("治疗项目审批", lambda: CatalogReviewWidget(api, "treatment"))
        if role == "doctor":
            tabs.add_lazy_tab("中药处方", lambda: TcmWidget(api, role="doctor"))
        if role == "pharmacist":
            tabs.add_lazy_tab("中药房 / 煎药室", lambda: TcmWidget(api, role="pharmacist"))
        if role == "decoction":
            tabs.add_lazy_tab("煎药室", lambda: TcmWidget(api, role="decoction"))
        if role == "admin":
            tabs.add_lazy_tab("中药 / 煎药", lambda: TcmWidget(api, role="admin"))
        if role in ("treatment", "admin"):
            tabs.add_lazy_tab("治疗室工作站", lambda: TreatmentRoomWidget(api))
        if role in ("pharmacist", "warehouse", "director"):
            tabs.add_lazy_tab("审批待办", lambda: ApprovalInboxWidget(api))
        if tabs.count() == 0:
            tabs.addTab(_placeholder(f"角色「{zh('role', role)}」暂无工作站"), "提示")
        self.tabs = tabs
        if tabs.count() > 12:
            # 管理端工作站过多，横向页签会溢出；改为下拉选择，避免隐藏入口
            central = QWidget()
            outer = QVBoxLayout(central)
            outer.setContentsMargins(8, 6, 8, 0)
            nav_row = QHBoxLayout()
            nav_row.addWidget(QLabel("当前工作站"))
            self.workstation_nav = QComboBox()
            self.workstation_nav.setObjectName("workstationNav")
            for index in range(tabs.count()):
                self.workstation_nav.addItem(tabs.tabText(index))
            self.workstation_nav.currentIndexChanged.connect(tabs.setCurrentIndex)
            tabs.currentChanged.connect(self._sync_workstation_nav)
            nav_row.addWidget(self.workstation_nav, 1)
            outer.addLayout(nav_row)
            tabs.tabBar().hide()
            outer.addWidget(tabs, 1)
            self.setCentralWidget(central)
        else:
            self.setCentralWidget(tabs)
        tabs.ensure_current()

        name = user.get("display_name") or user.get("username")
        self.statusBar().showMessage(
            f"服务器 {api.base_url} · 用户 {name}（{zh('role', role)}）· 客户端 v{CLIENT_VERSION}"
        )


    def _sync_workstation_nav(self, index: int) -> None:
        nav = getattr(self, "workstation_nav", None)
        if nav is not None and 0 <= index < nav.count() and nav.currentIndex() != index:
            nav.blockSignals(True)
            nav.setCurrentIndex(index)
            nav.blockSignals(False)

    def _build_menu(self) -> None:
        settings_menu = self.menuBar().addMenu("设置")
        refresh_action = settings_menu.addAction("刷新主题")
        refresh_action.setShortcut("F12")
        refresh_action.triggered.connect(self._refresh_theme)
        settings_menu.addSeparator()
        quit_action = settings_menu.addAction("退出")
        quit_action.triggered.connect(self.close)

    def _refresh_theme(self) -> None:
        refresh_theme()
        self.statusBar().showMessage("主题已刷新", 3000)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_light_title_done", False):
            self._light_title_done = True
            apply_light_titlebar(self)


def _placeholder(text: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    label = QLabel(text)
    label.setStyleSheet("font-size: 16px; color: #6b7280;")
    layout.addWidget(label)
    return widget
