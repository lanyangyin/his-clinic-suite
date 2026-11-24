from app import settings


def _encounter(client, auth, name, id_number):
    patient = client.post(
        "/patients/",
        json={"name": name, "id_number": id_number},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": f"{name}科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": f"{name}医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": f"{name}药", "base_price": 100, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    return enc


def test_insurance_disabled_payment_is_self_pay(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "INSURANCE_ENABLED", False)
    enc = _encounter(client, auth, "自费开关", "110101199001017001")
    payment = client.post(
        "/payments/", json={"encounter_id": enc["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    assert payment.status_code == 201, payment.text
    body = payment.json()
    assert body["insurance_amount"] == 0
    assert body["self_pay_amount"] == body["amount"]

    receipt = client.get(f"/print/receipt/{body['id']}")
    assert receipt.status_code == 200
    assert "医保支付" not in receipt.text


def test_insurance_disabled_rejects_insurance_card(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "INSURANCE_ENABLED", False)
    enc = _encounter(client, auth, "医保卡关闭", "110101199001017002")
    response = client.post(
        "/payments/",
        json={"encounter_id": enc["id"], "channel": "insurance_card"},
        headers=auth["cashier"],
    )
    assert response.status_code == 400
    assert "医保" in response.json()["detail"]


def test_insurance_disabled_self_pay_drug_not_blocked(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "INSURANCE_ENABLED", False)
    enc = _encounter(client, auth, "自费开方", "110101199001017003")
    drug = client.post(
        "/drugs/",
        json={"name": "全额自费药", "base_price": 10.0, "insurance_ratio": 0},
        headers=auth["admin"],
    ).json()
    added = client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert added.status_code == 201, added.text


def test_insurance_precheck_is_recorded(client, auth):
    enc = _encounter(client, auth, "医保审计", "110101199001017004")
    rows = client.get(
        "/insurance/transactions",
        params={"encounter_id": enc["id"]},
        headers=auth["doctor"],
    ).json()
    assert rows
    assert rows[0]["encounter_id"] == enc["id"]
    assert rows[0]["drug_name"]
    assert rows[0]["result"] in {"pass", "warn", "forbid", "unavailable"}


def test_insurance_gateway_unavailable_degrades_to_self_pay(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "INSURANCE_GATEWAY_URL", "http://127.0.0.1:1")
    enc = _encounter(client, auth, "网关降级", "110101199001017005")
    rows = client.get(
        "/insurance/transactions",
        params={"encounter_id": enc["id"]},
        headers=auth["doctor"],
    ).json()
    assert any(row["result"] == "unavailable" for row in rows)
