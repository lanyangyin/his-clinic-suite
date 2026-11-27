"""真实 Windows GUI 部门巡检测试：逐个角色打开主窗口和全部页签。"""
import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.pop("QT_QPA_PLATFORM", None)

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from his_client.api import ApiClient
from his_client.ui.main_window import MainWindow
from his_client.ui.table_policy import install_readonly_table_policy

BASE = os.environ.get("HIS_E2E_BASE", "http://127.0.0.1:8001")
ROLES = [
    ("admin", "admin", "admin123"),
    ("cashier", "cashier", "cashier123"),
    ("doctor", "doctor", "doctor123"),
    ("pharmacist", "pharmacist", "pharm123"),
    ("warehouse", "warehouse", "warehouse123"),
    ("nurse", "nurse", "nurse123"),
    ("lab", "lab", "lab123"),
    ("radiology", "radiology", "rad123"),
    ("archive", "archive", "archive123"),
    ("director", "director", "director123"),
    ("hr", "hr_gui", "hr123"),
    ("treatment", "treatment", "treatment123"),
    ("surgery", "surgery", "surgery123"),
    ("decoction", "decoction", "decoction123"),
]
OUT = Path("docs/gui_tour")
OUT.mkdir(parents=True, exist_ok=True)

app = QApplication(sys.argv)
QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
app.setFont(QFont("Microsoft YaHei", 10))
install_readonly_table_policy(app)

results = []
for role, user, password in ROLES:
    record = {"role": role, "user": user, "tabs": [], "errors": [], "screenshot": ""}
    try:
        api = ApiClient(BASE, user, password, timeout=20)
        me = api.me()
        window = MainWindow(api, me)
        window.resize(1600, 1000)
        window.show()
        app.processEvents()
        tabs = getattr(window, "tabs", None) or window.centralWidget()
        count = tabs.count()
        for index in range(count):
            tabs.setCurrentIndex(index)
            app.processEvents()
            title = tabs.tabText(index)
            record["tabs"].append(title)
            try:
                widget = tabs.widget(index)
                app.processEvents()
                if widget is None:
                    record["errors"].append(f"{title}: widget=None")
            except Exception as exc:
                record["errors"].append(f"{title}: {exc}")
        tabs.setCurrentIndex(0)
        app.processEvents()
        path = OUT / f"{role}.png"
        window.grab().save(str(path))
        record["screenshot"] = str(path)
        record["tab_count"] = count
        window.close()
        app.processEvents()
    except Exception:
        record["errors"].append(traceback.format_exc())
    results.append(record)
    print(role, record.get("tab_count"), record["tabs"], record["errors"])

Path("docs/gui_tour.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("DONE", len(results))
