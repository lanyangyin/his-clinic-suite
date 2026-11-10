"""收费员交班与门诊日结。"""
from datetime import date


def _sale(client, auth):
    dept = client.post(
        "/departments/", json={"name": "日结内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "日结医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/",
        json={"name": "日结患者", "id_number": "110101199901019999"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "日结诊断"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "日结药品", "base_price": 25},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    assert payment.status_code in (200, 201)
    return payment.json()


def test_cashier_shift_and_daily(client, auth):
    opened = client.post(
        "/cashier/shifts/open",
        json={"opening_float": 100},
        headers=auth["cashier"],
    )
    assert opened.status_code == 201, opened.text
    shift = opened.json()
    assert shift["shift_no"].startswith("CS")
    duplicate = client.post(
        "/cashier/shifts/open",
        json={"opening_float": 100},
        headers=auth["cashier"],
    )
    assert duplicate.status_code == 400

    payment = _sale(client, auth)
    assert payment["created_by"] == "cashier"
    daily = client.get("/cashier/daily", headers=auth["cashier"]).json()
    assert daily["payment_count"] >= 1
    assert daily["amount"] > 0
    assert daily["channels"][0]["channel"] == "cash"
    assert daily["shifts"]

    expected = round(100 + payment["amount"] - payment.get("refunded_amount", 0), 2)
    closed = client.post(
        f"/cashier/shifts/{shift['id']}/close",
        json={"counted_cash": expected + 5, "note": "交班测试"},
        headers=auth["cashier"],
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["status"] == "closed"
    assert body["expected_cash"] == expected
    assert body["difference"] == 5

    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/cashier-daily")
    assert page.status_code == 200
    assert "门诊收费日结" in page.text

    assert client.get("/cashier/daily", headers=auth["doctor"]).status_code == 403
