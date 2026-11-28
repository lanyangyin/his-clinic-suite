"""仿真发现的关键安全问题回归。"""
from datetime import date, timedelta

from app import settings


def _encounter(client, auth, name="仿真患者"):
    patient = client.post(
        "/patients/", json={"name": name, "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": f"仿真科{name}"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": f"仿真医生{name}", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": registration["id"]},
        headers=auth["doctor"],
    ).json()
    return patient, doctor, registration, encounter


def _drug_with_stock(client, auth, name="仿真药"):
    drug = client.post(
        "/drugs/", json={"name": name, "base_price": 10.0}, headers=auth["admin"]
    ).json()
    stock = client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": "SIM1", "expiry": "2029-12-31", "quantity": 20},
        headers=auth["pharmacist"],
    )
    assert stock.status_code == 201, stock.text
    return drug


def test_cancelled_registration_cannot_start_encounter(client, auth):
    patient = client.post(
        "/patients/", json={"name": "退号患者", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "退号科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "退号医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    cancelled = client.post(
        f"/registrations/{registration['id']}/cancel", headers=auth["cashier"]
    )
    assert cancelled.status_code == 200
    started = client.post(
        "/encounters/", json={"registration_id": registration["id"]},
        headers=auth["doctor"],
    )
    assert started.status_code == 400
    assert "已取消" in started.json()["detail"]


def test_past_schedule_cannot_register(client, auth):
    patient, doctor, _registration, _encounter_row = _encounter(client, auth, "过期排班")
    schedule = client.post(
        "/schedules/",
        json={"doctor_id": doctor["id"], "schedule_date": str(date.today() - timedelta(days=1)),
              "period": "morning", "capacity": 5},
        headers=auth["admin"],
    ).json()
    blocked = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"],
              "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    assert blocked.status_code == 400
    assert "已过" in blocked.json()["detail"]


def test_no_charge_complete_encounter(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "无费用完诊")
    completed = client.post(
        f"/encounters/{encounter['id']}/complete", headers=auth["doctor"]
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "closed"
    # 不生成 0 元付款/发票
    payments = client.get(
        "/payments/", params={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert payments.status_code == 200
    assert payments.json() == []


def test_lab_duplicate_order_rejected(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "重复检验")
    item = client.post(
        "/lab/items/", json={"code": "SIMDUP", "name": "重复检验", "price": 10},
        headers=auth["admin"],
    ).json()
    first = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    )
    assert second.status_code == 400
    assert "重复" in second.json()["detail"]


def test_pharmacy_requires_pickup_code_and_receiver(client, auth, monkeypatch):
    patient, _doctor, _registration, encounter = _encounter(client, auth, "取药码")
    drug = _drug_with_stock(client, auth, "取药码药")
    rx = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1}, headers=auth["doctor"],
    )
    assert rx.status_code == 201, rx.text
    pay = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert pay.status_code == 201, pay.text
    worklist = client.get("/pharmacy/worklist", headers=auth["pharmacist"]).json()
    code = next(row["pickup_code"] for row in worklist if row["encounter_id"] == encounter["id"])
    monkeypatch.setattr(settings, "PHARMACY_REQUIRE_PICKUP_CODE", True)

    missing = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "receiver_name": "患者本人"},
        headers=auth["pharmacist"],
    )
    assert missing.status_code == 400
    assert "取药码" in missing.json()["detail"]

    no_receiver = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "pickup_code": code},
        headers=auth["pharmacist"],
    )
    assert no_receiver.status_code == 400
    assert "取药人" in no_receiver.json()["detail"]

    ok = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "pickup_code": code,
              "receiver_name": "患者本人"},
        headers=auth["pharmacist"],
    )
    assert ok.status_code == 201, ok.text
    verify = client.get(f"/pharmacy/pickup-codes/{code}", headers=auth["pharmacist"])
    assert verify.status_code == 400
    assert "已使用" in verify.json()["detail"]


def test_partial_return_blocks_full_refund(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "部分退药")
    drug = _drug_with_stock(client, auth, "部分退药药")
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2}, headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    dispensed = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "receiver_name": "患者本人",
              "pickup_code": client.get("/pharmacy/worklist", headers=auth["pharmacist"]).json()[0]["pickup_code"]},
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    line = dispensed.json()["items"][0]
    returned = client.post(
        f"/pharmacy/dispense/{dispensed.json()['id']}/return-items",
        json={"items": [{"line_id": line["id"], "quantity": 1}], "reason": "患者要求"},
        headers=auth["pharmacist"],
    )
    assert returned.status_code == 200, returned.text
    blocked = client.post(
        f"/payments/{payment['id']}/refund",
        json={"reason": "整单退费"}, headers=auth["cashier"],
    )
    assert blocked.status_code == 400
    assert "已发药" in blocked.json()["detail"] or "退药" in blocked.json()["detail"]


