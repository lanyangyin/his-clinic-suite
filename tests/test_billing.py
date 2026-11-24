def make_registration(client, auth):
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
    return client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()


def make_drug(client, auth, name, base_price):
    return client.post(
        "/drugs/", json={"name": name, "base_price": base_price}, headers=auth["admin"]
    ).json()


def make_encounter_with_items(client, auth, items):
    """items: [(drug_id, quantity), ...]"""
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    for drug_id, quantity in items:
        client.post(
            f"/encounters/{encounter['id']}/prescriptions",
            json={"drug_id": drug_id, "quantity": quantity},
            headers=auth["doctor"],
        )
    return encounter


def test_payment_sums_items(client, auth):
    drug_a = make_drug(client, auth, "A药", 22.0)
    drug_b = make_drug(client, auth, "B药", 15.5)
    encounter = make_encounter_with_items(
        client, auth, [(drug_a["id"], 3), (drug_b["id"], 2)]
    )
    r = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert r.status_code == 201
    assert r.json()["amount"] == 97.0
    assert r.json()["status"] == "paid"


def test_duplicate_payment_rejected(client, auth):
    drug = make_drug(client, auth, "A药", 1.0)
    encounter = make_encounter_with_items(client, auth, [(drug["id"], 1)])
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    r = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊已收费"


def test_payment_empty_encounter_rejected(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    r = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊没有可收费的费用"


def test_payment_missing_encounter(client, auth):
    r = client.post("/payments/", json={"encounter_id": 999}, headers=auth["cashier"])
    assert r.status_code == 400
    assert r.json()["detail"] == "就诊记录不存在"


def test_payment_closes_encounter(client, auth):
    drug = make_drug(client, auth, "A药", 1.0)
    encounter = make_encounter_with_items(client, auth, [(drug["id"], 1)])
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    got = client.get(f"/encounters/{encounter['id']}").json()
    assert got["status"] == "closed"
    # 已关闭就诊不能再开处方
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "就诊已收费，不能再开处方"


def test_refund_payment(client, auth):
    drug = make_drug(client, auth, "A药", 5.0)
    encounter = make_encounter_with_items(client, auth, [(drug["id"], 1)])
    pay = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    r = client.post(f"/payments/{pay['id']}/refund", headers=auth["cashier"])
    assert r.status_code == 200
    assert r.json()["status"] == "refunded"
    # 重复退费被拒
    again = client.post(f"/payments/{pay['id']}/refund", headers=auth["cashier"])
    assert again.status_code == 400
    assert again.json()["detail"] == "该收费已退费"


def test_refund_blocked_after_dispense(client, auth):
    drug = make_drug(client, auth, "A药", 5.0)
    encounter = make_encounter_with_items(client, auth, [(drug["id"], 1)])
    pay = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": "B001", "expiry": "2027-06-30", "quantity": 10},
        headers=auth["pharmacist"],
    )
    client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    r = client.post(f"/payments/{pay['id']}/refund", headers=auth["cashier"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊已发药，不能退费"


def test_refund_missing_payment(client, auth):
    r = client.post("/payments/999/refund", headers=auth["cashier"])
    assert r.status_code == 400
    assert r.json()["detail"] == "收费记录不存在"


def test_summary(client, auth):
    drug = make_drug(client, auth, "A药", 10.0)
    paid = make_encounter_with_items(client, auth, [(drug["id"], 2)])
    client.post("/payments/", json={"encounter_id": paid["id"]}, headers=auth["cashier"])
    refunded = make_encounter_with_items(client, auth, [(drug["id"], 3)])
    pay = client.post(
        "/payments/", json={"encounter_id": refunded["id"]}, headers=auth["cashier"]
    ).json()
    client.post(f"/payments/{pay['id']}/refund", headers=auth["cashier"])
    r = client.get("/payments/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["paid_count"] == 1
    assert body["paid_total"] == 20.0
    assert body["refunded_count"] == 1
    assert body["refunded_total"] == 30.0


def test_get_payment(client, auth):
    drug = make_drug(client, auth, "A药", 5.0)
    encounter = make_encounter_with_items(client, auth, [(drug["id"], 1)])
    pay = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    r = client.get(f"/payments/{pay['id']}")
    assert r.status_code == 200
    assert r.json()["amount"] == 5.0


def test_get_payment_missing(client):
    assert client.get("/payments/999").status_code == 404


def test_mixed_payment_can_be_partially_refunded(client, auth, monkeypatch):
    from app import settings

    monkeypatch.setattr(settings, 'INSURANCE_ENABLED', False)
    d1 = client.post('/drugs/', json={'name': '混合退费A', 'base_price': 30.0}, headers=auth['admin']).json()
    d2 = client.post('/drugs/', json={'name': '混合退费B', 'base_price': 30.0}, headers=auth['admin']).json()
    encounter = make_encounter_with_items(client, auth, [(d1['id'], 1), (d2['id'], 1)])
    paid = client.post(
        '/payments/',
        json={
            'encounter_id': encounter['id'],
            'allocations': [
                {'channel': 'cash', 'amount': 30.0},
                {'channel': 'wechat', 'amount': 30.0},
            ],
        },
        headers=auth['cashier'],
    )
    assert paid.status_code == 201, paid.text
    assert paid.json()['channel'] == 'mixed'
    charges = client.get(f"/charges/encounters/{encounter['id']}", headers=auth['cashier']).json()
    charge = next(row for row in charges if row['status'] == 'paid')
    refunded = client.post(
        f"/payments/{paid.json()['id']}/refund",
        json={'items': [{'charge_id': charge['id'], 'quantity': 1}]},
        headers=auth['cashier'],
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()['status'] in ('partially_refunded', 'refunded')


def test_large_refund_requires_admin(client, auth, monkeypatch):
    from app import settings

    monkeypatch.setattr(settings, "INSURANCE_ENABLED", False)
    monkeypatch.setattr(settings, "REFUND_APPROVAL_THRESHOLD", 500.0)
    drug = make_drug(client, auth, "大额退费药", 600.0)
    encounter = make_encounter_with_items(client, auth, [(drug["id"], 1)])
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert payment.status_code == 201, payment.text
    blocked = client.post(
        f"/payments/{payment.json()['id']}/refund", headers=auth["cashier"]
    )
    assert blocked.status_code == 400
    assert "审批" in blocked.json()["detail"]
    allowed = client.post(
        f"/payments/{payment.json()['id']}/refund",
        json={"reason": "大额退费审批"},
        headers=auth["admin"],
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["status"] == "refunded"
