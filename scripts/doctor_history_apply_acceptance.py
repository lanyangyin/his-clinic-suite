"""真实客户端：从左侧历史就诊多选套用病历/诊断/处方。"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog
from his_client.api import ApiClient
from his_client.ui.doctor import DoctorWidget


def main() -> int:
    app = QApplication.instance() or QApplication([])
    admin = ApiClient("http://127.0.0.1:8001", "admin", "admin123", timeout=10)
    doctor = ApiClient("http://127.0.0.1:8001", "doctor", "doctor123", timeout=10)
    cashier = ApiClient("http://127.0.0.1:8001", "cashier", "cashier123", timeout=10)
    stamp = str(int(time.time()))
    dept = admin.create_department(f"套用科{stamp}")
    doc = admin.create_doctor(f"套用医生{stamp}", dept["id"])
    patient = admin.create_patient(payload={
        "name": f"套用患者{stamp}", "id_type": "none", "id_number": None,
        "gender": "male", "birth_date": "1990-01-01", "phone": f"133{stamp[-8:]}",
        "address": "测试", "emergency_contact_name": "联系人",
        "emergency_contact_relation": "家属", "emergency_contact_phone": "13300000000",
        "insurance_type": "self_pay", "allergy_status": "unknown",
        "allergy_detail": "", "special_history": "", "privacy_consent": True,
    })
    prior_reg = cashier.create_registration(patient["id"], doc["id"])
    prior = doctor.create_encounter(prior_reg["id"], "上呼吸道感染")
    doctor.save_encounter_diagnoses(prior["id"], [
        {"diagnosis_code": "J06.9", "diagnosis": "上呼吸道感染"},
    ])
    doctor.create_medical_record(prior["id"], {
        "chief_complaint": "历史主诉：发热咳嗽",
        "present_illness": "历史现病史：受凉后发热",
        "physical_exam": "历史查体：咽充血",
        "treatment_advice": "历史处理：多饮水",
    })
    drug = admin._request("POST", "/drugs/", json={
        "name": f"套用药{stamp}", "base_price": 10,
    })
    doctor.add_prescription(prior["id"], {"drug_id": drug["id"], "quantity": 2,
                                          "dosage": "1粒", "frequency": "tid",
                                          "route": "口服", "days": 3})
    cashier.create_payment(prior["id"])

    current_reg = cashier.create_registration(patient["id"], doc["id"])
    current = doctor.create_encounter(current_reg["id"], "本次诊断")

    widget = DoctorWidget(doctor)
    widget.auto_timer.stop()
    widget._load_workbench()
    for row, item in enumerate(widget.workbench_rows):
        if item.get("patient_id") == patient["id"] and item.get("encounter_id") == current["id"]:
            widget.wb_table.selectRow(row)
            widget._select_workbench(row, 0)
            break
    else:
        raise AssertionError("当前就诊不在队列")
    widget._load_record()
    assert widget._record_editable is True
    widget._load_side_history(patient["id"], force=True)
    source_row = next(i for i, row in enumerate(widget.side_history_data) if row["id"] == prior["id"])
    with patch("his_client.ui.doctor.HistoryApplyDialog.exec", return_value=QDialog.Accepted), \
         patch("his_client.ui.doctor.HistoryApplyDialog.selected",
               return_value={"record:chief_complaint", "record:present_illness", "diagnoses", "prescriptions"}):
        widget._apply_history(source_row)
    assert widget.record_edits["chief_complaint"].toPlainText() == "历史主诉：发热咳嗽"
    assert doctor.list_encounter_diagnoses(current["id"])[0]["diagnosis"] == "上呼吸道感染"
    rx = doctor.list_prescriptions(current["id"])
    assert any(row.get("drug_name") == f"套用药{stamp}" for row in rx), rx
    print(f"PRIOR={prior['id']} CURRENT={current['id']} HISTORY_APPLY=OK")
    widget.close()
    widget.deleteLater()
    app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
