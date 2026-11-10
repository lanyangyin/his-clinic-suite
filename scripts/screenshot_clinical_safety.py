"""生成医生端过敏硬拦截截图（真实 PySide 控件 + 真实 API）。

产出：docs/screenshots/allergy_block.png
"""
import base64
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from his_client.api import ApiClient  # noqa: E402
from his_client.ui.doctor import DoctorWidget  # noqa: E402

BASE = "http://127.0.0.1:8001"
OUT = ROOT / "docs" / "screenshots" / "allergy_block.png"


def main() -> int:
    app = QApplication(sys.argv)
    admin = ApiClient(BASE, "admin", "admin123")
    cashier = ApiClient(BASE, "cashier", "cashier123")
    doctor_api = ApiClient(BASE, "doctor", "doctor123")
    suffix = datetime.now().strftime("%H%M%S")
    patient = cashier.create_patient(
        payload={
            "name": f"过敏截图患者{suffix}",
            "id_type": "id_card",
            "id_number": f"11010119900101{suffix[-4:]}",
            "phone": "13800138000",
            "allergy_status": "present",
            "allergy_detail": "青霉素",
            "privacy_consent": True,
        }
    )
    dept = admin._request("POST", "/departments/", json={"name": f"过敏截图科{suffix}"})
    doc = admin._request(
        "POST", "/doctors/",
        json={"name": f"过敏截图医生{suffix}", "department_id": dept["id"]},
    )
    reg = cashier.create_registration(patient["id"], doc["id"])
    enc = doctor_api.create_encounter(reg["id"], "上呼吸道感染")
    drug = admin._request(
        "POST", "/drugs/", json={"name": f"阿莫西林胶囊{suffix}", "base_price": 12}
    )

    widget = DoctorWidget(ApiClient(BASE, "doctor", "doctor123"))
    widget.resize(1500, 900)
    widget.show()
    QTest.qWait(500)
    widget.tabs.setCurrentIndex(5)  # 开方
    widget.rx_encounter_id.setValue(enc["id"])
    widget._load_drugs()
    for row in range(widget.drug_table.rowCount()):
        if widget.drug_table.item(row, 1).text() == drug["name"]:
            widget.drug_table.selectRow(row)
            widget.rx_drug_id.setText(widget.drug_table.item(row, 0).text())
            break
    # 取消 override 弹窗：真实界面会停留在“已取消开方”并显示过敏冲突
    QInputDialog.getText = staticmethod(lambda *args, **kwargs: ("", False))
    widget._add_prescription()
    QTest.qWait(800)
    assert "过敏" in widget.rx_msg.text(), widget.rx_msg.text()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(OUT))
    print(f"截图：{OUT}")
    print("提示：", widget.rx_msg.text())
    widget.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
