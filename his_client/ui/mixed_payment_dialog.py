"""混合支付 / 折扣减免对话框。"""
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class MixedPaymentDialog(QDialog):
    def __init__(self, total: float, can_discount: bool, parent=None):
        super().__init__(parent)
        self.total = round(total, 2)
        self.setWindowTitle("混合支付 / 折扣")
        self.resize(420, 320)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"本次自费应收：{self.total:.2f} 元"))
        form = QFormLayout()
        self.cash = QDoubleSpinBox()
        self.cash.setRange(0, 999999)
        self.cash.setDecimals(2)
        self.wechat = QDoubleSpinBox()
        self.wechat.setRange(0, 999999)
        self.wechat.setDecimals(2)
        self.alipay = QDoubleSpinBox()
        self.alipay.setRange(0, 999999)
        self.alipay.setDecimals(2)
        self.discount = QDoubleSpinBox()
        self.discount.setRange(0, 999999)
        self.discount.setDecimals(2)
        self.discount.setEnabled(can_discount)
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("折扣原因（有折扣必填）")
        self.reason.setEnabled(can_discount)
        self.remain = QLabel("")
        form.addRow("现金", self.cash)
        form.addRow("微信", self.wechat)
        form.addRow("支付宝", self.alipay)
        form.addRow("折扣/减免", self.discount)
        form.addRow("折扣原因", self.reason)
        form.addRow("待分配", self.remain)
        layout.addLayout(form)
        for spin in (self.cash, self.wechat, self.alipay, self.discount):
            spin.valueChanged.connect(self._refresh)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("确认收款")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        paid = self.cash.value() + self.wechat.value() + self.alipay.value()
        target = round(self.total - self.discount.value(), 2)
        self.remain.setText(
            f"应收 {target:.2f}，已分配 {paid:.2f}，差额 {target - paid:.2f}"
        )

    def payload(self) -> dict:
        allocations = []
        for channel, spin in (
            ("cash", self.cash),
            ("wechat", self.wechat),
            ("alipay", self.alipay),
        ):
            if spin.value() > 0:
                allocations.append({"channel": channel, "amount": round(spin.value(), 2)})
        return {
            "allocations": allocations,
            "discount_amount": round(self.discount.value(), 2),
            "discount_reason": self.reason.text().strip(),
        }
