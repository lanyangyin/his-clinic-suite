"""护士工作站：门诊分诊叫号、治疗执行。"""
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.labels import zh


class NurseWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        tabs = QTabWidget()
        tabs.addTab(self._build_triage_tab(), "分诊叫号")
        tabs.addTab(self._build_treatment_tab(), "治疗执行")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    # ---------- 分诊 ----------
    def _build_triage_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("分诊登记")
        row = QHBoxLayout(box)
        self.triage_reg_id = QSpinBox()
        self.triage_reg_id.setRange(1, 10_000_000)
        submit = QPushButton("登记分诊")
        submit.clicked.connect(self._create_ticket)
        row.addWidget(QLabel("挂号 ID"))
        row.addWidget(self.triage_reg_id)
        row.addWidget(submit)
        layout.addWidget(box)

        queue_row = QHBoxLayout()
        refresh = QPushButton("刷新队列")
        refresh.clicked.connect(self._load_queue)
        call = QPushButton("叫号")
        call.clicked.connect(self._call_ticket)
        skip = QPushButton("过号")
        skip.clicked.connect(self._pass_ticket)
        queue_row.addWidget(refresh)
        queue_row.addWidget(call)
        queue_row.addWidget(skip)
        queue_row.addStretch(1)
        layout.addLayout(queue_row)

        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["叫号单 ID", "挂号 ID", "状态"])
        layout.addWidget(self.queue_table)

        self.triage_msg = QLabel("")
        self.triage_msg.setWordWrap(True)
        layout.addWidget(self.triage_msg)
        return page

    def _selected_ticket_id(self) -> int | None:
        row = self.queue_table.currentRow()
        if row < 0:
            return None
        item = self.queue_table.item(row, 0)
        return int(item.text()) if item else None

    def _create_ticket(self) -> None:
        try:
            ticket = self.api.create_triage_ticket(self.triage_reg_id.value())
        except ApiError as e:
            self.triage_msg.setText(f"分诊失败（{e.status_code}）：{e.detail}")
            return
        self.triage_msg.setText(f"分诊成功：叫号单 {ticket['id']}（{zh('ticket_status', ticket['status'])}）")
        self._load_queue()

    def _load_queue(self) -> None:
        try:
            tickets = self.api.triage_queue()
        except ApiError as e:
            self.triage_msg.setText(f"加载队列失败：{e.detail}")
            return
        self.queue_table.setRowCount(len(tickets))
        for row, ticket in enumerate(tickets):
            self.queue_table.setItem(row, 0, QTableWidgetItem(str(ticket["id"])))
            self.queue_table.setItem(
                row, 1, QTableWidgetItem(str(ticket["registration_id"]))
            )
            self.queue_table.setItem(row, 2, QTableWidgetItem(zh('ticket_status', ticket["status"])))
        self.triage_msg.setText(f"当前队列 {len(tickets)} 人")

    def _call_ticket(self) -> None:
        ticket_id = self._selected_ticket_id()
        if not ticket_id:
            self.triage_msg.setText("请先在队列中选中一条记录")
            return
        try:
            ticket = self.api.call_ticket(ticket_id)
        except ApiError as e:
            self.triage_msg.setText(f"叫号失败（{e.status_code}）：{e.detail}")
            return
        self.triage_msg.setText(f"已叫号：{ticket['id']}（{zh('ticket_status', ticket['status'])}）")
        self._load_queue()

    def _pass_ticket(self) -> None:
        ticket_id = self._selected_ticket_id()
        if not ticket_id:
            self.triage_msg.setText("请先在队列中选中一条记录")
            return
        try:
            ticket = self.api.pass_ticket(ticket_id)
        except ApiError as e:
            self.triage_msg.setText(f"过号失败（{e.status_code}）：{e.detail}")
            return
        self.triage_msg.setText(f"已过号：{ticket['id']}（{zh('ticket_status', ticket['status'])}）")
        self._load_queue()

    # ---------- 治疗执行 ----------
    def _build_treatment_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        refresh = QPushButton("刷新待执行治疗")
        refresh.clicked.connect(self._load_pending_treatments)
        execute = QPushButton("执行选中治疗")
        execute.clicked.connect(self._execute_treatment)
        row.addWidget(refresh)
        row.addWidget(execute)
        row.addStretch(1)
        layout.addLayout(row)

        self.treat_table = QTableWidget(0, 5)
        self.treat_table.setHorizontalHeaderLabels(
            ["治疗单 ID", "就诊 ID", "项目", "数量", "状态"]
        )
        layout.addWidget(self.treat_table)

        self.treat_msg = QLabel("")
        self.treat_msg.setWordWrap(True)
        layout.addWidget(self.treat_msg)
        return page

    def _load_pending_treatments(self) -> None:
        try:
            orders = self.api.list_pending_treatments()
        except ApiError as e:
            self.treat_msg.setText(f"加载治疗单失败：{e.detail}")
            return
        self.treat_table.setRowCount(len(orders))
        for row, order in enumerate(orders):
            self.treat_table.setItem(row, 0, QTableWidgetItem(str(order["id"])))
            self.treat_table.setItem(
                row, 1, QTableWidgetItem(str(order["encounter_id"]))
            )
            self.treat_table.setItem(row, 2, QTableWidgetItem(order["item_name"]))
            self.treat_table.setItem(row, 3, QTableWidgetItem(str(order["quantity"])))
            self.treat_table.setItem(row, 4, QTableWidgetItem(zh('treatment_status', order["status"])))
        self.treat_msg.setText(f"待执行治疗单 {len(orders)} 条")

    def _execute_treatment(self) -> None:
        row = self.treat_table.currentRow()
        if row < 0:
            self.treat_msg.setText("请先选中一条治疗单")
            return
        order_id = int(self.treat_table.item(row, 0).text())
        try:
            order = self.api.execute_treatment(order_id)
        except ApiError as e:
            self.treat_msg.setText(f"执行失败（{e.status_code}）：{e.detail}")
            return
        self.treat_msg.setText(
            f"已执行：{order['item_name']}（执行人 {order.get('executed_by') or '—'}）"
        )
        self._load_pending_treatments()

