"""药房工作站：入库、发药、库存查询。"""
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
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


class PharmacyWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        tabs = QTabWidget()
        tabs.addTab(self._build_stock_in_tab(), "入库")
        tabs.addTab(self._build_dispense_tab(), "发药")
        tabs.addTab(self._build_stock_tab(), "库存查询")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    # ---------- 入库 ----------
    def _build_stock_in_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("药品入库")
        form = QFormLayout(box)
        self.in_drug_combo = QComboBox()
        load = QPushButton("刷新药品目录")
        load.clicked.connect(self._load_drugs)
        self.in_batch = QLineEdit()
        self.in_batch.setPlaceholderText("如 20261108-A")
        self.in_expiry = QLineEdit()
        self.in_expiry.setPlaceholderText("效期 YYYY-MM-DD")
        self.in_location = QLineEdit()
        self.in_location.setPlaceholderText("如 D-01")
        self.in_quantity = QSpinBox()
        self.in_quantity.setRange(1, 100000)
        self.in_quantity.setValue(100)
        submit = QPushButton("入库")
        submit.clicked.connect(self._stock_in)
        form.addRow("药品", self.in_drug_combo)
        form.addRow("", load)
        form.addRow("批次号", self.in_batch)
        form.addRow("效期", self.in_expiry)
        form.addRow("货位", self.in_location)
        form.addRow("数量", self.in_quantity)
        form.addRow("", submit)
        layout.addWidget(box)

        self.in_msg = QLabel("")
        self.in_msg.setWordWrap(True)
        layout.addWidget(self.in_msg)
        layout.addStretch(1)
        return page

    def _load_drugs(self) -> None:
        try:
            drugs = self.api.list_drugs()
        except ApiError as e:
            self.in_msg.setText(f"加载药品失败：{e.detail}")
            return
        self.in_drug_combo.clear()
        for drug in drugs:
            self.in_drug_combo.addItem(drug["name"], drug["id"])

    def _stock_in(self) -> None:
        drug_id = self.in_drug_combo.currentData()
        if not drug_id:
            self.in_msg.setText("请先刷新并选择药品")
            return
        payload = {
            "drug_id": drug_id,
            "batch_no": self.in_batch.text().strip(),
            "expiry": self.in_expiry.text().strip(),
            "location": self.in_location.text().strip(),
            "quantity": self.in_quantity.value(),
        }
        try:
            stock = self.api.stock_in(payload)
        except ApiError as e:
            self.in_msg.setText(f"入库失败（{e.status_code}）：{e.detail}")
            return
        self.in_msg.setText(
            f"入库成功：{stock['drug_id']} 批次 {stock['batch_no']}，当前库存 {stock['quantity']}"
        )

    # ---------- 发药 ----------
    def _build_dispense_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        box = QGroupBox("门诊发药")
        row = QHBoxLayout(box)
        self.disp_encounter_id = QSpinBox()
        self.disp_encounter_id.setRange(1, 10_000_000)
        submit = QPushButton("发药")
        submit.clicked.connect(self._dispense)
        row.addWidget(QLabel("就诊 ID"))
        row.addWidget(self.disp_encounter_id)
        row.addWidget(submit)
        layout.addWidget(box)

        self.disp_msg = QLabel("")
        self.disp_msg.setWordWrap(True)
        layout.addWidget(self.disp_msg)

        return_box = QGroupBox("退药")
        return_row = QHBoxLayout(return_box)
        self.return_dispense_id = QSpinBox()
        self.return_dispense_id.setRange(1, 10_000_000)
        return_btn = QPushButton("退药（库存回补）")
        return_btn.clicked.connect(self._return_dispense)
        return_row.addWidget(QLabel("发药记录 ID"))
        return_row.addWidget(self.return_dispense_id)
        return_row.addWidget(return_btn)
        layout.addWidget(return_box)

        self.return_msg = QLabel("")
        self.return_msg.setWordWrap(True)
        layout.addWidget(self.return_msg)
        layout.addStretch(1)
        return page

    def _dispense(self) -> None:
        try:
            record = self.api.dispense(self.disp_encounter_id.value())
        except ApiError as e:
            self.disp_msg.setText(f"发药失败（{e.status_code}）：{e.detail}")
            return
        self.disp_msg.setText(
            f"发药成功：记录 {record['id']}，就诊 {record['encounter_id']}（{record['status']}）"
        )
        self.return_dispense_id.setValue(record["id"])

    def _return_dispense(self) -> None:
        try:
            record = self.api.return_dispense(self.return_dispense_id.value())
        except ApiError as e:
            self.return_msg.setText(f"退药失败（{e.status_code}）：{e.detail}")
            return
        self.return_msg.setText(
            f"退药成功：记录 {record['id']}（{record['status']}），库存已回补"
        )

    # ---------- 库存 ----------
    def _build_stock_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        refresh = QPushButton("刷新库存")
        refresh.clicked.connect(self._load_stocks)
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)

        self.stock_table = QTableWidget(0, 6)
        self.stock_table.setHorizontalHeaderLabels(
            ["ID", "药品 ID", "批次", "效期", "数量", "货位"]
        )
        layout.addWidget(self.stock_table)

        self.stock_msg = QLabel("")
        self.stock_msg.setWordWrap(True)
        layout.addWidget(self.stock_msg)
        return page

    def _load_stocks(self) -> None:
        try:
            stocks = self.api.list_stocks()
        except ApiError as e:
            self.stock_msg.setText(f"加载库存失败：{e.detail}")
            return
        self.stock_table.setRowCount(len(stocks))
        for row, stock in enumerate(stocks):
            self.stock_table.setItem(row, 0, QTableWidgetItem(str(stock["id"])))
            self.stock_table.setItem(row, 1, QTableWidgetItem(str(stock["drug_id"])))
            self.stock_table.setItem(row, 2, QTableWidgetItem(stock["batch_no"]))
            self.stock_table.setItem(row, 3, QTableWidgetItem(stock["expiry"]))
            self.stock_table.setItem(row, 4, QTableWidgetItem(str(stock["quantity"])))
            self.stock_table.setItem(row, 5, QTableWidgetItem(stock.get("location") or ""))
        self.stock_msg.setText(f"共 {len(stocks)} 个库存批次")
