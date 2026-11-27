"""主窗口：独立客户端只构建本岗位页签；通用客户端保留按角色显示。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow, QScrollArea,
    QVBoxLayout, QWidget,
)

from his_client.api import ApiClient
from his_client.labels import zh
from his_client.profiles import ClientProfile, detect_profile
from his_client.ui.approval_flow import ApprovalFlowWidget
from his_client.ui.approval_inbox import ApprovalInboxWidget
from his_client.ui.archive import ArchiveWidget
from his_client.ui.audit_center import AuditCenterWidget
from his_client.ui.cashier import CashierWidget
from his_client.ui.catalog_proposal import CatalogReviewWidget
from his_client.ui.director import DirectorWidget
from his_client.ui.doctor import DoctorWidget
from his_client.ui.hr import HrWidget
from his_client.ui.integration_config import IntegrationConfigWidget
from his_client.ui.lab import LabWidget
from his_client.ui.narcotic import NarcoticWidget
from his_client.ui.notifications import NotificationWidget
from his_client.ui.nurse import NurseWidget
from his_client.ui.patient360 import Patient360Widget
from his_client.ui.pharmacy import PharmacyWidget
from his_client.ui.prescription_review import PrescriptionReviewWidget
from his_client.ui.purchase_receive import PurchaseReceiveWidget
from his_client.ui.radiology import RadiologyWidget
from his_client.ui.sidebar_tabs import SidebarTabs
from his_client.ui.surgery import SurgeryWidget
from his_client.ui.tcm import TcmWidget
from his_client.ui.theme import apply_theme, refresh_theme
from his_client.ui.treatment_room import TreatmentRoomWidget
from his_client.ui.window_theme import apply_light_titlebar


# 页签 ID → 构建函数；独立客户端只构建自己需要的页签
_TAB_BUILDERS = {
    "hr": lambda api, role: HrWidget(api),
    "approval_inbox": lambda api, role: ApprovalInboxWidget(api),
    "approval_flow": lambda api, role: ApprovalFlowWidget(api),
    "integration": lambda api, role: IntegrationConfigWidget(api),
    "notifications": lambda api, role: NotificationWidget(api, can_dispatch=(role == "admin")),
    "cashier": lambda api, role: CashierWidget(api, role=role),
    "doctor": lambda api, role: DoctorWidget(api),
    "patient360": lambda api, role: Patient360Widget(api),
    "pharmacy": lambda api, role: PharmacyWidget(api, role="pharmacist"),
    "pharmacy_review": lambda api, role: CatalogReviewWidget(api, "pharmacy"),
    "rx_review": lambda api, role: PrescriptionReviewWidget(api),
    "warehouse": lambda api, role: PharmacyWidget(api, role="warehouse"),
    "warehouse_review": lambda api, role: CatalogReviewWidget(api, "warehouse"),
    "purchase": lambda api, role: PurchaseReceiveWidget(api),
    "nurse": lambda api, role: NurseWidget(api),
    "lab": lambda api, role: LabWidget(api),
    "radiology": lambda api, role: RadiologyWidget(api),
    "surgery": lambda api, role: SurgeryWidget(api),
    "archive": lambda api, role: ArchiveWidget(api),
    "narcotic": lambda api, role: NarcoticWidget(api),
    "audit": lambda api, role: AuditCenterWidget(api),
    "director": lambda api, role: DirectorWidget(api),
    "treatment_review": lambda api, role: CatalogReviewWidget(api, "treatment"),
    "tcm_doctor": lambda api, role: TcmWidget(api, role="doctor"),
    "tcm_pharmacy": lambda api, role: TcmWidget(api, role="pharmacist"),
    "tcm_decoction": lambda api, role: TcmWidget(api, role="decoction"),
    "tcm_admin": lambda api, role: TcmWidget(api, role="admin"),
    "treatment": lambda api, role: TreatmentRoomWidget(api),
}

_TAB_TITLES = {
    "hr": "人事工作站", "approval_inbox": "审批待办", "approval_flow": "审批流程配置",
    "integration": "集成配置", "notifications": "通知中心", "cashier": "收费员工作站",
    "doctor": "门诊工作站", "patient360": "患者 360", "pharmacy": "药房工作站",
    "pharmacy_review": "药事审核工作站", "rx_review": "处方审方", "warehouse": "库房工作站",
    "warehouse_review": "库房审核工作站", "purchase": "采购到货", "nurse": "护士工作站",
    "lab": "检验工作站", "radiology": "影像工作站", "surgery": "手术室工作站",
    "archive": "病案档案工作站", "narcotic": "麻精账册", "audit": "审计中心",
    "director": "院长审批工作站", "treatment_review": "治疗项目审批",
    "tcm_doctor": "中药处方", "tcm_pharmacy": "中药房 / 煎药室",
    "tcm_decoction": "煎药室", "tcm_admin": "中药 / 煎药", "treatment": "治疗室工作站",
}


def _legacy_tabs(role: str) -> list[str]:
    tabs: list[str] = []
    if role in ("hr", "admin"):
        tabs += ["hr", "approval_inbox"]
    if role == "admin":
        tabs += ["approval_flow", "integration"]
    if role in ("admin", "director", "pharmacist", "warehouse", "hr"):
        tabs.append("notifications")
    if role in ("cashier", "admin"):
        tabs.append("cashier")
    if role in ("doctor", "admin"):
        tabs += ["doctor", "patient360"]
    if role in ("pharmacist", "admin"):
        tabs += ["pharmacy", "pharmacy_review", "rx_review"]
    if role in ("warehouse", "admin"):
        tabs += ["warehouse", "warehouse_review", "purchase"]
    if role in ("nurse", "admin"):
        tabs.append("nurse")
    if role in ("lab", "admin"):
        tabs.append("lab")
    if role in ("radiology", "admin"):
        tabs.append("radiology")
    if role in ("surgery", "anesthesia", "surgery_nurse", "admin"):
        tabs.append("surgery")
    if role in ("archive", "admin"):
        tabs.append("archive")
    if role in ("pharmacist", "director", "admin"):
        tabs.append("narcotic")
    if role in ("director", "admin"):
        tabs += ["audit", "director", "treatment_review"]
    if role == "doctor":
        tabs.append("tcm_doctor")
    if role == "pharmacist":
        tabs.append("tcm_pharmacy")
    if role == "decoction":
        tabs.append("tcm_decoction")
    if role == "admin":
        tabs.append("tcm_admin")
    if role in ("treatment", "admin"):
        tabs.append("treatment")
    if role in ("pharmacist", "warehouse", "director"):
        tabs.append("approval_inbox")
    # 去重且保持顺序
    return list(dict.fromkeys(tabs))


class MainWindow(QMainWindow):
    def __init__(self, api: ApiClient, user: dict, parent=None, profile: ClientProfile | None = None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.user = user
        self.profile = profile or detect_profile()
        self.setWindowTitle(self.profile.title)
        self.resize(1366, 768)
        self.setMinimumSize(1000, 640)
        self._build_menu()

        self._light_title_done = False
        role = user.get("role", "")
        self.sidebar = SidebarTabs()
        if self.profile.key == "universal":
            tab_ids = _legacy_tabs(role)
        elif role not in self.profile.roles:
            tab_ids = []
        else:
            tab_ids = list(self.profile.tabs)
        for tab_id in tab_ids:
            builder = _TAB_BUILDERS.get(tab_id)
            if builder is None:
                continue
            title = _TAB_TITLES.get(tab_id, tab_id)
            self.sidebar.add_lazy_tab(title, lambda b=builder: b(api, role))
        if self.sidebar.count() == 0:
            self.sidebar.addTab(
                _placeholder(f"当前岗位「{zh('role', role)}」不能使用此客户端"), "提示"
            )
        self.tabs = self.sidebar
        central = QWidget()
        central.setObjectName("scrollContent")
        # 给内容画布一个最小工作尺寸：窗口再小也不压扁输入框/表格，
        # 由外层 QScrollArea 提供上下滚动条。
        central.setMinimumSize(960, 720)
        if self.sidebar.count() > 12:
            outer = QVBoxLayout(central)
            outer.setContentsMargins(8, 6, 8, 0)
            nav_row = QHBoxLayout()
            nav_row.addWidget(QLabel("当前工作站"))
            self.workstation_nav = QComboBox()
            self.workstation_nav.setObjectName("workstationNav")
            for index in range(self.sidebar.count()):
                self.workstation_nav.addItem(self.sidebar.tabText(index))
            self.workstation_nav.currentIndexChanged.connect(self.sidebar.setCurrentIndex)
            self.sidebar.currentChanged.connect(self._sync_workstation_nav)
            nav_row.addWidget(self.workstation_nav, 1)
            outer.addLayout(nav_row)
            self.sidebar.tabBar().hide()
            outer.addWidget(self.sidebar, 1)
        else:
            outer = QVBoxLayout(central)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.addWidget(self.sidebar)
        scroll = QScrollArea()
        scroll.setObjectName("mainScroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(central)
        self.scroll_area = scroll
        self.setCentralWidget(scroll)
        self.sidebar.ensure_current()

        name = user.get("display_name") or user.get("username")
        self.statusBar().showMessage(
            f"服务器 {api.base_url} · 用户 {name}（{zh('role', role)}）· "
            f"{self.profile.title} v{self.profile.version} · 服务端 v{getattr(api, 'server_version', '—')}"
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
        about_action = settings_menu.addAction("关于客户端")
        about_action.triggered.connect(self._show_about)
        settings_menu.addSeparator()
        quit_action = settings_menu.addAction("退出")
        quit_action.triggered.connect(self.close)

    def _show_about(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(
            self, "关于客户端",
            f"{self.profile.title}\n岗位：{self.profile.key}\n"
            f"客户端版本：{self.profile.version}\n服务端：{self.api.base_url}",
        )

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
