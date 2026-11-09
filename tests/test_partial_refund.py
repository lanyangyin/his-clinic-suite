import time


def make_encounter(client, auth, items):
    suffix = str(int(time.time() * 1000))[-12:]
    patient = client.post(
        "/patients/",
        json={"name": f"部分退费{suffix[-4:]}", "id_number": f"110101{suffix}"},
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
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    for drug_id, quantity in items:
        client.post(
            f"/encounters/{encounter['id']}/prescriptions",
            json={"drug_id": drug_id, "quantity": quantity},
            headers=auth["doctor"],
        )
    return encounter


def make_drug(client, auth, name, price, ratio=0.0):
    return client.post(
        "/drugs/",
        json={"name": name, "base_price": price, "insurance_ratio": ratio},
        headers=auth["admin"],
    ).json()


def allow_self_pay(monkeypatch):
    """医保服务降级，处方按自费放行（用于构造全自费收费）。"""
    import app.modules.encounter.service as encounter_service
    from app.modules.insurance.adapter import InsuranceUnavailable

    def down(**kwargs):
        raise InsuranceUnavailable("医保服务不可用")

    monkeypatch.setattr(encounter_service, "check_prescription", down)


def test_partial_refund_one_pill(client, auth, monkeypatch):
    allow_self_pay(monkeypatch)
    drug_a = make_drug(client, auth, "A药", 10.0)
    drug_b = make_drug(client, auth, "B药", 5.0)
    encounter = make_encounter(client, auth, [(drug_a["id"], 2), (drug_b["id"], 1)])
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    assert payment["amount"] == 25.0

    charges = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()
    charge_a = next(c for c in charges if c["item_name"] == "A药")
    charge_b = next(c for c in charges if c["item_name"] == "B药")

    r = client.post(
        f"/payments/{payment['id']}/refund",
        json={"items": [{"charge_id": charge_a["id"], "quantity": 1}]},
        headers=auth["cashier"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "partially_refunded"
    assert body["refunded_amount"] == 10.0
    assert body["refunded_insurance_amount"] == 0.0
    assert body["refunded_self_pay_amount"] == 10.0

    charges = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()
    charge_a = next(c for c in charges if c["item_name"] == "A药")
    charge_b = next(c for c in charges if c["item_name"] == "B药")
    assert charge_a["refunded_quantity"] == 1
    assert charge_a["status"] == "partially_refunded"
    assert charge_b["refunded_quantity"] == 0
    assert charge_b["status"] == "paid"

    over = client.post(
        f"/payments/{payment['id']}/refund",
        json={"items": [{"charge_id": charge_a["id"], "quantity": 2}]},
        headers=auth["cashier"],
    )
    assert over.status_code == 400
    assert "超过可退数量" in over.json()["detail"]

    rest = client.post(
        f"/payments/{payment['id']}/refund",
        json={"items": [{"charge_id": charge_a["id"], "quantity": 1}]},
        headers=auth["cashier"],
    ).json()
    assert rest["status"] == "partially_refunded"

    final = client.post(
        f"/payments/{payment['id']}/refund",
        json={"items": [{"charge_id": charge_b["id"], "quantity": 1}]},
        headers=auth["cashier"],
    ).json()
    assert final["status"] == "refunded"
    assert final["refunded_amount"] == 25.0

    again = client.post(f"/payments/{payment['id']}/refund", headers=auth["cashier"])
    assert again.status_code == 400
    assert again.json()["detail"] == "该收费已退费"


def test_refund_drug_blocked_after_dispense(client, auth, monkeypatch):
    allow_self_pay(monkeypatch)
    drug = make_drug(client, auth, "已发药", 10.0)
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "PR-B1",
            "expiry": "2028-12-31",
            "quantity": 5,
        },
        headers=auth["pharmacist"],
    )
    encounter = make_encounter(client, auth, [(drug["id"], 1)])
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    charge = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()[0]

    blocked = client.post(
        f"/payments/{payment['id']}/refund",
        json={"items": [{"charge_id": charge["id"], "quantity": 1}]},
        headers=auth["cashier"],
    )
    assert blocked.status_code == 400
    assert "先退药" in blocked.json()["detail"]

    all_blocked = client.post(
        f"/payments/{payment['id']}/refund", headers=auth["cashier"]
    )
    assert all_blocked.status_code == 400
    assert all_blocked.json()["detail"] == "该就诊已发药，不能退费"

def test_insurance_payment_only_allows_full_refund(client, auth):
    drug = make_drug(client, auth, "医保药", 10.0, ratio=0.7)
    encounter = make_encounter(client, auth, [(drug["id"], 2)])
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    assert payment["insurance_amount"] == 14.0
    charge = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()[0]

    partial = client.post(
        f"/payments/{payment['id']}/refund",
        json={"items": [{"charge_id": charge["id"], "quantity": 1}]},
        headers=auth["cashier"],
    )
    assert partial.status_code == 400
    assert "医保收费只能全额退费" in partial.json()["detail"]

    full = client.post(
        f"/payments/{payment['id']}/refund", headers=auth["cashier"]
    )
    assert full.status_code == 200, full.text
    body = full.json()
    assert body["status"] == "refunded"
    assert body["refunded_amount"] == 20.0
    assert body["refunded_insurance_amount"] == 14.0

def test_insurance_card_channel_only_allows_full_refund(client, auth, monkeypatch):
    allow_self_pay(monkeypatch)
    drug = make_drug(client, auth, "医保卡药", 10.0)
    encounter = make_encounter(client, auth, [(drug["id"], 2)])
    payment = client.post(
        "/payments/",
        json={
            "encounter_id": encounter["id"],
            "channel": "insurance_card",
            "card_no": "YB123456",
        },
        headers=auth["cashier"],
    ).json()
    assert payment["insurance_amount"] == 0.0
    charge = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()[0]
    partial = client.post(
        f"/payments/{payment['id']}/refund",
        json={"items": [{"charge_id": charge["id"], "quantity": 1}]},
        headers=auth["cashier"],
    )
    assert partial.status_code == 400
    assert "医保收费只能全额退费" in partial.json()["detail"]

    full = client.post(f"/payments/{payment['id']}/refund", headers=auth["cashier"])
    assert full.status_code == 200
    assert full.json()["status"] == "refunded"
