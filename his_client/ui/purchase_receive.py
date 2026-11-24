"""库房采购到货入库：查看采购单、按明细收货。"""
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QDate, Qt

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme

STATUS = {
    "submitted": "待审批",
    "approved": "已批准",
    "ordered": "已下单",
    "partially_received": "部分到货",
    "received": "已入库",
    "rejected": "已驳回",
}


class PurchaseReceiveWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.requests: list[dict] = []
        self.items: list[dict] = []
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("采购到货入库")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        refresh = QPushButton("刷新采购单")
        refresh.clicked.connect(self._load)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(refresh)
        layout.addLayout(top)
        splitter = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["采购号", "申请人", "状态", "金额", "供应商", "下单时间"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._select)
        splitter.addWidget(self.table)

        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        self.item_table = QTableWidget(0, 6)
        self.item_table.setHorizontalHeaderLabels(
            ["明细 ID", "品名", "规格", "订购", "已收", "单位"]
        )
        self.item_table.horizontalHeader().setStretchLastSection(True)
        self.item_table.cellClicked.connect(self._select_item)
        bl.addWidget(self.item_table, 1)
        form = QFormLayout()
        self.qty = QSpinBox()
        self.qty.setRange(1, 999999)
        self.batch = QLineEdit()
        self.expiry = QDateEdit(QDate.currentDate().addYears(1))
        self.expiry.setCalendarPopup(True)
        self.note = QLineEdit()
        form.addRow("本次到货数量", self.qty)
        form.addRow("批号", self.batch)
        form.addRow("效期", self.expiry)
        form.addRow("备注", self.note)
        bl.addLayout(form)
        submit = QPushButton("收货入库")
        submit.clicked.connect(self._receive)
        bl.addWidget(submit)
        self.msg = QLabel("")
        bl.addWidget(self.msg)
        splitter.addWidget(bottom)
        splitter.setSizes([260, 360])
        layout.addWidget(splitter, 1)
        self._load()

    def _load(self) -> None:
        try:
            self.requests = [
                row for row in self.api.list_purchase_requests()
                if row["status"] in ("approved", "ordered", "partially_received")
            ]
        except ApiError as e:
            self.msg.setText(f"加载失败：{e.detail}")
            return
        self.table.setRowCount(len(self.requests))
        for i, row in enumerate(self.requests):
            values = [
                row.get("request_no") or "",
                row.get("requester") or "",
                STATUS.get(row.get("status"), row.get("status") or ""),
                f"{float(row.get('total_amount') or 0):.2f}",
                str(row.get("supplier_id") or "—"),
                str(row.get("ordered_at") or "—")[:16].replace("T", " "),
            ]
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        self.msg.setText(f"待收货采购单 {len(self.requests)} 张")

    def _select(self, row: int, _col: int) -> None:
        if not 0 <= row < len(self.requests):
            return
        self.items = self.requests[row].get("items") or []
        self.item_table.setRowCount(len(self.items))
        for i, item in enumerate(self.items):
            values = [
                item.get("id"),
                item.get("name") or "",
                item.get("spec") or "",
                item.get("quantity") or 0,
                item.get("received_quantity") or 0,
                item.get("unit") or "",
            ]
            for j, value in enumerate(values):
                self.item_table.setItem(i, j, QTableWidgetItem(str(value)))
        self.msg.setText("请选择一条明细，填写本次到货")

    def _select_item(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.items):
            remaining = int(self.items[row].get("quantity") or 0) - int(
                self.items[row].get("received_quantity") or 0
            )
            self.qty.setValue(max(remaining, 1))
            self.batch.setText(self.items[row].get("batch_no") or "")

    def _receive(self) -> None:
        req_row = self.table.currentRow()
        item_row = self.item_table.currentRow()
        if not 0 <= req_row < len(self.requests) or not 0 <= item_row < len(self.items):
            self.msg.setText("请先选择采购单和明细")
            return
        payload = {
            "items": [
                {
                    "item_id": self.items[item_row]["id"],
                    "quantity": self.qty.value(),
                    "batch_no": self.batch.text().strip(),
                    "expiry": self.expiry.date().toString("yyyy-MM-dd"),
                }
            ],
            "note": self.note.text().strip(),
        }
        try:
            row = self.api.receive_purchase_request(
                self.requests[req_row]["id"], payload
            )
        except ApiError as e:
            self.msg.setText(f"收货失败：{e.detail}")
            return
        self._load()
        self.msg.setText(
            f"收货成功：{row['request_no']}，状态 {STATUS.get(row['status'], row['status'])}"
        )
