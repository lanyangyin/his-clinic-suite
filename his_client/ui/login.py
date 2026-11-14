"""登录对话框：服务器 IP/端口分开记忆，账号记忆，密码不保存。"""
import json
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from his_client.api import ApiClient, ApiError
from his_client.config import ClientConfig
from his_client.ui.theme import apply_theme, colors, register_theme_listener
from his_client.ui.window_theme import apply_light_titlebar


def _split_server(url: str) -> tuple[str, int, str]:
    raw = (url or "").strip()
    if not raw:
        return "127.0.0.1", 8000, "http"
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    return (
        parsed.hostname or "127.0.0.1",
        parsed.port or 8000,
        parsed.scheme or "http",
    )


class LoginDialog(QDialog):
    def __init__(self, config: ClientConfig, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.setWindowTitle("HIS 客户端登录")
        self.setMinimumWidth(460)
        self.config = config
        self.api: ApiClient | None = None
        self.user: dict | None = None
        self.history_path = Path(config.history_path or Path.cwd() / "login_history.json")
        self.history = self._load_history()

        layout = QVBoxLayout(self)
        title = QLabel("HIS 门诊部客户端")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 600; margin: 6px 0;")
        layout.addWidget(title)

        host, port, self.scheme = _split_server(config.server_url)
        form = QFormLayout()
        self.host_combo = QComboBox()
        self.host_combo.setEditable(True)
        self.host_combo.setInsertPolicy(QComboBox.NoInsert)
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setInsertPolicy(QComboBox.NoInsert)
        self.port_combo.setValidator(QIntValidator(1, 65535, self))
        self.username_combo = QComboBox()
        self.username_combo.setEditable(True)
        self.username_combo.setInsertPolicy(QComboBox.NoInsert)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)

        self._fill_combo(self.host_combo, self.history.get("hosts", []), str(host))
        self._fill_combo(self.port_combo, self.history.get("ports", []), str(port))
        self._fill_combo(self.username_combo, self.history.get("usernames", []), "")

        form.addRow("服务器 IP / 主机名", self.host_combo)
        form.addRow("端口", self.port_combo)
        form.addRow("账号", self.username_combo)
        form.addRow("密码", self.password_edit)
        layout.addLayout(form)

        self.hint = QLabel("IP、端口、账号会记住；密码不保存。")
        self.hint.setStyleSheet(f"color: {colors()['muted']};")
        layout.addWidget(self.hint)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #b91c1c;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("登录")
        buttons.button(QDialogButtonBox.Cancel).setText("退出")
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.password_edit.returnPressed.connect(self._try_login)
        register_theme_listener(self)

    def apply_theme(self) -> None:
        self.hint.setStyleSheet(f"color: {colors()['muted']};")
        self.error_label.setStyleSheet(f"color: {colors()['danger']};")
        self.update()

    def _fill_combo(self, combo: QComboBox, values: list, current: str) -> None:
        combo.clear()
        for value in values:
            text = str(value).strip()
            if text and combo.findText(text) < 0:
                combo.addItem(text)
        if current and combo.findText(current) < 0:
            combo.addItem(current)
        if values:
            # 最近使用的值优先；配置值仍保留在下拉历史里
            combo.setCurrentIndex(0)
        elif current:
            combo.setCurrentText(current)

    def _load_history(self) -> dict:
        empty = {"hosts": [], "ports": [], "usernames": []}
        if not self.config.remember_login:
            return empty
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return empty
        if not isinstance(data, dict):
            return empty
        limit = max(1, min(50, int(self.config.remember_limit)))
        return {
            key: [str(item) for item in data.get(key, []) if str(item).strip()][:limit]
            for key in empty
        }

    def _save_history(self, host: str, port: str, username: str) -> None:
        if not self.config.remember_login:
            return
        limit = max(1, min(50, int(self.config.remember_limit)))
        for key, value in (
            ("hosts", host),
            ("ports", port),
            ("usernames", username),
        ):
            values = [str(item) for item in self.history.get(key, []) if str(item) != value]
            self.history[key] = [value] + values
            self.history[key] = self.history[key][:limit]
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.history_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self.history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.history_path)
        except OSError:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_light_title_done", False):
            self._light_title_done = True
            apply_light_titlebar(self)

    def _try_login(self) -> None:
        host = self.host_combo.currentText().strip()
        port_text = self.port_combo.currentText().strip()
        username = self.username_combo.currentText().strip()
        password = self.password_edit.text()
        if not host or not port_text or not username or not password:
            self.error_label.setText("请填写服务器 IP、端口、账号和密码")
            return
        if "://" in host:
            parsed = urlparse(host)
            host = parsed.hostname or ""
            if parsed.port and not port_text:
                port_text = str(parsed.port)
            if parsed.scheme:
                self.scheme = parsed.scheme
        try:
            port = int(port_text)
        except ValueError:
            self.error_label.setText("端口必须是数字")
            return
        if not 1 <= port <= 65535:
            self.error_label.setText("端口必须在 1-65535 之间")
            return
        host_part = f"[{host}]" if ":" in host and not host.startswith("[") else host
        server = f"{self.scheme}://{host_part}:{port}"

        self.error_label.setText("正在连接服务器…")
        client = ApiClient(server, username, password, timeout=self.config.timeout)
        try:
            user = client.me()
        except ApiError as e:
            self.error_label.setText(f"登录失败（{e.status_code}）：{e.detail}")
            return

        self._save_history(host, str(port), username)
        self.api = client
        self.user = user
        self.accept()
