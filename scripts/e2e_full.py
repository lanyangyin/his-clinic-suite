"""真实服务端全流程 E2E：不依赖 TestClient，直接走 HTTP。

用法：
    .venv\\Scripts\\python.exe scripts\\e2e_full.py
环境变量：
    HIS_E2E_BASE（默认 http://127.0.0.1:8001）
"""
import base64
import datetime
import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("HIS_E2E_BASE", "http://127.0.0.1:8001").rstrip("/")
SUFFIX = datetime.datetime.now().strftime("%H%M%S")
RESULTS = []


def auth(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


AUTH = {
    "admin": auth("admin", "admin123"),
    "doctor": auth("doctor", "doctor123"),
    "cashier": auth("cashier", "cashier123"),
    "pharmacist": auth("pharmacist", "pharm123"),
    "nurse": auth("nurse", "nurse123"),
    "lab": auth("lab", "lab123"),
    "director": auth("director", "director123"),
}


def call(method: str, path: str, role: str, payload=None, expect: int = 200):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("Authorization", AUTH[role]["Authorization"])
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            obj = json.loads(body) if body else None
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        obj = None
        status = exc.code
    if status != expect:
        raise AssertionError(f"{method} {path} -> {status}, expected {expect}: {body[:500]}")
    RESULTS.append((method, path, status))
    return obj


def step(name: str):
    print(f"\n== {name} ==")


def main():
    step("health")
    health = call("GET", "/health", "admin")
    assert health["status"] == "ok"

    step("主数据：科室/医生/药品/库存")
    dept = call("POST", "/departments/", "admin", {"name": f"E2E科室{SUFFIX}"}, 201)
    doctor = call(
        "POST", "/doctors/", "admin",
        {"name": f"E2E医生{SUFFIX}", "department_id": dept["id"]}, 201,
    )
    drug = call(
        "POST", "/drugs/", "admin",
        {"name": f"E2E西药{SUFFIX}", "base_price": 12.5}, 201,
    )
    call(
        "POST", "/pharmacy/stock-in", "pharmacist",
        {
            "drug_id": drug["id"],
            "batch_no": f"E2E{SUFFIX}",
            "expiry": (datetime.date.today() + datetime.timedelta(days=365)).isoformat(),
            "quantity": 20,
        },
        201,
    )

    step("患者/挂号/就诊")
    patient = call(
        "POST", "/patients/", "cashier",
        {"name": f"E2E患者{SUFFIX}", "id_number": f"11010119900101{SUFFIX[-4:]}"},
        201,
    )
    registration = call(
        "POST", "/registrations/", "cashier",
        {"patient_id": patient["id"], "doctor_id": doctor["id"]}, 201,
    )
    encounter = call(
        "POST", "/encounters/", "doctor",
        {"registration_id": registration["id"], "diagnosis": "上呼吸道感染"}, 201,
    )

    step("病历：创建/修改/签名/版本")
    call(
        "POST", f"/encounters/{encounter['id']}/medical-record", "doctor",
        {"chief_complaint": "发热咳嗽3天", "present_illness": "受凉后出现"},
        201,
    )
    call(
        "PUT", f"/encounters/{encounter['id']}/medical-record", "doctor",
        {"treatment_advice": "多饮水，注意休息"},
    )
    call("POST", f"/encounters/{encounter['id']}/medical-record/sign", "doctor")
    versions = call(
        "GET", f"/encounters/{encounter['id']}/medical-record/versions", "doctor"
    )
    assert [row["action"] for row in versions] == ["create", "update", "sign"]

    step("西药：开方 -> 审方 -> 收费 -> 发药 -> 退药")
    item = call(
        "POST", f"/encounters/{encounter['id']}/prescriptions", "doctor",
        {"drug_id": drug["id"], "quantity": 2, "dosage": "1片", "frequency": "bid",
         "route": "口服", "days": 3},
        201,
    )
    assert item["prescription_status"] == "pending_review"
    headers = call(
        "GET", f"/encounters/{encounter['id']}/prescriptions/headers", "doctor"
    )
    header = headers[0]
    reviews = call("GET", "/pharmacy/prescription-reviews", "pharmacist")
    assert any(row["id"] == header["id"] for row in reviews)
    reviewed = call(
        "POST", f"/encounters/{encounter['id']}/prescriptions/{header['id']}/review",
        "pharmacist", {"approve": True, "note": "E2E审方通过"},
    )
    assert reviewed["status"] == "approved"
    call("POST", "/payments/", "cashier", {"encounter_id": encounter["id"]}, 201)
    dispense = call(
        "POST", "/pharmacy/dispense", "pharmacist",
        {"encounter_id": encounter["id"], "receiver_name": patient["name"]}, 201,
    )
    slip = call(
        "GET", f"/pharmacy/dispense-slips/{encounter['id']}", "pharmacist"
    )
    assert slip["items"][0]["batch_no"] == f"E2E{SUFFIX}"
    assert slip["items"][0]["quantity"] == 2
    call("POST", f"/pharmacy/dispense/{dispense['id']}/return", "pharmacist")

    step("处方中心/通用明细/单张打印")
    center = call(
        "GET", f"/encounters/{encounter['id']}/prescription-center", "doctor"
    )
    assert center["western"] and center["western"][0]["id"] == header["id"]
    lines = call(
        "GET", f"/encounters/{encounter['id']}/prescription-lines", "doctor"
    )
    assert lines[0]["kind"] == "drug" and lines[0]["quantity"] == 2
    # 打印接口返回 HTML，用 urllib 单独验证
    request = urllib.request.Request(BASE + f"/print/prescription-header/{header['id']}")
    with urllib.request.urlopen(request, timeout=20) as response:
        printed = response.read().decode("utf-8")
    assert "门诊处方" in printed and f"E2E西药{SUFFIX}" in printed

    step("第二就诊：中药/检验")
    registration2 = call(
        "POST", "/registrations/", "cashier",
        {"patient_id": patient["id"], "doctor_id": doctor["id"]}, 201,
    )
    encounter2 = call(
        "POST", "/encounters/", "doctor",
        {"registration_id": registration2["id"], "diagnosis": "调理"}, 201,
    )

    step("中药：饮片处方 -> 审核 -> 统一处方头")
    herb = call(
        "POST", "/tcm/herbs", "admin",
        {"code": f"HERB{SUFFIX}", "name": f"E2E饮片{SUFFIX}", "price_per_g": 0.2},
        201,
    )
    tcm = call(
        "POST", f"/tcm/encounters/{encounter2['id']}/prescriptions", "doctor",
        {"formula_name": "E2E方", "packs": 2, "decoct_service": "self",
         "items": [{"herb_id": herb["id"], "dose_g": 10}]},
        201,
    )
    assert tcm["prescription_id"]
    tcm_header = next(
        row for row in call(
            "GET", f"/encounters/{encounter2['id']}/prescriptions/headers", "doctor"
        ) if row["id"] == tcm["prescription_id"]
    )
    assert tcm_header["type"] == "tcm_herb"
    call("POST", f"/tcm/prescriptions/{tcm['id']}/review", "pharmacist")
    after = call(
        "GET", f"/encounters/{encounter2['id']}/prescriptions/headers", "doctor"
    )
    assert next(row for row in after if row["id"] == tcm["prescription_id"])["status"] == "approved"

    step("检验：申请 -> 采样 -> 接收 -> 上机 -> 报告 -> 审核")
    lab_item = call(
        "POST", "/lab/items/", "admin",
        {"code": f"CBC{SUFFIX}", "name": f"E2E血常规{SUFFIX}", "price": 20.0},
        201,
    )
    lab_request = call(
        "POST", f"/lab/encounters/{encounter2['id']}/lab-requests", "doctor",
        {"item_id": lab_item["id"]}, 201,
    )
    call("POST", f"/lab/requests/{lab_request['id']}/collect", "nurse")
    call("POST", f"/lab/requests/{lab_request['id']}/receive", "lab")
    call("POST", f"/lab/requests/{lab_request['id']}/start", "lab")
    call(
        "POST", f"/lab/requests/{lab_request['id']}/report", "lab",
        {"result": "白细胞 6.2×10^9/L，正常"},
    )
    lab_reviewed = call("POST", f"/lab/requests/{lab_request['id']}/review", "lab")
    assert lab_reviewed["status"] == "reviewed"

    step("患者访问审计")
    call("GET", f"/patients/{patient['id']}", "doctor")
    call("GET", f"/patients/{patient['id']}/history", "doctor")
    access = call("GET", f"/patients/{patient['id']}/access-log", "admin")
    assert any(row["action"] == "view_history" for row in access)

    step("通知")
    notes = call("GET", "/notifications", "pharmacist")
    assert any("待审批" in row["title"] or "审批" in row["title"] for row in notes)
    dispatched = call("POST", "/notifications/dispatch", "admin")
    assert dispatched["processed"] >= 1

    step("汇总")
    print(f"patient={patient['id']} encounter={encounter['id']} encounter2={encounter2['id']} "
          f"rx={header['id']} tcm={tcm['id']} lab={lab_request['id']} dispense={dispense['id']}")
    print(f"HTTP requests: {len(RESULTS)}")
    print("E2E OK")


if __name__ == "__main__":
    main()
