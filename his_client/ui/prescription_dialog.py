"""双击药品目录后的快速用法确认。"""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from his_client.ui.theme import apply_theme

USAGES = (
    ("口服 bid", {"route": "口服", "frequency": "bid", "dosage": ""}),
    ("口服 tid", {"route": "口服", "frequency": "tid", "dosage": ""}),
    ("口服 qd", {"route": "口服", "frequency": "qd", "dosage": ""}),
    ("静滴 qd", {"route": "静滴", "frequency": "qd", "dosage": ""}),
    ("静滴 bid", {"route": "静滴", "frequency": "bid", "dosage": ""}),
    ("肌注 qd", {"route": "肌注", "frequency": "qd", "dosage": ""}),
    ("外用 bid", {"route": "外用", "frequency": "bid", "dosage": ""}),
    ("雾化 bid", {"route": "雾化", "frequency": "bid", "dosage": ""}),
)


class PrescriptionQuickDialog(QDialog):
    def __init__(self, drug: dict, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.setWindowTitle("加入处方")
        self.setMinimumWidth(380)
        self.drug = drug
        layout = QVBoxLayout(self)
        title = QLabel(f"{drug.get('name')}  {drug.get('spec') or ''}")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        layout.addWidget(title)
        price = float(drug.get("base_price") or 0)
        form = QFormLayout()
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 100)
        self.usage = QComboBox()
        for label, data in USAGES:
            self.usage.addItem(label, data)
        default = "静滴 qd" if "注射" in (drug.get("dosage_form") or "") else "口服 bid"
        self.usage.setCurrentIndex(max(0, self.usage.findText(default)))
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(3)
        self.amount = QLabel(f"{price:.2f}")
        form.addRow("数量", self.quantity)
        form.addRow("用法用量", self.usage)
        form.addRow("天数", self.days)
        form.addRow("单价", QLabel(f"{price:.2f} 元"))
        form.addRow("金额", self.amount)
        layout.addLayout(form)
        self.quantity.valueChanged.connect(self._update_amount)
        layout.addWidget(
            QLabel("提交后会立即写入处方；可在下方处方表删除未收费项目。")
        )
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("加入处方")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_amount(self) -> None:
        price = float(self.drug.get("base_price") or 0)
        self.amount.setText(f"{price * self.quantity.value():.2f}")

    def payload(self) -> dict:
        usage = self.usage.currentData() or {}
        return {
            "drug_id": int(self.drug["id"]),
            "quantity": self.quantity.value(),
            "dosage": usage.get("dosage") or "",
            "frequency": usage.get("frequency") or "",
            "route": usage.get("route") or "",
            "days": self.days.value(),
        }