def test_system_setting_bool_zero_loads_false(client, auth):
    from conftest import TestingSessionLocal
    from app.modules.admin.system_settings import load, save

    db = TestingSessionLocal()
    before = settings.ALLOW_ANONYMOUS_READ
    try:
        save(db, {"ALLOW_ANONYMOUS_READ": False}, "test")
        values = load(db)
        assert values["ALLOW_ANONYMOUS_READ"] is False
        assert settings.ALLOW_ANONYMOUS_READ is False
    finally:
        setattr(settings, "ALLOW_ANONYMOUS_READ", before)
        db.close()


def test_audit_logs_require_admin(client, auth):
    assert client.get("/audit/logs", headers=auth["doctor"]).status_code == 403
    assert client.get("/audit/logs", headers=auth["admin"]).status_code == 200


def test_payment_can_be_recreated_after_full_refund(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "重收费")
    drug = _drug_with_stock(client, auth, "重收费药")
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1}, headers=auth["doctor"],
    )
    first = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert first.status_code == 201, first.text
    refund = client.post(
        f"/payments/{first.json()['id']}/refund",
        json={"reason": "测试全额退"}, headers=auth["cashier"],
    )
    assert refund.status_code == 200, refund.text
    lab = client.post(
        "/lab/items/", json={"code": "RECHARGE", "name": "重收费检验", "price": 12},
        headers=auth["admin"],
    ).json()
    added = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": lab["id"]}, headers=auth["doctor"],
    )
    assert added.status_code == 201, added.text
    second = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert second.status_code == 201, second.text


def test_complete_with_pending_can_waive(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "作废后完诊")
    lab = client.post(
        "/lab/items/", json={"code": "WAIVELAB", "name": "待收检验", "price": 20},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": lab["id"]}, headers=auth["doctor"],
    )
    blocked = client.post(
        f"/encounters/{encounter['id']}/complete", headers=auth["doctor"]
    )
    assert blocked.status_code == 400
    assert "仍有待收费" in blocked.json()["detail"]
    completed = client.post(
        f"/encounters/{encounter['id']}/complete",
        params={"waive_pending": "true"}, headers=auth["doctor"],
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "closed"


def test_abandoned_registration_can_be_reopened(client, auth):
    _patient, _doctor, registration, encounter = _encounter(client, auth, "放弃重开")
    abandoned = client.post(
        f"/encounters/{encounter['id']}/abandon", headers=auth["doctor"]
    )
    assert abandoned.status_code == 200
    reopened = client.post(
        "/encounters/", json={"registration_id": registration["id"]},
        headers=auth["doctor"],
    )
    assert reopened.status_code == 201, reopened.text
    assert reopened.json()["id"] != encounter["id"]
    rows = client.get(
        "/encounters/", params={"patient_id": _patient["id"]}, headers=auth["doctor"]
    ).json()
    assert {row["status"] for row in rows} >= {"abandoned", "open"}


def test_pharmacy_call_requires_reviewed_prescription(client, auth, monkeypatch):
    from app import settings as app_settings

    monkeypatch.setattr(app_settings, "REQUIRE_PRESCRIPTION_REVIEW", True)
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "待审叫号")
    drug = _drug_with_stock(client, auth, "待审药")
    rx = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1}, headers=auth["doctor"],
    )
    assert rx.status_code == 201, rx.text
    pay = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert pay.status_code == 201, pay.text
    called = client.post(
        f"/pharmacy/calls/{encounter['id']}",
        json={"window_no": "1"}, headers=auth["pharmacist"],
    )
    assert called.status_code == 400
    assert "审核" in called.json()["detail"]


def test_discount_refund_never_exceeds_self_pay(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "折扣退费")
    item = client.post(
        "/lab/items/",
        json={"code": "DISCOUNT", "name": "折扣项目", "price": 100},
        headers=auth["admin"],
    ).json()
    assert client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).status_code == 201
    paid = client.post(
        "/payments/", json={
            "encounter_id": encounter["id"], "channel": "cash",
            "discount_amount": 10, "discount_reason": "测试折扣",
        }, headers=auth["admin"],
    )
    assert paid.status_code == 201, paid.text
    payment = paid.json()
    refunded = client.post(
        f"/payments/{payment['id']}/refund", json={"reason": "全额退"},
        headers=auth["admin"],
    )
    assert refunded.status_code == 200, refunded.text
    body = refunded.json()
    assert body["status"] == "refunded"
    assert body["refunded_amount"] <= body["amount"] + 0.01
    assert body["net_amount"] >= -0.01


