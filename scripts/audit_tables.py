"""遍历所有角色/工作站，检查每个 QTableWidget 的只读状态。"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import his_client.ui  # noqa: F401  install hardened QTableWidget before Qt import
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication, QAbstractItemView

from his_client.api import ApiClient
from his_client.ui.table_policy import ReadOnlyTable
from his_client.ui.main_window import MainWindow

BASE = "http://127.0.0.1:8001"
ROLES = [
    ("admin", "admin123"),
    ("cashier", "cashier123"),
    ("doctor", "doctor123"),
    ("pharmacist", "pharm123"),
    ("warehouse", "warehouse123"),
    ("nurse", "nurse123"),
    ("lab", "lab123"),
    ("radiology", "rad123"),
    ("archive", "archive123"),
    ("director", "director123"),
    ("hr_gui", "hr123"),
    ("treatment", "treatment123"),
    ("surgery", "surgery123"),
    ("decoction", "decoction123"),
]

app = QApplication.instance() or QApplication([])
report = {"roles": [], "errors": [], "total_tables": 0, "allowed_tables": 0}
seen = set()
for username, password in ROLES:
    role_report = {"role": username, "tables": [], "errors": []}
    try:
        api = ApiClient(BASE, username, password, timeout=10)
        user = api.me()
        window = MainWindow(api, user)
        window.show()
        app.processEvents()
        for index in range(window.tabs.count()):
            window.tabs.setCurrentIndex(index)
            app.processEvents()
        tables = window.findChildren(QtWidgets.QTableWidget)
        for table in tables:
            object_id = id(table)
            seen.add(object_id)
            allow = bool(table.property("allow_cell_edit"))
            columns = table.property("editable_columns")
            columns = tuple(columns) if columns is not None else None
            data = {
                "type": type(table).__name__,
                "allow_cell_edit": allow,
                "editable_columns": columns,
                "edit_triggers": table.editTriggers().value,
                "object_name": table.objectName(),
            }
            role_report["tables"].append(data)
            report["total_tables"] += 1
            if not isinstance(table, ReadOnlyTable):
                role_report["errors"].append(f"表格未使用硬约束类: {data}")
            if allow:
                report["allowed_tables"] += 1
                if columns != (2,):
                    role_report["errors"].append(f"白名单表格列异常: {data}")
            else:
                if table.editTriggers() != QAbstractItemView.NoEditTriggers:
                    role_report["errors"].append(f"只读表格仍可编辑: {data}")
                if table.edit(table.model().index(0, 0), QAbstractItemView.DoubleClicked, None):
                    role_report["errors"].append(f"只读表格 edit() 返回 True: {data}")
        window.close()
    except Exception as exc:  # noqa: BLE001
        role_report["errors"].append(f"{type(exc).__name__}: {exc}")
    if role_report["errors"]:
        report["errors"].extend([f"{username}: {item}" for item in role_report["errors"]])
    report["roles"].append(role_report)
    print(username, "tables=", len(role_report["tables"]), "errors=", len(role_report["errors"]))

Path("docs/table_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("TOTAL", report["total_tables"], "ALLOWED", report["allowed_tables"], "ERRORS", len(report["errors"]))
raise SystemExit(1 if report["errors"] else 0)
