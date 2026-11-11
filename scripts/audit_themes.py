r"""主题完整性审计：递归遍历全部工作站页签和弹窗。

用法：
    $env:HIS_THEME="dark"; .venv\Scripts\python.exe scripts\audit_themes.py
    $env:HIS_THEME="light"; .venv\Scripts\python.exe scripts\audit_themes.py

输出：build/theme_audit/<mode>/*.png 和控制台异常比例。
浅色模式检查大面积深色；深色模式检查大面积浅色。
"""
import os
import sys
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QInputDialog,
    QMessageBox,
    QTabWidget,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.config import ClientConfig  # noqa: E402
from his_client.ui.adverse_reaction_dialog import AdverseReactionDialog  # noqa: E402
from his_client.ui.archive import ArchiveWidget  # noqa: E402
from his_client.ui.cashier import CashierWidget  # noqa: E402
from his_client.ui.director import DirectorWidget  # noqa: E402
from his_client.ui.doctor import DoctorWidget  # noqa: E402
from his_client.ui.lab import LabWidget  # noqa: E402
from his_client.ui.login import LoginDialog  # noqa: E402
from his_client.ui.main_window import MainWindow  # noqa: E402
from his_client.ui.mixed_payment_dialog import MixedPaymentDialog  # noqa: E402
from his_client.ui.nurse import NurseWidget  # noqa: E402
from his_client.ui.patient360 import Patient360Widget  # noqa: E402
from his_client.ui.pharmacy import PharmacyWidget  # noqa: E402
from his_client.ui.surgery import SurgeryWidget  # noqa: E402
from his_client.ui.tcm import TcmWidget  # noqa: E402
from his_client.ui.treatment_room import TreatmentRoomWidget  # noqa: E402
from his_client.ui.theme import apply_theme  # noqa: E402

MODE = os.environ.get("HIS_THEME", "system")
OUT = ROOT / "build" / "theme_audit" / MODE
OUT.mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv)


def api(user: str, password: str) -> ApiClient:
    return ApiClient("http://127.0.0.1:8001", user, password)


def anomaly(path: Path) -> float:
    image = QImage(str(path)).scaled(240, 150)
    light = dark = 0
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if c.red() > 235 and c.green() > 235 and c.blue() > 235:
                light += 1
            if c.red() < 55 and c.green() < 55 and c.blue() < 55:
                dark += 1
    total = image.width() * image.height()
    return light / total if MODE == "dark" else dark / total


def capture(name: str, widget) -> None:
    widget.show()
    app.processEvents()
    app.processEvents()
    path = OUT / f"{name}.png"
    widget.grab().save(str(path))
    ratio = anomaly(path)
    flag = " <-- CHECK" if ratio > (0.18 if MODE == "dark" else 0.04) else ""
    print(f"{MODE:5} {name:36} {ratio:6.3f}{flag}")


def walk_tabs(name: str, widget) -> None:
    widget.resize(1366, 768)
    widget.show()
    app.processEvents()
    tabwidgets = widget.findChildren(QTabWidget)
    if not tabwidgets:
        capture(name, widget)
        return
    for tw_index, tabs in enumerate(tabwidgets):
        if tabs.count() == 0:
            continue
        tabs.setCurrentIndex(0)
        app.processEvents()
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            app.processEvents()
            label = tabs.tabText(index) or f"tab{index}"
            safe = f"{name}_{tw_index}_{label}".replace("/", "_").replace("\\", "_")
            capture(safe, widget)


specs = [
    ("Cashier", lambda: CashierWidget(api("cashier", "cashier123"), role="cashier")),
    ("Doctor", lambda: DoctorWidget(api("doctor", "doctor123"))),
    ("Pharmacy", lambda: PharmacyWidget(api("pharmacist", "pharm123"), role="pharmacist")),
    ("Nurse", lambda: NurseWidget(api("nurse", "nurse123"))),
    ("Lab", lambda: LabWidget(api("lab", "lab123"))),
    ("Treatment", lambda: TreatmentRoomWidget(api("treatment", "treatment123"))),
    ("Archive", lambda: ArchiveWidget(api("archive", "archive123"))),
    ("Director", lambda: DirectorWidget(api("director", "director123"))),
    ("Tcm", lambda: TcmWidget(api("admin", "admin123"), role="admin")),
    ("Patient360", lambda: Patient360Widget(api("doctor", "doctor123"))),
    ("Surgery", lambda: SurgeryWidget(api("doctor", "doctor123"))),
]

for name, factory in specs:
    try:
        widget = factory()
        walk_tabs(name, widget)
        widget.close()
    except Exception as exc:  # noqa: BLE001
        print(f"{MODE:5} {name:36} ERROR {exc!r}")

# 主窗口 / 登录 / 业务对话框
try:
    main = MainWindow(
        api("admin", "admin123"),
        {"username": "admin", "role": "admin", "display_name": "管理员"},
    )
    capture("MainWindow_Admin", main)
    main.close()
except Exception as exc:  # noqa: BLE001
    print(f"{MODE:5} MainWindow ERROR {exc!r}")

try:
    login = LoginDialog(ClientConfig(server_url="http://127.0.0.1:8001"))
    capture("Login", login)
    login.close()
except Exception as exc:  # noqa: BLE001
    print(f"{MODE:5} Login ERROR {exc!r}")

for name, factory in (
    ("Dialog_Adverse", lambda: AdverseReactionDialog("演示患者")),
    ("Dialog_MixedPayment", lambda: MixedPaymentDialog(100, True)),
):
    try:
        dialog = factory()
        capture(name, dialog)
        dialog.close()
    except Exception as exc:  # noqa: BLE001
        print(f"{MODE:5} {name} ERROR {exc!r}")

parent = DoctorWidget(api("doctor", "doctor123"))
parent.show()
app.processEvents()
for name, factory in (
    (
        "Dialog_MessageBox",
        lambda: QMessageBox(
            QMessageBox.Information, "提示", "浅色/深色主题提示", QMessageBox.Ok, parent
        ),
    ),
    ("Dialog_Input", lambda: QInputDialog(parent)),
):
    try:
        dialog = factory()
        if isinstance(dialog, QInputDialog):
            dialog.setWindowTitle("输入")
            dialog.setLabelText("拒收原因")
            dialog.setTextValue("溶血")
        capture(name, dialog)
        dialog.close()
    except Exception as exc:  # noqa: BLE001
        print(f"{MODE:5} {name} ERROR {exc!r}")

try:
    combo = QComboBox()
    combo.addItems(["全部剂型", "口服", "注射", "外用"])
    combo.resize(220, 32)
    apply_theme(combo)
    combo.show()
    app.processEvents()
    combo.showPopup()
    app.processEvents()
    popup = combo.view().window()
    path = OUT / "Popup_ComboBox.png"
    popup.grab().save(str(path))
    ratio = anomaly(path)
    flag = " <-- CHECK" if ratio > (0.18 if MODE == "dark" else 0.04) else ""
    print(f"{MODE:5} {'Popup_ComboBox':36} {ratio:6.3f}{flag}")
    popup.close()
    combo.close()
except Exception as exc:  # noqa: BLE001
    print(f"{MODE:5} Popup ERROR {exc!r}")

print(f"DONE {MODE} -> {OUT}")
