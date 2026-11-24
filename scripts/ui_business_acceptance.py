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
from his_client.ui.tcm import TcmWidget
from his_client.ui.inpatient import InpatientWidget
from PySide6.QtWidgets import QTabWidget


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

    herb = api._request("POST", "/tcm/herbs", json={
        "code": f"UIH{stamp % 100000}", "name": f"验收饮片{stamp}",
        "price_per_g": 1, "stock_g": 0,
    })
    batch = api._request("POST", f"/tcm/herbs/{herb['id']}/stock-batches", json={
        "batch_no": f"UIB{stamp % 100000}", "quantity_g": 10,
    })
    adjustment = api._request("POST", f"/tcm/stock-batches/{batch['id']}/adjust-requests", json={
        "delta_g": -2, "reason": "UI 业务验收",
    })
    tcm = TcmWidget(api, role="admin")
    tcm_tabs = tcm.findChild(QTabWidget)
    for i in range(tcm_tabs.count()):
        if tcm_tabs.tabText(i) == "盘点审批":
            tcm_tabs.setCurrentIndex(i)
            break
    tcm._load_adjustments()
    for row in range(tcm.adjust_table.rowCount()):
        if tcm.adjust_table.item(row, 0).text() == str(adjustment["id"]):
            tcm.adjust_table.setCurrentCell(row, 0)
            break
    tcm._review_adjustment(True)
    pending = api._request("GET", "/tcm/adjustments", params={"status": "pending"})
    tcm_ok = not any(row["id"] == adjustment["id"] for row in pending)
    print(f"TCM_ADJUSTMENT={adjustment['id']} APPROVED={tcm_ok}")

    ward = api._request("POST", "/wards/", json={"name": f"验收病区{stamp}"})
    bed = api._request("POST", "/beds/", json={"ward_id": ward["id"], "code": f"B{stamp % 100}"})
    dept = api.create_department(f"验收科{stamp}")
    doctor = api.create_doctor(f"验收医生{stamp}", dept["id"])
    inpatient = _patient(api, f"住院验收{stamp}", f"137{stamp % 100000000:08d}")
    admission = api.create_inpatient_admission(inpatient["id"], doctor["id"], bed["id"])
    widget = InpatientWidget(api, role="admin")
    widget._load()
    for row in range(widget.admission_table.rowCount()):
        if widget.admission_table.item(row, 0).text() == str(admission["id"]):
            widget.admission_table.setCurrentCell(row, 0)
            break
    widget._select(widget.admission_table.currentRow(), 0)
    widget._discharge()
    admissions = api.list_inpatient_admissions()
    discharged = any(
        row["id"] == admission["id"] and row["status"] == "discharged" for row in admissions
    )
    print(f"ADMISSION={admission['id']} DISCHARGED={discharged}")
    dialog.close()
    tcm.close()
    widget.close()
    dialog.deleteLater()
    tcm.deleteLater()
    widget.deleteLater()
    app.processEvents()
    return 0 if matched and tcm_ok and discharged else 1


if __name__ == "__main__":
    sys.exit(main())
