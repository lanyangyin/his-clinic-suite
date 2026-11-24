"""患者合并对话框：管理员提交申请，院长可直接合并。"""
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from his_client.api import ApiClient, ApiError


class PatientMergeDialog(QDialog):
    def __init__(self, api: ApiClient, role: str, source_id: int | None = None, parent=None):
        super().__init__(parent)
        self.api = api
        self.role = role
        self.setWindowTitle("患者档案合并")
        self.resize(460, 240)
        layout = QVBoxLayout(self)
        hint = QLabel(
            "源档案将被并入目标档案；管理员提交申请，院长审批后执行。"
            if role != "director"
            else "院长可直接执行合并；合并后源档案重定向到目标。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        self.source = QSpinBox()
        self.source.setRange(0, 100_000_000)
        self.source.setSpecialValueText("请输入源患者 ID")
        if source_id:
            self.source.setValue(source_id)
        self.target = QSpinBox()
        self.target.setRange(0, 100_000_000)
        self.target.setSpecialValueText("请输入目标患者 ID")
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("合并原因（必填）")
        form.addRow("源患者 ID", self.source)
        form.addRow("目标患者 ID", self.target)
        form.addRow("原因", self.reason)
        layout.addLayout(form)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        layout.addWidget(self.msg)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("提交合并")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self) -> None:
        source_id = self.source.value()
        target_id = self.target.value()
        reason = self.reason.text().strip()
        if not source_id or not target_id:
            self.msg.setText("请输入源患者和目标患者 ID")
            return
        if not reason:
            self.msg.setText("请填写合并原因")
            return
        try:
            if self.role == "director":
                self.api.merge_patient_direct(source_id, target_id, reason)
                self.msg.setText("合并完成")
            else:
                self.api.create_patient_merge_request(source_id, target_id, reason)
                self.msg.setText("合并申请已提交，等待院长审批")
        except ApiError as e:
            self.msg.setText(f"提交失败（{e.status_code}）：{e.detail}")
            return
        self.accept()
