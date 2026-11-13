"""院长审批工作站：病案销毁、采购申请。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme
from his_client.ui.sidebar_tabs import SidebarTabs

ARCHIVE_STATUS = {
    "pending": "待审批",
    "approved": "已批准",
    "rejected": "已驳回",
    "executed": "已执行",
}
PURCHASE_STATUS = {
    "submitted": "待审批",
    "approved": "已批准",
    "rejected": "已驳回",
    "ordered": "已下单",
    "received": "已收货",
}


class DirectorWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.archive_rows: list[dict] = []
        self.purchase_rows: list[dict] = []
        tabs = SidebarTabs()
        tabs.addTab(self._build_archive_tab(), "病案销毁审批")
        tabs.addTab(self._build_purchase_tab(), "采购申请审批")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        self._load_archives()
        self._load_purchases()

    def _build_archive_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        refresh = QPushButton("刷新待审批")
        refresh.clicked.connect(self._load_archives)
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)
        splitter = QSplitter(Qt.Horizontal)
        self.archive_table = QTableWidget(0, 7)
        self.archive_table.setHorizontalHeaderLabels(
            ["申请号", "病案号", "患者", "原因", "申请人", "附件", "状态"]
        )
        self.archive_table.cellClicked.connect(self._show_archive_detail)
        self.archive_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.archive_table)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        detail_box = QGroupBox("申请详情")
        detail_form = QFormLayout(detail_box)
        self.archive_detail = QLabel("请选择一条申请")
        self.archive_detail.setWordWrap(True)
        detail_form.addRow(self.archive_detail)
        right_layout.addWidget(detail_box)
        self.archive_preset = QComboBox()
        self.archive_preset.addItem("选择意见模板", "")
        self.archive_preset.addItem("同意，按清册执行", "同意，按清册执行")
        self.archive_preset.addItem("材料不齐，需补充附件", "材料不齐，需补充附件")
        self.archive_preset.addItem("暂缓，待进一步核实", "暂缓，待进一步核实")
        self.archive_preset.currentIndexChanged.connect(
            lambda: self.archive_note.setText(self.archive_preset.currentData() or "")
        )
        right_layout.addWidget(self.archive_preset)
        self.archive_note = QLineEdit()
        self.archive_note.setPlaceholderText("审批意见（可选）")
        approve = QPushButton("批准销毁")
        approve.clicked.connect(self._approve_archive)
        reject = QPushButton("驳回")
        reject.clicked.connect(self._reject_archive)
        note_row = QHBoxLayout()
        note_row.addWidget(self.archive_note, 1)
        note_row.addWidget(approve)
        note_row.addWidget(reject)
        right_layout.addLayout(note_row)
        self.archive_msg = QLabel("")
        self.archive_msg.setWordWrap(True)
        right_layout.addWidget(self.archive_msg)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 450])
        layout.addWidget(splitter, 1)
        return page

    def _build_purchase_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        refresh = QPushButton("刷新待审批")
        refresh.clicked.connect(self._load_purchases)
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)
        splitter = QSplitter(Qt.Horizontal)
        self.purchase_table = QTableWidget(0, 5)
        self.purchase_table.setHorizontalHeaderLabels(
            ["申请号", "科室", "申请人", "金额", "状态"]
        )
        self.purchase_table.cellClicked.connect(self._show_purchase_detail)
        self.purchase_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.purchase_table)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        detail_box = QGroupBox("申请详情")
        detail_form = QFormLayout(detail_box)
        self.purchase_detail = QLabel("请选择一条申请")
        self.purchase_detail.setWordWrap(True)
        detail_form.addRow(self.purchase_detail)
        right_layout.addWidget(detail_box)
        self.purchase_preset = QComboBox()
        self.purchase_preset.addItem("选择意见模板", "")
        self.purchase_preset.addItem("同意采购", "同意采购")
        self.purchase_preset.addItem("预算不足，暂缓", "预算不足，暂缓")
        self.purchase_preset.addItem("请补充三家比价", "请补充三家比价")
        self.purchase_preset.currentIndexChanged.connect(
            lambda: self.purchase_note.setText(self.purchase_preset.currentData() or "")
        )
        right_layout.addWidget(self.purchase_preset)
        self.purchase_note = QLineEdit()
        self.purchase_note.setPlaceholderText("驳回原因（批准可空）")
        approve = QPushButton("批准采购")
        approve.clicked.connect(self._approve_purchase)
        reject = QPushButton("驳回")
        reject.clicked.connect(self._reject_purchase)
        note_row = QHBoxLayout()
        note_row.addWidget(self.purchase_note, 1)
        note_row.addWidget(approve)
        note_row.addWidget(reject)
        right_layout.addLayout(note_row)
        self.purchase_msg = QLabel("")
        self.purchase_msg.setWordWrap(True)
        right_layout.addWidget(self.purchase_msg)
        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([820, 450])
        layout.addWidget(splitter, 1)
        return page

    def _show_archive_detail(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.archive_rows):
            item = self.archive_rows[row]
            self.archive_detail.setText(
                f"申请号：{item['id']}\n"
                f"病案号：{item.get('archive_no') or '—'}\n"
                f"患者：{item.get('patient_name') or '—'}\n"
                f"原因：{item.get('reason') or '—'}\n"
                f"申请人：{item.get('requested_by') or '—'}\n"
                f"附件：{item.get('attachment_name') or '无'}\n"
                f"状态：{ARCHIVE_STATUS.get(item['status'], item['status'])}"
            )

    def _show_purchase_detail(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.purchase_rows):
            item = self.purchase_rows[row]
            self.purchase_detail.setText(
                f"申请号：{item.get('request_no') or '—'}\n"
                f"科室：{item.get('department') or '—'}\n"
                f"申请人：{item.get('requester') or '—'}\n"
                f"金额：{item.get('amount', 0):.2f} 元\n"
                f"状态：{PURCHASE_STATUS.get(item['status'], item['status'])}"
            )

    def _load_archives(self) -> None:
        try:
            rows = self.api.list_archive_destruction_requests("pending")
        except ApiError as e:
            self.archive_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.archive_rows = rows
        self.archive_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            values = [
                str(item["id"]),
                item.get("archive_no") or "",
                item.get("patient_name") or "",
                item.get("reason") or "",
                item.get("requested_by") or "",
                item.get("attachment_name") or "无",
                ARCHIVE_STATUS.get(item["status"], item["status"]),
            ]
            for col, value in enumerate(values):
                self.archive_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.archive_msg.setText(f"待审批病案销毁 {len(rows)} 条")

    def _load_purchases(self) -> None:
        try:
            rows = self.api.list_purchase_requests("submitted")
        except ApiError as e:
            self.purchase_msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        self.purchase_rows = rows
        self.purchase_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            values = [
                item["request_no"],
                item.get("department") or "",
                item.get("requester") or "",
                f"{item.get('total_amount', 0):.2f}",
                PURCHASE_STATUS.get(item["status"], item["status"]),
            ]
            for col, value in enumerate(values):
                self.purchase_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.purchase_msg.setText(f"待审批采购申请 {len(rows)} 条")

    def _approve_archive(self) -> None:
        row = self.archive_table.currentRow()
        if row < 0:
            self.archive_msg.setText("请先选择一条销毁申请")
            return
        try:
            self.api.approve_archive_destruction(
                self.archive_rows[row]["id"], self.archive_note.text().strip()
            )
        except ApiError as e:
            self.archive_msg.setText(f"批准失败（{e.status_code}）：{e.detail}")
            return
        self.archive_msg.setText("已批准，等待病案室双人执行")
        self._load_archives()

    def _reject_archive(self) -> None:
        row = self.archive_table.currentRow()
        if row < 0:
            self.archive_msg.setText("请先选择一条销毁申请")
            return
        try:
            self.api.reject_archive_destruction(
                self.archive_rows[row]["id"], self.archive_note.text().strip()
            )
        except ApiError as e:
            self.archive_msg.setText(f"驳回失败（{e.status_code}）：{e.detail}")
            return
        self.archive_msg.setText("已驳回")
        self._load_archives()

    def _approve_purchase(self) -> None:
        row = self.purchase_table.currentRow()
        if row < 0:
            self.purchase_msg.setText("请先选择一条采购申请")
            return
        try:
            self.api.approve_purchase_request(self.purchase_rows[row]["id"])
        except ApiError as e:
            self.purchase_msg.setText(f"批准失败（{e.status_code}）：{e.detail}")
            return
        self.purchase_msg.setText("已批准")
        self._load_purchases()

    def _reject_purchase(self) -> None:
        row = self.purchase_table.currentRow()
        if row < 0:
            self.purchase_msg.setText("请先选择一条采购申请")
            return
        reason = self.purchase_note.text().strip()
        if not reason:
            self.purchase_msg.setText("驳回必须填写原因")
            return
        try:
            self.api.reject_purchase_request(self.purchase_rows[row]["id"], reason)
        except ApiError as e:
            self.purchase_msg.setText(f"驳回失败（{e.status_code}）：{e.detail}")
            return
        self.purchase_msg.setText("已驳回")
        self._load_purchases()
