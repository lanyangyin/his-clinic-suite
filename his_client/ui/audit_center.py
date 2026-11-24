"""审计中心：患者访问日志 + 病历修改版本。"""
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme


class AuditCenterWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        layout = QVBoxLayout(self)
        title = QLabel("审计中心")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        layout.addWidget(title)
        tabs = QTabWidget()
        tabs.addTab(self._build_access_tab(), "患者访问审计")
        tabs.addTab(self._build_version_tab(), "病历修改版本")
        layout.addWidget(tabs, 1)
        self._load_access()

    def _build_access_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        self.access_patient = QSpinBox()
        self.access_patient.setRange(1, 999999999)
        self.access_patient.setValue(381)
        load = QPushButton("查询")
        load.clicked.connect(self._load_access)
        row.addWidget(QLabel("患者 ID"))
        row.addWidget(self.access_patient)
        row.addWidget(load)
        row.addStretch(1)
        layout.addLayout(row)
        self.access_table = QTableWidget(0, 5)
        self.access_table.setHorizontalHeaderLabels(["时间", "用户", "角色", "动作", "路径"])
        self.access_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.access_table, 1)
        self.access_msg = QLabel("")
        layout.addWidget(self.access_msg)
        return page

    def _build_version_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        self.version_encounter = QSpinBox()
        self.version_encounter.setRange(1, 999999999)
        self.version_encounter.setValue(390)
        load = QPushButton("查询")
        load.clicked.connect(self._load_versions)
        row.addWidget(QLabel("就诊 ID"))
        row.addWidget(self.version_encounter)
        row.addWidget(load)
        row.addStretch(1)
        layout.addLayout(row)
        self.version_table = QTableWidget(0, 4)
        self.version_table.setHorizontalHeaderLabels(["版本", "动作", "修改人", "时间"])
        self.version_table.horizontalHeader().setStretchLastSection(True)
        self.version_table.cellClicked.connect(self._show_version)
        layout.addWidget(self.version_table, 1)
        self.version_detail = QLineEdit()
        self.version_detail.setReadOnly(True)
        self.version_detail.setPlaceholderText("选中版本查看 before/after JSON")
        layout.addWidget(self.version_detail)
        self.version_rows: list[dict] = []
        return page

    def _load_access(self) -> None:
        try:
            rows = self.api.list_patient_access_log(self.access_patient.value())
        except ApiError as e:
            self.access_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.access_table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            values = [
                str(item.get("created_at") or "")[:19].replace("T", " "),
                item.get("username") or "",
                item.get("role") or "",
                item.get("action") or "",
                item.get("path") or "",
            ]
            for j, value in enumerate(values):
                self.access_table.setItem(i, j, QTableWidgetItem(str(value)))
        self.access_msg.setText(f"访问记录 {len(rows)} 条")

    def _load_versions(self) -> None:
        try:
            self.version_rows = self.api.list_medical_record_versions(
                self.version_encounter.value()
            )
        except ApiError as e:
            self.version_detail.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.version_table.setRowCount(len(self.version_rows))
        for i, item in enumerate(self.version_rows):
            values = [
                str(item.get("version") or ""),
                item.get("action") or "",
                item.get("changed_by") or "",
                str(item.get("created_at") or "")[:19].replace("T", " "),
            ]
            for j, value in enumerate(values):
                self.version_table.setItem(i, j, QTableWidgetItem(str(value)))

    def _show_version(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.version_rows):
            item = self.version_rows[row]
            self.version_detail.setText(
                f"before={item.get('before_json') or '{}'}  after={item.get('after_json') or '{}'}"
            )
