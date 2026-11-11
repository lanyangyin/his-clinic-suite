"""收费面板：门诊工作站/药房工作站共用（现金/微信/支付宝/POS/医保卡）。"""
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.config import load_config
from his_client.labels import zh


class PaymentPanel(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.insurance_enabled = load_config().insurance_enabled
        layout = QVBoxLayout(self)

        box = QGroupBox("就诊费用")
        box_layout = QVBoxLayout(box)
        scan_row = QHBoxLayout()
        self.scan_code = QLineEdit()
        self.scan_code.setPlaceholderText("扫处方条码（RX.../中药处方码），回车带出")
        self.scan_code.returnPressed.connect(self._scan_barcode)
        scan_btn = QPushButton("扫码带出")
        scan_btn.clicked.connect(self._scan_barcode)
        self.scan_status = QLabel("")
        self.scan_status.setWordWrap(True)
        scan_row.addWidget(self.scan_code)
        scan_row.addWidget(scan_btn)
        scan_row.addWidget(self.scan_status)
        box_layout.addLayout(scan_row)

        row = QHBoxLayout()
        self.encounter_id = QSpinBox()
        self.encounter_id.setRange(1, 10_000_000)
        query = QPushButton("查询费用")
        query.clicked.connect(self._load_charges)
        pay = QPushButton("收费")
        pay.clicked.connect(self._pay)
        row.addWidget(QLabel("就诊 ID"))
        row.addWidget(self.encounter_id)
        row.addWidget(query)
        row.addWidget(pay)
        box_layout.addLayout(row)

        method_row = QHBoxLayout()
        self.channel = QComboBox()
        channels = [
            ("现金", "cash"),
            ("微信支付", "wechat"),
            ("支付宝", "alipay"),
            ("POS 刷卡", "pos"),
        ]
        if self.insurance_enabled:
            channels.append(("医保卡", "insurance_card"))
        for label, value in channels:
            self.channel.addItem(label, value)
        self.auth_code = QLineEdit()
        self.auth_code.setPlaceholderText("付款码（微信/支付宝）")
        self.card_no = QLineEdit()
        self.card_no.setPlaceholderText("卡号/读卡返回值（POS）")
        method_row.addWidget(QLabel("支付方式"))
        method_row.addWidget(self.channel)
        method_row.addWidget(self.auth_code)
        method_row.addWidget(self.card_no)
        box_layout.addLayout(method_row)
        self.channel.currentIndexChanged.connect(self._update_payment_inputs)
        self._update_payment_inputs()

        self.charge_table = QTableWidget(0, 5)
        self.charge_table.setHorizontalHeaderLabels(["类型", "项目", "数量", "金额", "状态"])
        box_layout.addWidget(self.charge_table)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        box_layout.addWidget(self.message)
        layout.addWidget(box)
        layout.addStretch(1)

    def _update_payment_inputs(self) -> None:
        channel = self.channel.currentData() if hasattr(self, "channel") else "cash"
        self.auth_code.setEnabled(channel in ("wechat", "alipay"))
        self.card_no.setEnabled(channel in ("pos", "insurance_card"))

    def _scan_barcode(self) -> None:
        code = self.scan_code.text().strip()
        if not code:
            self.message.setText("请扫描处方条码")
            return
        try:
            row = self.api.resolve_prescription_barcode(code)
        except ApiError as e:
            self.message.setText(f"条码解析失败（{e.status_code}）：{e.detail}")
            return
        self.encounter_id.setValue(row["encounter_id"])
        self._load_charges()
        if row["is_paid"]:
            self.scan_status.setStyleSheet("color:#f87171;font-weight:bold")
            self.scan_status.setText(f"已收费：{row['patient_name']}，不能重复收费")
        else:
            self.scan_status.setStyleSheet("color:#86efac;font-weight:bold")
            self.scan_status.setText(
                f"未收费：{row['patient_name']}，待收 {row['pending_amount']:.2f} 元"
            )

    def _load_charges(self) -> None:
        encounter_id = self.encounter_id.value()
        try:
            charges = self.api.get_charges(encounter_id)
            summary = self.api.get_charge_summary(encounter_id)
        except ApiError as e:
            self.message.setText(f"查询失败（{e.status_code}）：{e.detail}")
            return
        self.charge_table.setRowCount(len(charges))
        for row, charge in enumerate(charges):
            values = [
                zh("charge_type", charge["charge_type"]),
                charge["item_name"],
                str(charge["quantity"]),
                f"{charge['amount']:.2f}",
                zh("charge_status", charge["status"]),
            ]
            for col, value in enumerate(values):
                self.charge_table.setItem(row, col, QTableWidgetItem(value))
        self.message.setText(
            f"待收 {summary['total_pending']:.2f} 元；已收 {summary['total_paid']:.2f} 元"
        )

    def _pay(self) -> None:
        try:
            payment = self.api.create_payment(
                self.encounter_id.value(),
                channel=self.channel.currentData(),
                auth_code=self.auth_code.text().strip(),
                card_no=self.card_no.text().strip(),
            )
        except ApiError as e:
            self.message.setText(f"收费失败（{e.status_code}）：{e.detail}")
            return
        self.message.setText(
            f"收费成功：单号 {payment['id']}，金额 {payment['amount']:.2f} 元，"
            + (
                f"医保 {payment['insurance_amount']:.2f}，自费 {payment['self_pay_amount']:.2f}，"
                if self.insurance_enabled
                else "实收 "
            )
            + f"方式 {zh('payment_channel', payment.get('channel'))}"
            + (
                f"，交易号 {payment['channel_trade_no']}"
                if payment.get("channel_trade_no")
                else ""
            )
        )
        self._load_charges()
