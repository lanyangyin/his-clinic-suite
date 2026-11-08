"""离屏渲染客户端界面截图（验证布局用，不参与业务）。"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from his_client.api import ApiClient  # noqa: E402
from his_client.config import load_config  # noqa: E402
from his_client.ui.login import LoginDialog  # noqa: E402
from his_client.ui.main_window import MainWindow  # noqa: E402

out = Path("docs/screenshots")
out.mkdir(parents=True, exist_ok=True)

app = QApplication([])

# 离屏渲染需要显式加载中文字体（真实 Windows 桌面会自动使用系统字体）
for font_path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
    if Path(font_path).exists():
        QFontDatabase.addApplicationFont(font_path)
app.setFont(QFont("Microsoft YaHei", 10))

login = LoginDialog(load_config())
login.show()
app.processEvents()
login.grab().save(str(out / "login.png"))

window = MainWindow(
    ApiClient("http://127.0.0.1:8000"),
    {"username": "cashier", "display_name": "收费员", "role": "cashier"},
)
window.resize(1100, 720)
window.show()
app.processEvents()
window.grab().save(str(out / "cashier.png"))

for role, title in (
    ("doctor", "doctor"),
    ("pharmacist", "pharmacy"),
    ("nurse", "nurse"),
):
    win = MainWindow(
        ApiClient("http://127.0.0.1:8000"),
        {"username": role, "display_name": role, "role": role},
    )
    win.resize(1100, 720)
    win.show()
    app.processEvents()
    win.grab().save(str(out / f"{title}.png"))

print("screenshots:", sorted(p.name for p in out.glob("*.png")))
