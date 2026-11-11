"""医生接诊时修改患者级过敏史/现存疾病，带修改原因。"""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from his_client.ui.theme import apply_theme
from his_client.ui.window_theme import apply_light_titlebar


class PatientClinicalDialog(QDialog):
    def __init__(self, patient: dict, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.patient = patient
        self.setWindowTitle(f"修改患者史 · {patient.get('name') or ''}")
        self.resize(520, 430)
        layout = QVBoxLayout(self)
        hint = QLabel("此处修改患者级档案，会影响以后所有就诊；保存会记录修改人、原因、旧值。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#b45309")
        layout.addWidget(hint)

        form = QFormLayout()
        self.allergy_status = QComboBox()
        for value, label in (
            ("unknown", "过敏史不详"),
            ("none", "无过敏史"),
            ("present", "有过敏史"),
        ):
            self.allergy_status.addItem(label, value)
        index = self.allergy_status.findData(patient.get("allergy_status") or "unknown")
        self.allergy_status.setCurrentIndex(max(0, index))
        self.allergy_detail = QLineEdit(patient.get("allergy_detail") or "")
        self.allergy_detail.setPlaceholderText("如 青霉素、头孢；有过敏史必填")
        self.special_history = QTextEdit()
        self.special_history.setPlainText(patient.get("special_history") or "")
        self.special_history.setPlaceholderText(
            "如 2型糖尿病 8 年；高血压 5 年；约3年前发现高血脂"
        )
        self.special_history.setFixedHeight(120)
        self.reason = QLineEdit("接诊核对患者史")
        self.reason.setPlaceholderText("修改原因，必填")
        form.addRow("过敏状态", self.allergy_status)
        form.addRow("过敏原", self.allergy_detail)
        form.addRow("现存疾病/既往史", self.special_history)
        form.addRow("修改原因", self.reason)
        layout.addLayout(form)

        self.error = QLabel("")
        self.error.setStyleSheet("color:#dc2626")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存并留痕")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if self.allergy_status.currentData() == "present" and not self.allergy_detail.text().strip():
            self.error.setText("有过敏史时必须填写过敏原")
            return
        if not self.reason.text().strip():
            self.error.setText("请填写修改原因")
            return
        self.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not getattr(self, "_light_title_done", False):
            self._light_title_done = True
            apply_light_titlebar(self)

    def payload(self) -> dict:
        return {
            "allergy_status": self.allergy_status.currentData(),
            "allergy_detail": self.allergy_detail.text().strip(),
            "special_history": self.special_history.toPlainText().strip(),
            "reason": self.reason.text().strip(),
        }
