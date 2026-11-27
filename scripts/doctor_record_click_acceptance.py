"""真实医生窗口：点击保存/签名病历。"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from his_client.api import ApiClient
from his_client.ui.doctor import DoctorWidget


def click(root, text):
    for button in root.findChildren(QPushButton):
        if button.text().strip() == text and button.isVisible() and button.isEnabled():
            QTest.mouseClick(button, Qt.LeftButton)
            return True
    raise AssertionError(f"找不到按钮 {text}")


def main():
    app = QApplication.instance() or QApplication([])
    admin = ApiClient("http://127.0.0.1:8001", "admin", "admin123")
    cashier = ApiClient("http://127.0.0.1:8001", "cashier", "cashier123")
    doctor = ApiClient("http://127.0.0.1:8001", "doctor", "doctor123")
    stamp = str(int(time.time()))
    patient = admin.create_patient(payload={
        "name": f"病历点击{stamp}", "id_type": "none", "id_number": None,
        "gender": "male", "birth_date": "1990-01-01", "phone": f"136{stamp[-8:]}",
        "address": "测试", "emergency_contact_name": "联系人",
        "emergency_contact_relation": "家属", "emergency_contact_phone": "13600000000",
        "insurance_type": "self_pay", "allergy_status": "unknown",
        "allergy_detail": "", "special_history": "", "privacy_consent": True,
    })
    dept = admin.create_department(f"病历点击科{stamp}")
    doc = admin.create_doctor(f"病历点击医生{stamp}", dept["id"])
    reg = cashier.create_registration(patient["id"], doc["id"])
    enc = doctor.create_encounter(reg["id"], "上呼吸道感染")
    widget = DoctorWidget(doctor)
    widget.show()
    app.processEvents()
    widget.auto_timer.stop()
    widget._load_workbench()
    row = next(i for i, item in enumerate(widget.workbench_rows) if item["patient_id"] == patient["id"])
    widget.wb_table.selectRow(row)
    widget._select_workbench(row, 0)
    widget._wb_record()
    widget._switch_tab("病历")
    widget._load_record()
    widget.record_edits["chief_complaint"].setPlainText("发热咳嗽两天，患者自述受凉后起病")
    widget.record_edits["present_illness"].setPlainText("最高体温 38.3℃，伴咽痛，无胸闷气促")
    widget.record_edits["physical_exam"].setPlainText("咽充血，双肺呼吸音清")
    widget.record_edits["treatment_advice"].setPlainText("对症退热，多饮水，必要时复诊")
    click(widget, "保存 / 更新")
    assert "病历已" in widget.record_msg.text(), widget.record_msg.text()
    click(widget, "签名锁定")
    record = doctor.get_medical_record(enc["id"])
    assert record.get("signed_by"), record
    assert widget.record_edits["chief_complaint"].isReadOnly()
    print(f"ENC={enc['id']} RECORD_CLICK=OK SIGNED={record['signed_by']}")
    widget.close(); widget.deleteLater(); app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main())
