"""管理员：按业务类型配置多级审批步骤。"""
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme

BIZ_LABELS = {
    "prescription": "处方审方",
    "catalog_proposal": "目录建议",
    "purchase_request": "采购申请",
    "archive_destruction": "病案销毁",
    "salary_request": "薪资申请",
}
ROLES = ["pharmacist", "warehouse", "director", "hr", "admin"]


class ApprovalFlowWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("审批流程配置")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        self.biz = QComboBox()
        for key, label in BIZ_LABELS.items():
            self.biz.addItem(label, key)
        self.biz.currentIndexChanged.connect(self._load)
        load = QPushButton("刷新")
        load.clicked.connect(self._load)
        top.addWidget(title)
        top.addSpacing(12)
        top.addWidget(self.biz)
        top.addStretch(1)
        top.addWidget(load)
        layout.addLayout(top)
        hint = QLabel("步骤按顺序执行；未配置的业务使用单步默认审批。处方第一步必须是药师。")
        hint.setStyleSheet("color:#64748b;")
        layout.addWidget(hint)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["步骤", "审批角色", "时限(小时)", "启用"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        add = QPushButton("增加步骤")
        add.clicked.connect(self._add)
        remove = QPushButton("删除选中")
        remove.clicked.connect(self._remove)
        save = QPushButton("保存流程")
        save.clicked.connect(self._save)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addStretch(1)
        actions.addWidget(save)
        layout.addLayout(actions)
        self.msg = QLabel("")
        layout.addWidget(self.msg)
        self._load()

    def _load(self) -> None:
        biz = self.biz.currentData()
        try:
            rows = self.api.get_approval_flow(biz)
        except ApiError as e:
            self.msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            role = QComboBox()
            role.addItems(ROLES)
            role.setCurrentText(row.get("role_required") or "pharmacist")
            self.table.setCellWidget(i, 1, role)
            self.table.setItem(i, 2, QTableWidgetItem(str(row.get("due_hours") or 24)))
            self.table.setItem(i, 3, QTableWidgetItem("是" if row.get("active", True) else "否"))
        self.msg.setText(f"{BIZ_LABELS.get(biz, biz)}：{len(rows)} 个步骤")

    def _add(self) -> None:
        i = self.table.rowCount()
        self.table.insertRow(i)
        self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
        role = QComboBox()
        role.addItems(ROLES)
        self.table.setCellWidget(i, 1, role)
        self.table.setItem(i, 2, QTableWidgetItem("24"))
        self.table.setItem(i, 3, QTableWidgetItem("是"))

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            for i in range(self.table.rowCount()):
                self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

    def _save(self) -> None:
        steps = []
        for i in range(self.table.rowCount()):
            role = self.table.cellWidget(i, 1)
            due = self.table.item(i, 2)
            active = self.table.item(i, 3)
            steps.append(
                {
                    "role_required": role.currentText() if role else "pharmacist",
                    "due_hours": int(due.text()) if due and due.text().isdigit() else 24,
                    "active": not active or active.text() != "否",
                }
            )
        if not steps:
            self.msg.setText("至少保留一个步骤")
            return
        biz = self.biz.currentData()
        if biz == "prescription" and steps[0]["role_required"] != "pharmacist":
            self.msg.setText("处方审批第一步必须是药师")
            return
        try:
            self.api.set_approval_flow(biz, steps)
        except ApiError as e:
            self.msg.setText(f"保存失败（{e.status_code}）：{e.detail}")
            return
        self.msg.setText("已保存")
        self._load()
