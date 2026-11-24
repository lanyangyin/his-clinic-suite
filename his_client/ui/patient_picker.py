"""患者搜索选择器：按姓名/电话检索，选中后回填患者 ID。"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget

from his_client.api import ApiClient, ApiError


class PatientPicker(QWidget):
    patient_selected = Signal(dict)

    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.patients: list[dict] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("姓名 / 电话，回车查询")
        self.keyword.returnPressed.connect(self.search)
        self.result = QComboBox()
        self.result.setMinimumWidth(260)
        self.result.currentIndexChanged.connect(self._choose)
        button = QPushButton("查患者")
        button.clicked.connect(self.search)
        layout.addWidget(self.keyword, 1)
        layout.addWidget(button)
        layout.addWidget(self.result, 1)
        self.message = None

    def search(self) -> None:
        keyword = self.keyword.text().strip()
        if not keyword:
            return
        try:
            rows = self.api.list_patients(name=keyword)
            if not rows:
                rows = self.api.list_patients(phone=keyword)
        except ApiError as e:
            self.result.clear()
            self.result.addItem(f"查询失败：{e.detail}", None)
            return
        self.patients = rows
        self.result.blockSignals(True)
        self.result.clear()
        for patient in rows:
            gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "—")
            age = patient.get("age")
            age_text = f"{age}岁" if age is not None else "年龄不详"
            phone = patient.get("phone") or ""
            phone_text = f" · {phone[-4:]}" if phone else ""
            self.result.addItem(
                f"{patient.get('patient_no') or patient['id']} {patient['name']} "
                f"{gender}/{age_text}{phone_text}",
                patient,
            )
        if not rows:
            self.result.addItem("未找到患者", None)
        self.result.blockSignals(False)
        if rows:
            self.result.setCurrentIndex(0)
            self._choose(0)

    def _choose(self, index: int) -> None:
        patient = self.result.itemData(index) if index >= 0 else None
        if patient:
            self.patient_selected.emit(patient)

    def set_patient(self, patient: dict | None) -> None:
        if patient:
            self.result.blockSignals(True)
            self.result.clear()
            self.result.addItem(patient.get("name") or f"ID {patient['id']}", patient)
            self.result.blockSignals(False)
