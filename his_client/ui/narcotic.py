"""麻精账册与盘点差异工作站。"""
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
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


class NarcoticWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        layout = QVBoxLayout(self)
        title = QLabel("麻精账册 / 盘点")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        layout.addWidget(title)
        tabs = QTabWidget()
        tabs.addTab(self._build_ledger_tab(), "专用账册")
        tabs.addTab(self._build_check_tab(), "盘点差异")
        layout.addWidget(tabs, 1)
        self._load_ledger()
        self._load_checks()

    def _build_ledger_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._load_ledger)
        top.addWidget(QLabel("发药/退药/空安瓿回收逐笔记录"))
        top.addStretch(1)
        top.addWidget(refresh)
        layout.addLayout(top)
        self.ledger_table = QTableWidget(0, 7)
        self.ledger_table.setHorizontalHeaderLabels(
            ["时间", "药品", "批号", "动作", "数量", "操作人", "见证人"]
        )
        self.ledger_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.ledger_table, 1)
        self.ledger_msg = QLabel("")
        layout.addWidget(self.ledger_msg)
        return page

    def _build_check_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.drug_id = QSpinBox()
        self.drug_id.setRange(1, 999999999)
        self.batch = QLineEdit()
        self.counted = QSpinBox()
        self.counted.setRange(0, 999999)
        self.reason = QLineEdit()
        form.addRow("药品 ID", self.drug_id)
        form.addRow("批号", self.batch)
        form.addRow("实盘数量", self.counted)
        form.addRow("差异原因", self.reason)
        layout.addLayout(form)
        actions = QHBoxLayout()
        create = QPushButton("登记盘点")
        create.clicked.connect(self._create_check)
        approve = QPushButton("通过选中")
        approve.clicked.connect(lambda: self._review(True))
        reject = QPushButton("驳回选中")
        reject.clicked.connect(lambda: self._review(False))
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._load_checks)
        actions.addWidget(create)
        actions.addStretch(1)
        actions.addWidget(approve)
        actions.addWidget(reject)
        actions.addWidget(refresh)
        layout.addLayout(actions)
        self.check_table = QTableWidget(0, 7)
        self.check_table.setHorizontalHeaderLabels(
            ["药品", "批号", "账面", "实盘", "差异", "状态", "原因"]
        )
        self.check_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.check_table, 1)
        self.check_msg = QLabel("")
        layout.addWidget(self.check_msg)
        return page

    def _load_ledger(self) -> None:
        try:
            rows = self.api.list_narcotic_ledger()
        except ApiError as e:
            self.ledger_msg.setText(f"加载失败：{e.detail}")
            return
        labels = {"issue": "发药", "return": "退药", "ampoule_return": "空安瓿回收"}
        self.ledger_table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            values = [
                str(item.get("created_at") or "")[:19].replace("T", " "),
                item.get("drug_name") or "",
                item.get("batch_no") or "",
                labels.get(item.get("action"), item.get("action") or ""),
                str(item.get("quantity") or 0),
                item.get("operator") or "",
                item.get("witness") or "",
            ]
            for j, value in enumerate(values):
                self.ledger_table.setItem(i, j, QTableWidgetItem(str(value)))
        self.ledger_msg.setText(f"账册 {len(rows)} 笔")

    def _load_checks(self) -> None:
        try:
            self.check_rows = self.api.list_inventory_checks()
        except ApiError as e:
            self.check_msg.setText(f"加载失败：{e.detail}")
            return
        labels = {"pending": "待审批", "approved": "已通过", "rejected": "已驳回"}
        self.check_table.setRowCount(len(self.check_rows))
        for i, item in enumerate(self.check_rows):
            values = [
                item.get("drug_name") or "",
                item.get("batch_no") or "",
                str(item.get("expected_qty") or 0),
                str(item.get("counted_qty") or 0),
                str(item.get("difference") or 0),
                labels.get(item.get("status"), item.get("status") or ""),
                item.get("reason") or "",
            ]
            for j, value in enumerate(values):
                self.check_table.setItem(i, j, QTableWidgetItem(str(value)))
        self.check_msg.setText(f"盘点单 {len(self.check_rows)} 条")

    def _create_check(self) -> None:
        try:
            self.api.create_inventory_check(
                {
                    "drug_id": self.drug_id.value(),
                    "batch_no": self.batch.text().strip(),
                    "counted_qty": self.counted.value(),
                    "reason": self.reason.text().strip(),
                }
            )
        except ApiError as e:
            self.check_msg.setText(f"登记失败：{e.detail}")
            return
        self._load_checks()
        self.check_msg.setText("已登记，等待院长审批")

    def _review(self, approve: bool) -> None:
        row = self.check_table.currentRow()
        rows = getattr(self, "check_rows", [])
        if not 0 <= row < len(rows):
            self.check_msg.setText("请先选择盘点单")
            return
        note = self.reason.text().strip()
        if not approve and not note:
            self.check_msg.setText("驳回必须填写原因")
            return
        try:
            self.api.review_inventory_check(rows[row]["id"], approve, note)
        except ApiError as e:
            self.check_msg.setText(f"处理失败：{e.detail}")
            return
        self._load_checks()
        self.check_msg.setText("已通过" if approve else "已驳回")
