"""管理员：医保/短信/企业微信集成地址配置。"""
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from his_client.api import ApiClient, ApiError
from his_client.ui.theme import apply_theme


class IntegrationConfigWidget(QWidget):
    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.api = api
        self.fields: dict[str, QLineEdit] = {}
        layout = QVBoxLayout(self)
        title = QLabel("集成配置")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        layout.addWidget(title)
        hint = QLabel("只保存在本系统；真实医保/短信/企业微信凭据由对应平台提供。")
        hint.setStyleSheet("color:#64748b;")
        layout.addWidget(hint)
        form = QFormLayout()
        layout.addLayout(form)
        self.form = form
        save = QPushButton("保存")
        save.clicked.connect(self._save)
        layout.addWidget(save)
        self.msg = QLabel("")
        layout.addWidget(self.msg)
        self._load()

    def _load(self) -> None:
        try:
            rows = self.api.list_integrations()
        except ApiError as e:
            self.msg.setText(f"加载失败（{e.status_code}）：{e.detail}")
            return
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields = {}
        for row in rows:
            field = QLineEdit(row.get("value") or "")
            field.setPlaceholderText("未配置" if not row.get("configured") else "")
            self.fields[row["key"]] = field
            self.form.addRow(row.get("label") or row["key"], field)
        self.msg.setText("已加载；留空表示不使用该集成")

    def _save(self) -> None:
        values = {key: field.text().strip() for key, field in self.fields.items()}
        try:
            self.api.set_integrations(values)
        except ApiError as e:
            self.msg.setText(f"保存失败（{e.status_code}）：{e.detail}")
            return
        self.msg.setText("已保存")
        self._load()
