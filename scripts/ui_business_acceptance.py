"""管理员患者合并对话框真实业务冒烟（真实服务端）。"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from his_client.api import ApiClient
from his_client.ui.patient_merge import PatientMergeDialog


def _patient(api, name, phone):
    return api.create_patient(payload={
        "name": name, "id_type": "none", "id_number": None, "gender": "male",
        "birth_date": "1990-01-01", "phone": phone, "address": "测试地址",
        "emergency_contact_name": "联系人", "emergency_contact_relation": "家属",
        "emergency_contact_phone": phone, "insurance_type": "self_pay",
        "allergy_status": "unknown", "allergy_detail": "",
        "special_history": "", "privacy_consent": True,
    })


def main() -> int:
    app = QApplication.instance() or QApplication([])
    api = ApiClient("http://127.0.0.1:8001", "admin", "admin123", timeout=10)
    stamp = int(time.time())
    source = _patient(api, f"UI合并源{stamp}", f"139{stamp % 100000000:08d}")
    target = _patient(api, f"UI合并目标{stamp}", f"138{stamp % 100000000:08d}")
    dialog = PatientMergeDialog(api, "admin", source["id"])
    dialog.target.setValue(target["id"])
    dialog.reason.setText("UI 业务验收")
    dialog._submit()
    assert dialog.result() == 1, dialog.msg.text()
    rows = api._request("GET", "/patients/merge-requests", params={"status": "pending"})
    matched = [
        row for row in rows
        if row["source_id"] == source["id"] and row["target_id"] == target["id"]
    ]
    print(f"SOURCE={source['id']} TARGET={target['id']} REQUESTS={len(matched)}")
    return 0 if matched else 1


if __name__ == "__main__":
    sys.exit(main())
