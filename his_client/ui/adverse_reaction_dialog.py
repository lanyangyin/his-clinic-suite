"""药物不良反应/换药记录对话框。"""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)


class AdverseReactionDialog(QDialog):
    def __init__(self, patient_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"药物反应 / 换药 · {patient_name}")
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.drug_name = QLineEdit()
        self.drug_name.setPlaceholderText("可疑药品，如 头孢曲松")
        self.reaction = QTextEdit()
        self.reaction.setPlaceholderText("症状、发生时间、生命体征变化")
        self.reaction.setFixedHeight(110)
        self.severity = QComboBox()
        self.severity.addItem("轻度", "mild")
        self.severity.addItem("中度", "moderate")
        self.severity.addItem("重度", "severe")
        self.severity.setCurrentIndex(1)
        self.action_taken = QTextEdit()
        self.action_taken.setPlaceholderText("已采取的措施：停药、抗过敏、吸氧、换药方案……")
        self.action_taken.setFixedHeight(90)
        self.action_taken.setPlainText("立即停药，评估生命体征，准备更换治疗方案。")
        form.addRow("可疑药品", self.drug_name)
        form.addRow("反应表现", self.reaction)
        form.addRow("严重程度", self.severity)
        form.addRow("已采取措施", self.action_taken)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Save).setText("记录并挂起就诊")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def payload(self) -> dict:
        return {
            "drug_name": self.drug_name.text().strip(),
            "reaction": self.reaction.toPlainText().strip(),
            "severity": self.severity.currentData(),
            "action_taken": self.action_taken.toPlainText().strip(),
            "pause_encounter": True,
        }
