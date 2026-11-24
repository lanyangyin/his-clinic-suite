"""处方明细行内编辑：待审处方可改用法/频次/途径/天数，可删明细。"""
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from his_client.api import ApiClient, ApiError


class PrescriptionEditDialog(QDialog):
    def __init__(self, api: ApiClient, encounter_id: int, prescription_id: int, parent=None):
        super().__init__(parent)
        self.api = api
        self.encounter_id = encounter_id
        self.prescription_id = prescription_id
        self.rows: list[dict] = []
        self.setWindowTitle("处方明细编辑")
        self.resize(720, 460)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["药品", "数量", "用法", "状态"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._select)
        layout.addWidget(self.table, 1)

        form = QFormLayout()
        self.dosage = QLineEdit()
        self.frequency = QLineEdit()
        self.route = QLineEdit()
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 999)
        form.addRow("数量", self.quantity)
        form.addRow("每次剂量", self.dosage)
        form.addRow("频次", self.frequency)
        form.addRow("途径", self.route)
        form.addRow("天数", self.days)
        layout.addLayout(form)

        actions = QHBoxLayout()
        save = QPushButton("保存用法")
        save.clicked.connect(self._save)
        delete = QPushButton("删除选中明细")
        delete.clicked.connect(self._delete)
        actions.addWidget(save)
        actions.addWidget(delete)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.msg = QLineEdit()
        self.msg.setReadOnly(True)
        layout.addWidget(self.msg)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._load()

    def _load(self) -> None:
        if not self.encounter_id:
            return
        try:
            all_rows = self.api.list_prescriptions(self.encounter_id)
        except ApiError as e:
            self.msg.setText(f"加载失败：{e.detail}")
            return
        self.rows = [
            row for row in all_rows if row.get("prescription_id") == self.prescription_id
        ]
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            values = [
                row.get("drug_name") or "",
                str(row.get("quantity") or ""),
                " ".join(
                    str(x)
                    for x in (row.get("dosage"), row.get("frequency"), row.get("route"))
                    if x
                )
                or "—",
                row.get("prescription_status") or "",
            ]
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        self.msg.setText(f"共 {len(self.rows)} 条明细；只有待审处方可改用法")

    def _select(self, row: int, _col: int) -> None:
        if not 0 <= row < len(self.rows):
            return
        item = self.rows[row]
        self.dosage.setText(item.get("dosage") or "")
        self.frequency.setText(item.get("frequency") or "")
        self.route.setText(item.get("route") or "")
        self.days.setValue(int(item.get("days") or 1))
        self.quantity.setValue(int(item.get("quantity") or 1))

    def _save(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self.rows):
            self.msg.setText("请先选择一条明细")
            return
        item = self.rows[row]
        try:
            self.api.update_prescription_item(
                self.encounter_id,
                item["id"],
                {
                    "quantity": self.quantity.value(),
                    "dosage": self.dosage.text().strip(),
                    "frequency": self.frequency.text().strip(),
                    "route": self.route.text().strip(),
                    "days": self.days.value(),
                },
            )
        except ApiError as e:
            self.msg.setText(f"保存失败：{e.detail}")
            return
        self.msg.setText("已保存")
        self._load()

    def _delete(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self.rows):
            self.msg.setText("请先选择一条明细")
            return
        if QMessageBox.question(self, "确认", "删除选中的处方明细？") != QMessageBox.Yes:
            return
        try:
            self.api.delete_prescription(self.encounter_id, self.rows[row]["id"])
        except ApiError as e:
            self.msg.setText(f"删除失败：{e.detail}")
            return
        self.msg.setText("已删除")
        self._load()
