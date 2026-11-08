from datetime import date

TODAY = date.today().isoformat()
MONTH = TODAY[:7]


def make_encounter_with_payment(client, auth, drug_price=10.0, quantity=1):
    """建一次完整门诊就诊并收费，返回 payment。"""
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": drug_price, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": quantity},
        headers=auth["doctor"],
    )
    return client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()


def test_daily_close(client, auth):
    payment = make_encounter_with_payment(client, auth, drug_price=10.0, quantity=2)
    assert payment["amount"] == 20.0
    r = client.post(
        "/finance/daily-close", json={"close_date": TODAY}, headers=auth["admin"]
    )
    assert r.status_code == 201
    body = r.json()
    assert body["outpatient_paid_count"] == 1
    assert body["outpatient_paid_amount"] == 20.0
    assert body["insurance_amount"] == 16.0  # 20 * 0.8
    assert body["closed_by"] == "admin"


def test_daily_close_with_refund(client, auth):
    payment = make_encounter_with_payment(client, auth)
    client.post(f"/payments/{payment['id']}/refund", headers=auth["cashier"])
    r = client.post(
        "/finance/daily-close", json={"close_date": TODAY}, headers=auth["admin"]
    )
    body = r.json()
    assert body["outpatient_paid_count"] == 0
    assert body["outpatient_paid_amount"] == 0.0
    assert body["outpatient_refunded_count"] == 1
    assert body["outpatient_refunded_amount"] == 10.0


def test_duplicate_daily_close_rejected(client, auth):
    client.post("/finance/daily-close", json={"close_date": TODAY}, headers=auth["admin"])
    r = client.post(
        "/finance/daily-close", json={"close_date": TODAY}, headers=auth["admin"]
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该日已日结"


def test_get_daily_close(client, auth):
    client.post("/finance/daily-close", json={"close_date": TODAY}, headers=auth["admin"])
    r = client.get(f"/finance/daily-close/{TODAY}")
    assert r.status_code == 200
    assert r.json()["close_date"] == TODAY


def test_get_missing_daily_close(client):
    r = client.get("/finance/daily-close/2020-01-01")
    assert r.status_code == 404
    assert r.json()["detail"] == "该日未日结"


def test_list_closures(client, auth):
    client.post("/finance/daily-close", json={"close_date": TODAY}, headers=auth["admin"])
    r = client.get("/finance/daily-closes")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_monthly_summary(client, auth):
    make_encounter_with_payment(client, auth, drug_price=10.0, quantity=3)
    client.post("/finance/daily-close", json={"close_date": TODAY}, headers=auth["admin"])
    r = client.get(f"/finance/monthly-summary?month={MONTH}")
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == MONTH
    assert body["outpatient_paid_count"] == 1
    assert body["outpatient_paid_amount"] == 30.0
    assert body["insurance_amount"] == 24.0
    assert body["closed_days"] == 1


def test_monthly_summary_invalid_month(client):
    r = client.get("/finance/monthly-summary?month=2026-13")
    assert r.status_code == 400
    r = client.get("/finance/monthly-summary?month=abc")
    assert r.status_code in (400, 500)


def test_role_protection(client, auth):
    # 收费员不能日结
    r = client.post(
        "/finance/daily-close", json={"close_date": TODAY}, headers=auth["cashier"]
    )
    assert r.status_code == 403
    # 未登录不能日结
    r = client.post("/finance/daily-close", json={"close_date": TODAY})
    assert r.status_code == 401
