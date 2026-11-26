"""医生站真实集成：接诊中患者显示信息，已收费患者只保留历史诊疗。"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from his_client.api import ApiClient
from his_client.ui.doctor import DoctorWidget


def _patient(api, name, phone):
    return api.create_patient(payload={
        "name": name, "id_type": "none", "id_number": None, "gender": "male",
        "birth_date": "1990-01-01", "phone": phone, "address": "测试地址",
        "emergency_contact_name": "联系人", "emergency_contact_relation": "家属",
        "emergency_contact_phone": phone, "insurance_type": "self_pay",
        "allergy_status": "unknown", "allergy_detail": "",
        "special_history": "", "privacy_consent": True,
    })


def _visit(api, auth):
    dept = api.create_department(f"验收科{int(time.time())}")
    doctor = api.create_doctor(f"验收医生{int(time.time())}", dept["id"])
    patient = _patient(api, f"验收患者{int(time.time())}", f"136{int(time.time()) % 100000000:08d}")
    reg = api.create_registration(patient["id"], doctor["id"])
    encounter = api.create_encounter(reg["id"], "验收诊断")
    return patient, reg, encounter


def main() -> int:
    app = QApplication.instance() or QApplication([])
    admin = ApiClient("http://127.0.0.1:8001", "admin", "admin123", timeout=10)
    cashier = ApiClient("http://127.0.0.1:8001", "cashier", "cashier123", timeout=10)
    doctor = ApiClient("http://127.0.0.1:8001", "doctor", "doctor123", timeout=10)

    active_patient, _, active_enc = _visit(admin, None)
    paid_patient, _, paid_enc = _visit(admin, None)
    drug = admin._request("POST", "/drugs/", json={"name": f"验收药{int(time.time())}", "base_price": 1})
    doctor.add_prescription(paid_enc["id"], {"drug_id": drug["id"], "quantity": 1})
    paid = cashier.create_payment(paid_enc["id"])
    assert paid["status"] == "paid", paid

    widget = DoctorWidget(doctor)
    widget.auto_timer.stop()
    widget._load_workbench()
    assert widget.wb_table.rowCount() >= 2

    def select(patient_id):
        for row in range(widget.wb_table.rowCount()):
            if widget.workbench_rows[row].get("patient_id") == patient_id:
                widget.wb_table.selectRow(row)
                widget._select_workbench(row, 0)
                return
        raise AssertionError(f"队列没有患者 {patient_id}")

    select(active_patient["id"])
    assert widget.banner.patient_id == active_patient["id"], widget.banner.patient_id
    indexes = {widget.tabs.tabText(i): i for i in range(widget.tabs.count())}
    assert widget.tabs.isTabEnabled(indexes["病历"]) is True
    assert widget.tabs.isTabEnabled(indexes["治疗"]) is True

    select(paid_patient["id"])
    assert widget.banner.patient_id == 0, widget.banner.patient_id
    assert widget.banner.name.text() == "未选择患者"
    for label in ("病历", "开方", "检验 / 检查", "治疗", "收费"):
        assert widget.tabs.isTabEnabled(indexes[label]) is False, label
    assert widget.tabs.isTabEnabled(indexes["历史诊疗"]) is True
    print(f"ACTIVE={active_patient['id']} PAID={paid_patient['id']} OK")
    widget.close()
    widget.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
