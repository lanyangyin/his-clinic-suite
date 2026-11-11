"""患者信息侧卡：独立显示当前患者，不承担导航。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class PatientInfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("patientInfoPanel")
        self.setMinimumWidth(210)
        self.setMaximumWidth(280)
        self.setStyleSheet(
            "#patientInfoPanel{background:#ffffff;border:1px solid #dbe7f3;border-radius:8px;}"
            "#patientInfoPanel QLabel{color:#334155;font-size:12px;}"
            "#patientInfoPanel QLabel#title{font-size:15px;font-weight:bold;color:#1e3a5f;}"
            "#patientInfoPanel QLabel#allergy{color:#f87171;font-weight:bold;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.title = QLabel("当前患者")
        self.title.setObjectName("title")
        self.name = QLabel("未选择")
        self.name.setStyleSheet("font-size:16px;font-weight:bold;color:#0f172a;")
        self.demo = QLabel("")
        self.allergy = QLabel("")
        self.allergy.setObjectName("allergy")
        self.allergy.setWordWrap(True)
        self.encounter = QLabel("")
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.phone = QLabel("")
        self.extra = QLabel("")
        self.extra.setWordWrap(True)
        for widget in (
            self.title, self.name, self.demo, self.allergy,
            self.encounter, self.status, self.phone, self.extra,
        ):
            layout.addWidget(widget)
        layout.addStretch(1)
        self.patient_id = 0
        self.encounter_id = 0

    def set_patient(
        self,
        patient: dict | None,
        encounter_id: int | None = None,
        status: str = "",
        extra: str = "",
    ) -> None:
        if not patient:
            self.clear()
            return
        self.patient_id = int(patient.get("id") or 0)
        self.encounter_id = int(encounter_id or patient.get("encounter_id") or 0)
        gender = {"male": "男", "female": "女"}.get(patient.get("gender"), "不详")
        age = patient.get("age")
        self.name.setText(str(patient.get("name") or "未命名"))
        self.demo.setText(
            f"{gender} / {age if age is not None else '—'}岁  "
            f"{patient.get('patient_no') or ''}"
        )
        allergy = patient.get("allergy_label") or "过敏史不详"
        self.allergy.setText(
            f"⚠ {allergy}"
            if allergy not in ("无过敏史", "不详", "过敏史不详")
            else allergy
        )
        self.encounter.setText(
            f"就诊：{self.encounter_id}" if self.encounter_id else "就诊：未接诊"
        )
        self.status.setText(f"状态：{status}" if status else "")
        self.phone.setText(f"电话：{patient.get('phone') or '—'}")
        self.extra.setText(extra)
        self.extra.setVisible(bool(extra))

    def clear(self) -> None:
        self.patient_id = 0
        self.encounter_id = 0
        self.name.setText("未选择")
        self.demo.setText("")
        self.allergy.setText("")
        self.encounter.setText("")
        self.status.setText("")
        self.phone.setText("")
        self.extra.setText("")
        self.extra.setVisible(False)
