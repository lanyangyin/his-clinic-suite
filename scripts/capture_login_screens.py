"""为验收报告采集各角色真实登录框截图（不启动完整业务窗口）。"""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from his_client.config import ClientConfig  # noqa: E402
from his_client.ui.login import LoginDialog  # noqa: E402

ROLES = {
    "cashier": ("cashier", "cashier123"),
    "doctor": ("doctor", "doctor123"),
    "nurse": ("nurse", "nurse123"),
    "pharmacy": ("pharmacist", "pharm123"),
    "warehouse": ("warehouse", "warehouse123"),
    "lab": ("lab", "lab123"),
    "radiology": ("radiology", "rad123"),
    "treatment": ("treatment", "treatment123"),
    "tcm": ("doctor", "doctor123"),
    "archive": ("archive", "archive123"),
    "director": ("director", "director123"),
    "retail": ("pharmacist", "pharm123"),
    "cashier_backoffice": ("cashier", "cashier123"),
    "joint": ("cashier", "cashier123"),
    "overall": ("admin", "admin123"),
    "insurance": ("admin", "admin123"),
    "hr": ("hr_gui", "hr123"),
    "surgery": ("surgery", "surgery123"),
}

app = QApplication(sys.argv)
QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
app.setFont(QFont("Microsoft YaHei", 10))
out_root = ROOT / "docs" / "acceptance_20261124" / "screenshots"
for dept, (user, password) in ROLES.items():
    dialog = LoginDialog(ClientConfig(server_url="http://127.0.0.1:8001", timeout=20, remember_login=False))
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    dialog.host_combo.setCurrentText("127.0.0.1")
    dialog.port_combo.setCurrentText("8001")
    dialog.username_combo.setCurrentText(user)
    dialog.password_edit.setFocus()
    QTest.keyClicks(dialog.password_edit, password)
    app.processEvents()
    QTest.qWait(250)
    out = out_root / dept / "login_filled.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    dialog.grab().save(str(out), "PNG")
    print(dept, user, dialog.grab().size().toTuple())
    dialog.reject()
    dialog.deleteLater()
    app.processEvents()
