"""真实客户端：挂起 A 后接诊 B，病历不能串人；B 中途放弃。"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox
from his_client.api import ApiClient
from his_client.ui.doctor import DoctorWidget


def _patient(api, name, phone):
    return api.create_patient(payload={
        "name": name, "id_type": "none", "id_number": None, "gender": "male",
        "birth_date": "1990-01-01", "phone": phone, "address": "测试",
        "emergency_contact_name": "联系人", "emergency_contact_relation": "家属",
        "emergency_contact_phone": phone, "insurance_type": "self_pay",
        "allergy_status": "unknown", "allergy_detail": "",
        "special_history": "", "privacy_consent": True,
    })


def main() -> int:
    app = QApplication.instance() or QApplication([])
    admin = ApiClient("http://127.0.0.1:8001", "admin", "admin123", timeout=10)
    doctor = ApiClient("http://127.0.0.1:8001", "doctor", "doctor123", timeout=10)
    cashier = ApiClient("http://127.0.0.1:8001", "cashier", "cashier123", timeout=10)
    stamp = str(int(time.time()))
    dept = admin.create_department(f"切换科{stamp}")
    doc = admin.create_doctor(f"切换医生{stamp}", dept["id"])
    a = _patient(admin, f"切换A{stamp}", f"131{stamp[-8:]}")
    b = _patient(admin, f"切换B{stamp}", f"132{stamp[-8:]}")
    ra = cashier.create_registration(a["id"], doc["id"])
    rb = cashier.create_registration(b["id"], doc["id"])
    ea = doctor.create_encounter(ra["id"], "A 诊断")
    doctor.create_medical_record(ea["id"], {
        "chief_complaint": "A 的主诉", "present_illness": "A 的现病史",
        "physical_exam": "A 的查体", "treatment_advice": "A 的处理",
    })

    widget = DoctorWidget(doctor)
    widget.auto_timer.stop()
    widget._load_workbench()

    def select(patient_id):
        for row, item in enumerate(widget.workbench_rows):
            if item.get("patient_id") == patient_id:
                widget.wb_table.selectRow(row)
                widget._select_workbench(row, 0)
                return row
        raise AssertionError(f"没有患者 {patient_id}")

    select(a["id"])
    widget._wb_record()
    widget._load_record()
    assert widget.mr_encounter_id.value() == ea["id"]
    widget._pause_workbench()

    select(b["id"])
    # 挂起后可以选择 B；当前接诊上下文仍是 A，直到真正开始 B
    assert widget.banner.patient_id == b["id"]
    widget._start_workbench()
    eb = widget.mr_encounter_id.value()
    assert eb and eb != ea["id"], (ea["id"], eb)
    widget._load_record()
    assert widget._record_editable is True, "B 的新病历不应是只读"
    assert widget.record_edits["chief_complaint"].toPlainText() == "", "不能显示 A 的病历"

    with patch("his_client.ui.doctor.QMessageBox.question", return_value=QMessageBox.Yes):
        widget._abandon_workbench()
    enc = doctor.get_encounter(eb)
    assert enc["status"] == "abandoned", enc
    print(f"A={ea['id']} B={eb} SWITCH=OK ABANDON=OK")
    widget.close()
    widget.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
