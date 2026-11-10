"""生成院长审批工作站截图（真实 PySide + 真实待办）。

产出：docs/screenshots/director_approval.png
"""
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.director import DirectorWidget  # noqa: E402

BASE = "http://127.0.0.1:8001"
OUT = ROOT / "docs" / "screenshots" / "director_approval.png"


def main() -> int:
    app = QApplication(sys.argv)
    admin = ApiClient(BASE, "admin", "admin123")
    cashier = ApiClient(BASE, "cashier", "cashier123")
    doctor_api = ApiClient(BASE, "doctor", "doctor123")
    archive = ApiClient(BASE, "archive", "archive123")
    warehouse = ApiClient(BASE, "warehouse", "warehouse123")
    suffix = datetime.now().strftime("%H%M%S")

    patient = cashier.create_patient(
        payload={
            "name": f"院长审批患者{suffix}",
            "id_type": "id_card",
            "id_number": f"11010119900101{suffix[-4:]}",
            "phone": "13800138000",
            "privacy_consent": True,
        }
    )
    dept = admin._request("POST", "/departments/", json={"name": f"院长审批科{suffix}"})
    doc = admin._request(
        "POST", "/doctors/",
        json={"name": f"院长审批医生{suffix}", "department_id": dept["id"]},
    )
    reg = cashier.create_registration(patient["id"], doc["id"])
    enc = doctor_api.create_encounter(reg["id"], "健康检查")
    record = archive.create_archive_record(
        {"patient_id": patient["id"], "encounter_id": enc["id"]}
    )
    archive.archive_record(
        record["id"], {"storage_location": "E-01", "page_count": 8, "completeness": "complete"}
    )
    archive.request_archive_destruction(
        record["id"], {"reason": "保存期满", "note": "院长审批截图"}
    )

    supplier = admin._request(
        "POST", "/suppliers/", json={"code": f"DS{suffix}", "name": f"院长供应商{suffix}"}
    )
    drug = admin._request(
        "POST", "/drugs/", json={"name": f"院长采购药{suffix}", "base_price": 10}
    )
    warehouse._request(
        "POST", "/warehouse/purchase-requests",
        json={
            "department": "库房",
            "supplier_id": supplier["id"],
            "note": "院长审批截图",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "quantity": 10,
                    "estimated_unit_price": 9.5,
                }
            ],
        },
    )

    widget = DirectorWidget(ApiClient(BASE, "director", "director123"))
    widget.resize(1200, 760)
    widget.show()
    QTest.qWait(600)
    widget._load_archives()
    widget._load_purchases()
    QTest.qWait(600)
    assert widget.archive_table.rowCount() >= 1
    assert widget.purchase_table.rowCount() >= 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(OUT))
    print(f"截图：{OUT}")
    print(f"病案待办 {widget.archive_table.rowCount()}，采购待办 {widget.purchase_table.rowCount()}")
    widget.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