def test_admin_can_disable_reset_user_and_hr_resign_links(client, auth):
    import base64

    created = client.post(
        "/users/", json={"username": "lifecycle1", "password": "Oldpass1", "role": "nurse"},
        headers=auth["admin"],
    )
    assert created.status_code == 201, created.text
    user = created.json()
    old = {"Authorization": "Basic " + base64.b64encode(b"lifecycle1:Oldpass1").decode()}
    assert client.get("/auth/me", headers=old).status_code == 200
    disabled = client.patch(
        f"/users/{user['id']}/active", json={"active": False}, headers=auth["admin"]
    )
    assert disabled.status_code == 200, disabled.text
    assert client.get("/auth/me", headers=old).status_code == 403
    enabled = client.patch(
        f"/users/{user['id']}/active", json={"active": True}, headers=auth["admin"]
    )
    assert enabled.status_code == 200
    reset = client.post(
        f"/users/{user['id']}/reset-password", json={"password": "Newpass1"},
        headers=auth["admin"],
    )
    assert reset.status_code == 200, reset.text
    new = {"Authorization": "Basic " + base64.b64encode(b"lifecycle1:Newpass1").decode()}
    assert client.get("/auth/me", headers=new).status_code == 200
    assert client.get("/auth/me", headers=old).status_code == 401


def test_hr_resign_disables_linked_account(client, auth):
    import base64

    employee = client.post(
        "/hr/employees/",
        json={"employee_no": "LIFE001", "name": "离职员工", "role": "nurse",
              "hired_at": "2026-01-01"},
        headers=auth["admin"],
    )
    assert employee.status_code == 201, employee.text
    created = client.post(
        "/users/", json={"username": "lifecycle2", "password": "Oldpass1",
                         "role": "nurse", "employee_id": employee.json()["id"]},
        headers=auth["admin"],
    )
    assert created.status_code == 201, created.text
    headers = {"Authorization": "Basic " + base64.b64encode(b"lifecycle2:Oldpass1").decode()}
    assert client.get("/auth/me", headers=headers).status_code == 200
    resigned = client.post(
        f"/hr/employees/{employee.json()['id']}/resign", headers=auth["admin"]
    )
    assert resigned.status_code == 200, resigned.text
    assert client.get("/auth/me", headers=headers).status_code == 403


def test_pending_payment_encounters(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "待收费名单")
    item = client.post(
        "/lab/items/", json={"code": "PENDINGLIST", "name": "待收费检验", "price": 33},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    )
    rows = client.get("/payments/pending-encounters", headers=auth["cashier"]).json()
    assert any(row["encounter_id"] == encounter["id"] for row in rows)


def test_inactive_lab_item_hidden_from_doctor_and_blocked(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "停用检验")
    item = client.post(
        "/lab/items/", json={"code": "INACTIVE", "name": "停用项目", "price": 10},
        headers=auth["admin"],
    ).json()
    client.post(
        "/admin/login", data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    disabled = client.post(f"/admin/lab-items/{item['id']}/toggle", follow_redirects=False)
    assert disabled.status_code == 302
    items = client.get("/lab/items/", headers=auth["doctor"]).json()
    assert all(row["id"] != item["id"] for row in items)
    blocked = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    )
    assert blocked.status_code == 400
    assert "停用" in blocked.json()["detail"]


def test_cancelled_or_dc_exams_leave_worklist(client, auth):
    _patient, _doctor, _registration, encounter = _encounter(client, auth, "取消队列")
    lab_item = client.post(
        "/lab/items/", json={"code": "CANCELQ", "name": "取消队列检验", "price": 10},
        headers=auth["admin"],
    ).json()
    lab = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": lab_item["id"]}, headers=auth["doctor"],
    ).json()
    client.post("/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"])
    stopped = client.post(f"/lab/requests/{lab['id']}/cancel", headers=auth["doctor"])
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["status"] == "dc"
    rows = client.get("/lab/worklist", headers=auth["lab"]).json()
    dc_row = next(row for row in rows if row["id"] == lab["id"])
    assert dc_row["status"] == "dc"
    blocked = client.post(f"/lab/requests/{lab['id']}/collect", headers=auth["lab"])
    assert blocked.status_code == 400
