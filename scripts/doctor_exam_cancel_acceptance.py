"""真实客户端：医生开检验/检查/治疗后取消。"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from his_client.api import ApiClient
from his_client.ui.doctor import DoctorWidget


def main() -> int:
    app = QApplication.instance() or QApplication([])
    admin = ApiClient("http://127.0.0.1:8001", "admin", "admin123", timeout=10)
    doctor = ApiClient("http://127.0.0.1:8001", "doctor", "doctor123", timeout=10)
    cashier = ApiClient("http://127.0.0.1:8001", "cashier", "cashier123", timeout=10)
    stamp = str(int(time.time()))
    patient = admin.create_patient(payload={
        "name": f"取消验收{stamp}", "id_type": "none", "id_number": None,
        "gender": "male", "birth_date": "1990-01-01", "phone": f"135{stamp[-8:]}",
        "address": "测试", "emergency_contact_name": "联系人",
        "emergency_contact_relation": "家属", "emergency_contact_phone": "13500000000",
        "insurance_type": "self_pay", "allergy_status": "unknown",
        "allergy_detail": "", "special_history": "", "privacy_consent": True,
    })
    dept = admin.create_department(f"取消科{stamp}")
    doc = admin.create_doctor(f"取消医生{stamp}", dept["id"])
    reg = cashier.create_registration(patient["id"], doc["id"])
    enc = doctor.create_encounter(reg["id"], "取消验收")
    lab = admin._request("POST", "/lab/items/", json={
        "code": f"CL{stamp[-6:]}", "name": f"取消检验{stamp}", "price": 20,
    })
    treat_item = admin._request("POST", "/charges/items/", json={
        "code": f"CT{stamp[-6:]}", "name": f"取消治疗{stamp}", "category": "treatment", "price": 30,
    })
    doctor.create_treatment(enc["id"], treat_item["id"], 1, "取消验收")

    widget = DoctorWidget(doctor)
    widget.auto_timer.stop()
    widget._load_workbench()
    row = next(i for i, item in enumerate(widget.workbench_rows) if item.get("patient_id") == patient["id"])
    widget.wb_table.selectRow(row)
    widget._select_workbench(row, 0)
    widget.exam_encounter_id.setValue(enc["id"])
    widget._load_lab_items()
    widget.lab_combo.setCurrentIndex(widget.lab_combo.findData(lab["id"]))
    widget._create_lab()
    widget._refresh_exam_requests()
    assert widget.exam_table.rowCount() == 1, widget.exam_table.rowCount()
    with patch("his_client.ui.doctor.QMessageBox.question", return_value=widget and __import__("PySide6").QtWidgets.QMessageBox.Yes):
        widget.exam_table.selectRow(0)
        widget._cancel_exam()
    lab_rows = doctor.list_lab_requests(enc["id"])
    assert lab_rows[0]["status"] == "cancelled", lab_rows

    widget._refresh_treatments()
    assert widget.treat_table.rowCount() == 1
    with patch("his_client.ui.doctor.QMessageBox.question", return_value=__import__("PySide6").QtWidgets.QMessageBox.Yes):
        widget.treat_table.selectRow(0)
        widget._cancel_treatment_order()
    treat_rows = doctor.list_treatments(enc["id"])
    assert treat_rows[0]["status"] == "cancelled", treat_rows
    print(f"ENC={enc['id']} LAB_CANCEL=OK TREAT_CANCEL=OK")
    widget.close()
    widget.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
