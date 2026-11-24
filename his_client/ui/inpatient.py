"""住院工作站：在院列表、医嘱查看、出院。"""
from PySide6.QtWidgets import (
    QFormLayout,
    QLineEdit,
    QGroupBox,
    QHBoxLayout,
    QSpinBox,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme


class InpatientWidget(QWidget):
    def __init__(self, api: ApiClient, role: str = "doctor", parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.role = role
        self.rows: list[dict] = []
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        title = QLabel("住院工作站")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        refresh = QPushButton("刷新在院")
        refresh.clicked.connect(self._load)
        discharge = QPushButton("办理出院")
        discharge.clicked.connect(self._discharge)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(refresh)
        if role in ("doctor", "admin"):
            top.addWidget(discharge)
        layout.addLayout(top)
        if role == "admin":
            admit_box = QGroupBox("入院登记")
            admit_form = QFormLayout(admit_box)
            self.admit_patient = QSpinBox()
            self.admit_patient.setRange(0, 100_000_000)
            self.admit_doctor = QSpinBox()
            self.admit_doctor.setRange(0, 100_000_000)
            self.admit_bed = QSpinBox()
            self.admit_bed.setRange(0, 100_000_000)
            admit_btn = QPushButton("办理入院")
            admit_btn.clicked.connect(self._admit)
            admit_form.addRow("患者 ID", self.admit_patient)
            admit_form.addRow("医生 ID", self.admit_doctor)
            admit_form.addRow("床位 ID", self.admit_bed)
            admit_form.addRow("", admit_btn)
            layout.addWidget(admit_box)
        if role in ("doctor", "admin"):
            takehome_box = QGroupBox("出院带药")
            takehome_form = QFormLayout(takehome_box)
            self.takehome_drug = QSpinBox()
            self.takehome_drug.setRange(0, 100_000_000)
            self.takehome_qty = QSpinBox()
            self.takehome_qty.setRange(1, 10000)
            self.takehome_directions = QLineEdit()
            self.takehome_directions.setPlaceholderText("用法用量")
            takehome_btn = QPushButton("添加带药")
            takehome_btn.clicked.connect(self._add_takehome)
            takehome_form.addRow("药品 ID", self.takehome_drug)
            takehome_form.addRow("数量", self.takehome_qty)
            takehome_form.addRow("用法", self.takehome_directions)
            takehome_form.addRow("", takehome_btn)
            layout.addWidget(takehome_box)
        splitter = QSplitter(Qt.Vertical)
        self.admission_table = QTableWidget(0, 5)
        self.admission_table.setHorizontalHeaderLabels(
            ["住院ID", "患者ID", "医生ID", "床位ID", "状态"]
        )
        self.admission_table.horizontalHeader().setStretchLastSection(True)
        self.admission_table.cellClicked.connect(self._select)
        splitter.addWidget(self.admission_table)
        self.order_table = QTableWidget(0, 5)
        self.order_table.setHorizontalHeaderLabels(
            ["医嘱ID", "药品", "类型", "数量", "状态"]
        )
        self.order_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.order_table)
        splitter.setSizes([320, 240])
        layout.addWidget(splitter, 1)
        self.msg = QLabel("")
        layout.addWidget(self.msg)
        self._load()

    def _load(self) -> None:
        try:
            self.rows = self.api.list_inpatient_admissions()
        except ApiError as e:
            self.msg.setText(f"加载失败：{e.detail}")
            return
        self.admission_table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            values = [
                row.get("id"), row.get("patient_id"), row.get("doctor_id"),
                row.get("bed_id"),
                {"in": "在院", "discharged": "已出院"}.get(row.get("status"), row.get("status")),
            ]
            for j, value in enumerate(values):
                self.admission_table.setItem(i, j, QTableWidgetItem(str(value)))
        self.msg.setText(f"共 {len(self.rows)} 条住院记录")

    def _select(self, row: int, _col: int) -> None:
        if not 0 <= row < len(self.rows):
            return
        try:
            orders = self.api.list_inpatient_orders(self.rows[row]["id"])
        except ApiError as e:
            self.msg.setText(f"医嘱加载失败：{e.detail}")
            return
        self.order_table.setRowCount(len(orders))
        for i, order in enumerate(orders):
            values = [
                order.get("id"), order.get("drug_name") or "",
                order.get("order_type"), order.get("quantity"), order.get("status"),
            ]
            for j, value in enumerate(values):
                self.order_table.setItem(i, j, QTableWidgetItem(str(value)))

    def _add_takehome(self) -> None:
        row = self.admission_table.currentRow()
        if not 0 <= row < len(self.rows):
            self.msg.setText("请先选择住院记录")
            return
        drug_id = self.takehome_drug.value()
        if not drug_id:
            self.msg.setText("请填写药品 ID")
            return
        try:
            self.api.create_discharge_medication(
                self.rows[row]["id"], drug_id, self.takehome_qty.value(),
                self.takehome_directions.text().strip(),
            )
        except ApiError as e:
            self.msg.setText(f"带药保存失败：{e.detail}")
            return
        self.msg.setText("出院带药已保存")

    def _admit(self) -> None:
        patient_id = self.admit_patient.value()
        doctor_id = self.admit_doctor.value()
        bed_id = self.admit_bed.value()
        if not patient_id or not doctor_id or not bed_id:
            self.msg.setText("请填写患者、医生、床位 ID")
            return
        try:
            self.api.create_inpatient_admission(patient_id, doctor_id, bed_id)
        except ApiError as e:
            self.msg.setText(f"入院失败：{e.detail}")
            return
        self._load()
        self.msg.setText("入院办理完成")

    def _discharge(self) -> None:
        row = self.admission_table.currentRow()
        if not 0 <= row < len(self.rows):
            self.msg.setText("请先选择住院记录")
            return
        try:
            self.api.discharge_inpatient(self.rows[row]["id"])
        except ApiError as e:
            self.msg.setText(f"出院失败：{e.detail}")
            return
        self._load()
        self.msg.setText("已办理出院")
