"""生成医生工作台危急值待确认截图（真实 PySide + 真实 API）。

产出：docs/screenshots/critical_alert.png
"""
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.doctor import DoctorWidget  # noqa: E402

BASE = "http://127.0.0.1:8001"
OUT = ROOT / "docs" / "screenshots" / "critical_alert.png"


def main() -> int:
    app = QApplication(sys.argv)
    admin = ApiClient(BASE, "admin", "admin123")
    cashier = ApiClient(BASE, "cashier", "cashier123")
    doctor_api = ApiClient(BASE, "doctor", "doctor123")
    lab = ApiClient(BASE, "lab", "lab123")
    suffix = datetime.now().strftime("%H%M%S")
    patient = cashier.create_patient(
        payload={
            "name": f"危急值截图患者{suffix}",
            "id_type": "id_card",
            "id_number": f"11010119900101{suffix[-4:]}",
            "phone": "13800138000",
            "privacy_consent": True,
        }
    )
    dept = admin._request("POST", "/departments/", json={"name": f"危急值截图科{suffix}"})
    doc = admin._request(
        "POST", "/doctors/",
        json={"name": f"危急值截图医生{suffix}", "department_id": dept["id"]},
    )
    reg = cashier.create_registration(patient["id"], doc["id"])
    enc = doctor_api.create_encounter(reg["id"], "发热")
    item = admin._request(
        "POST", "/lab/items/",
        json={"code": f"CV{suffix[-6:]}", "name": f"白细胞危急值{suffix}", "price": 20},
    )
    request = doctor_api.create_lab_request(enc["id"], item["id"])
    lab.collect_lab(request["id"])
    lab.receive_lab(request["id"])
    lab.start_lab(request["id"])
    lab.report_lab(
        request["id"],
        {
            "result": "WBC 25.0×10^9/L",
            "result_value": 25.0,
            "result_unit": "×10^9/L",
            "critical_flag": True,
            "critical_note": "白细胞显著升高",
            "critical_notified_to": "急诊医生",
        },
    )
    QTest.qWait(300)

    widget = DoctorWidget(ApiClient(BASE, "doctor", "doctor123"))
    widget.resize(1500, 1000)
    widget.show()
    QTest.qWait(600)
    widget._load_workbench()
    QTest.qWait(600)
    widget._load_critical_alerts()
    QTest.qWait(600)
    assert "待确认" in widget.critical_msg.text(), widget.critical_msg.text()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(OUT))
    print(f"截图：{OUT}")
    print("提示：", widget.critical_msg.text())
    widget.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
