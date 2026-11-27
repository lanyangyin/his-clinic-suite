"""真实人事窗口：点击停用/启用账号。"""
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget
from his_client.api import ApiClient
from his_client.ui.hr import HrWidget

def click(root, text):
    for b in root.findChildren(QPushButton):
        if b.text().strip() == text and b.isVisible() and b.isEnabled():
            QTest.mouseClick(b, Qt.LeftButton); return
    raise AssertionError(f"找不到 {text}")

def main():
    app = QApplication.instance() or QApplication([])
    admin = ApiClient("http://127.0.0.1:8001", "admin", "admin123")
    hr = ApiClient("http://127.0.0.1:8001", "hr_gui", "hr123")
    stamp = str(int(time.time()))
    user = admin._request("POST", "/users/", json={
        "username": f"hrclick{stamp[-6:]}", "password": "Pass1234",
        "role": "nurse", "display_name": "人事点击测试",
    })
    widget = HrWidget(hr); widget.show(); app.processEvents()
    tabs = widget.findChild(QTabWidget)
    tabs.setCurrentIndex(3); app.processEvents()
    widget._load_accounts(); app.processEvents()
    row = next(i for i, u in enumerate(widget.users) if u["id"] == user["id"])
    widget.acc_table.selectRow(row)
    click(widget, "停用/启用选中账号")
    assert admin._request("GET", f"/users/{user['id']}")["is_active"] is False
    widget._load_accounts(); app.processEvents()
    row = next(i for i, u in enumerate(widget.users) if u["id"] == user["id"])
    widget.acc_table.selectRow(row)
    click(widget, "停用/启用选中账号")
    assert admin._request("GET", f"/users/{user['id']}")["is_active"] is True
    print(f"USER={user['id']} HR_ACCOUNT_CLICK=OK")
    widget.close(); widget.deleteLater(); app.processEvents()
    return 0
if __name__ == "__main__":
    sys.exit(main())
