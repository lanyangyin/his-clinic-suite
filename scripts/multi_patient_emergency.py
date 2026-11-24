"""多患者 + 跨部门突发事件联动测试（真实 HTTP + 真实 Windows GUI 截图）。"""
import base64
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
BASE = os.environ.get("HIS_E2E_BASE", "http://127.0.0.1:8001").rstrip("/")
SFX = datetime.datetime.now().strftime("%H%M%S")
OUT = Path("docs/scenario_shots")
OUT.mkdir(parents=True, exist_ok=True)
LOG = []


def auth(user, password):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


A = {
    "admin": auth("admin", "admin123"),
    "cashier": auth("cashier", "cashier123"),
    "doctor": auth("doctor", "doctor123"),
    "pharmacist": auth("pharmacist", "pharm123"),
    "warehouse": auth("warehouse", "warehouse123"),
    "nurse": auth("nurse", "nurse123"),
    "lab": auth("lab", "lab123"),
    "director": auth("director", "director123"),
}


def call(method, path, role, payload=None, expect=200):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", A[role])
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            obj = json.loads(body) if body else None
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            obj = json.loads(body) if body else None
        except Exception:
            obj = None
        status = exc.code
    LOG.append((role, method, path, status))
    if status != expect:
        raise AssertionError(f"{method} {path} {status} != {expect}: {body[:300]}")
    return obj


_SEQ = 0


def patient(name, **extra):
    global _SEQ
    _SEQ += 1
    return call("POST", "/patients/", "cashier", {
        "name": name,
        "id_number": f"1101011990{SFX[-4:]}{_SEQ:02d}",
        **extra,
    }, 201)


def visit(pid, doctor_id):
    reg = call("POST", "/registrations/", "cashier", {"patient_id": pid, "doctor_id": doctor_id}, 201)
    enc = call("POST", "/encounters/", "doctor", {"registration_id": reg["id"]}, 201)
    return enc


