"""全局患者条：当前患者、过敏、就诊、状态。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


class PatientBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("patientBanner")
        self.setStyleSheet(
            "#patientBanner{background:#eef2ff;border-bottom:2px solid #6366f1;}"
            "#patientBanner QLabel{font-size:13px;color:#1e293b;}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(16)
        self.name = QLabel("未选择患者")
        self.name.setStyleSheet("font-weight:bold;font-size:15px;color:#0f172a;")
        self.demo = QLabel("")
        self.allergy = QLabel("")
        self.allergy.setStyleSheet("color:#b91c1c;font-weight:bold;")
        self.encounter = QLabel("")
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for widget in (self.name, self.demo, self.allergy, self.encounter):
            layout.addWidget(widget)
        layout.addStretch(1)
        layout.addWidget(self.status)
        self.patient_id = 0
        self.encounter_id = 0

    def set_patient(self, patient: dict | None, encounter_id: int | None = None, status: str = "") -> None:
        if not patient:
            self.clear()
            return
        self.patient_id = int(patient.get("id") or 0)
        self.encounter_id = int(encounter_id or patient.get("encounter_id") or 0)
        gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "性别不详")
        age = patient.get("age")
        age_text = f"{age}岁" if age is not None else "年龄不详"
        number = patient.get("patient_no") or (f"ID {patient['id']}" if patient.get("id") else "")
        self.name.setText(str(patient.get("name") or "未命名"))
        self.demo.setText(f"{gender} / {age_text} / {number}")
        allergy = patient.get("allergy_label") or "过敏史不详"
        self.allergy.setText(
            f"⚠ {allergy}"
            if allergy not in ("无过敏史", "不详", "过敏史不详")
            else allergy
        )
        self.encounter.setText(f"就诊 {self.encounter_id}" if self.encounter_id else "未接诊")
        self.status.setText(status)
        self.status.setStyleSheet(
            "color:#15803d;font-weight:bold" if "可" in status or "已收费" in status
            else "color:#b91c1c;font-weight:bold" if status and ("未" in status or "禁" in status)
            else "color:#475569"
        )

    def set_status(self, status: str) -> None:
        self.status.setText(status)

    def clear(self) -> None:
        self.patient_id = 0
        self.encounter_id = 0
        self.name.setText("未选择患者")
        self.demo.setText("")
        self.allergy.setText("")
        self.encounter.setText("")
        self.status.setText("")
