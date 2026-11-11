"""登录对话框：服务器地址 + 账号密码，调用 /auth/me 校验。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from his_client.api import ApiClient, ApiError
from his_client.config import ClientConfig
from his_client.ui.theme import apply_theme
from his_client.ui.window_theme import apply_light_titlebar


class LoginDialog(QDialog):
    def __init__(self, config: ClientConfig, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.setWindowTitle("HIS 客户端登录")
        self.setMinimumWidth(380)
        self.api: ApiClient | None = None
        self.user: dict | None = None

        layout = QVBoxLayout(self)
        title = QLabel("HIS 门诊部客户端")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 600; margin: 6px 0;")
        layout.addWidget(title)

        form = QFormLayout()
        self.server_edit = QLineEdit(config.server_url)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("服务器地址", self.server_edit)
        form.addRow("账号", self.username_edit)
        form.addRow("密码", self.password_edit)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #b91c1c;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("登录")
        buttons.button(QDialogButtonBox.Cancel).setText("退出")
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_light_title_done", False):
            self._light_title_done = True
            apply_light_titlebar(self)

    def _try_login(self) -> None:
        server = self.server_edit.text().strip()
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not server or not username or not password:
            self.error_label.setText("请填写服务器地址、账号和密码")
            return

        self.error_label.setText("正在连接服务器…")
        client = ApiClient(server, username, password)
        try:
            user = client.me()
        except ApiError as e:
            self.error_label.setText(f"登录失败（{e.status_code}）：{e.detail}")
            return

        self.api = client
        self.user = user
        self.accept()