def main():
    call("GET", "/health", "admin")
    dept = call("POST", "/departments/", "admin", {"name": f"联动科{SFX}"}, 201)
    doctor = call("POST", "/doctors/", "admin", {"name": f"联动医生{SFX}", "department_id": dept["id"]}, 201)
    normal_drug = call("POST", "/drugs/", "admin", {"name": f"联动药{SFX}", "base_price": 9.0}, 201)
    call("POST", "/pharmacy/stock-in", "pharmacist", {
        "drug_id": normal_drug["id"], "batch_no": f"SC{SFX}",
        "expiry": (datetime.date.today() + datetime.timedelta(days=365)).isoformat(),
        "quantity": 30,
    }, 201)

    # 患者 1：正常发药
    p1 = patient(f"联动甲{SFX}")
    e1 = visit(p1["id"], doctor["id"])
    rx1 = call("POST", f"/encounters/{e1['id']}/prescriptions", "doctor", {
        "drug_id": normal_drug["id"], "quantity": 2, "dosage": "1片", "frequency": "bid", "route": "口服"
    }, 201)
    h1 = call("GET", f"/encounters/{e1['id']}/prescriptions/headers", "doctor")[0]
    call("POST", f"/encounters/{e1['id']}/prescriptions/{h1['id']}/review", "pharmacist", {"approve": True, "note": "联动通过"})
    call("POST", "/payments/", "cashier", {"encounter_id": e1["id"]}, 201)
    disp = call("POST", "/pharmacy/dispense", "pharmacist", {"encounter_id": e1["id"], "receiver_name": p1["name"]}, 201)
    call("POST", f"/pharmacy/dispense/{disp['id']}/return", "pharmacist")

    # 患者 2：过敏冲突 + 医生 override
    p2 = patient(f"联动乙{SFX}", allergy_status="present", allergy_detail="青霉素")
    e2 = visit(p2["id"], doctor["id"])
    allergy_drug = call("POST", "/drugs/", "admin", {"name": f"青霉素V钾{SFX}", "base_price": 5.0}, 201)
    denied = call("POST", f"/encounters/{e2['id']}/prescriptions", "doctor", {
        "drug_id": allergy_drug["id"], "quantity": 1
    }, 400)
    assert "过敏" in denied["detail"]
    override = call("POST", f"/encounters/{e2['id']}/prescriptions", "doctor", {
        "drug_id": allergy_drug["id"], "quantity": 1, "allergy_override_reason": "皮试阴性，已告知"
    }, 201)
    assert override["allergy_warning"]

    # 患者 3：检验危急值 -> 医生确认
    p3 = patient(f"联动丙{SFX}")
    e3 = visit(p3["id"], doctor["id"])
    lab_item = call("POST", "/lab/items/", "admin", {"code": f"CR{SFX}", "name": f"联动血钾{SFX}", "price": 15.0}, 201)
    lab = call("POST", f"/lab/encounters/{e3['id']}/lab-requests", "doctor", {"item_id": lab_item["id"]}, 201)
    call("POST", f"/lab/requests/{lab['id']}/collect", "nurse")
    call("POST", f"/lab/requests/{lab['id']}/receive", "lab")
    call("POST", f"/lab/requests/{lab['id']}/start", "lab")
    reported = call("POST", f"/lab/requests/{lab['id']}/report", "lab", {
        "result": "血钾 7.2 mmol/L", "result_value": 7.2, "result_unit": "mmol/L",
        "reference_low": 3.5, "reference_high": 5.5, "abnormal_flag": "H",
        "critical_flag": True, "critical_notified_to": "联动医生",
    })
    assert reported["critical_flag"]
    alerts = call("GET", "/lab/critical-alerts", "doctor")
    assert any(row["id"] == lab["id"] for row in alerts)
    ack = call("POST", f"/lab/requests/{lab['id']}/critical-ack", "doctor", {"note": "已电话通知并处理"})
    assert ack["critical_ack_by"] == "doctor"

    # 患者 4：库存不足 -> 采购申请 -> 院长审批
    p4 = patient(f"联动丁{SFX}")
    e4 = visit(p4["id"], doctor["id"])
    shortage_drug = call("POST", "/drugs/", "admin", {"name": f"联动缺货药{SFX}", "base_price": 4.0}, 201)
    outbound = call("POST", "/warehouse/outbound-orders", "pharmacist", {
        "target_type": "pharmacy", "target_name": "药房",
        "items": [{"kind": "drug", "drug_id": shortage_drug["id"], "batch_no": f"OUT{SFX}", "quantity": 6}]
    }, 201)
    purchase = call("POST", f"/warehouse/outbound-orders/{outbound['id']}/purchase-request", "warehouse", expect=201)
    approved = call("POST", f"/warehouse/purchase-requests/{purchase['id']}/approve", "director")
    assert approved["status"] == "approved"

    # 患者 5：正常就诊，用于队列/多患者
    p5 = patient(f"联动戊{SFX}")
    e5 = visit(p5["id"], doctor["id"])
    call("POST", f"/encounters/{e5['id']}/prescriptions", "doctor", {
        "drug_id": normal_drug["id"], "quantity": 1, "dosage": "1片", "frequency": "qd", "route": "口服"
    }, 201)

    print(json.dumps({
        "patients": [p["id"] for p in (p1, p2, p3, p4, p5)],
        "encounters": [e["id"] for e in (e1, e2, e3, e4, e5)],
        "lab": lab["id"], "critical_ack": ack["critical_ack_at"],
        "purchase": purchase["id"], "http": len(LOG),
    }, ensure_ascii=False))

    # GUI 截图：医生队列、检验危急值、院长采购待办
    os.environ.pop("QT_QPA_PLATFORM", None)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase, QFont
    from his_client.api import ApiClient
    from his_client.ui.doctor import DoctorWidget
    from his_client.ui.lab import LabWidget
    from his_client.ui.approval_inbox import ApprovalInboxWidget

    app = QApplication(sys.argv)
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
    app.setFont(QFont("Microsoft YaHei", 10))
    doctor_ui = DoctorWidget(ApiClient(BASE, "doctor", "doctor123"))
    doctor_ui._load_workbench()
    doctor_ui.resize(1600, 1000)
    doctor_ui.show()
    app.processEvents()
    doctor_ui.grab().save(str(OUT / "multi_patient_doctor_queue.png"))

    lab_ui = LabWidget(ApiClient(BASE, "lab", "lab123"))
    lab_ui.resize(1600, 1000)
    lab_ui.show()
    app.processEvents()
    lab_ui.grab().save(str(OUT / "critical_lab_worklist.png"))

    director_ui = ApprovalInboxWidget(ApiClient(BASE, "director", "director123"))
    director_ui.resize(1200, 600)
    director_ui.show()
    app.processEvents()
    director_ui.grab().save(str(OUT / "purchase_approval_inbox.png"))

    print("SCENARIO OK")


if __name__ == "__main__":
    main()
