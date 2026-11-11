def _encounter(client, auth, suffix):
    dept = client.post("/departments/", json={"name": f"混合科{suffix}"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": f"混合医生{suffix}", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/", json={"name": f"混合患者{suffix}", "id_number": f"11010119900101{suffix}"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/", json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": f"混合药{suffix}", "base_price": 100},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1}, headers=auth["doctor"],
    )
    summary = client.get(f"/charges/encounters/{enc['id']}/summary").json()
    return enc, round(summary.get("total_pending", 0), 2)


def test_mixed_payment_allocations(client, auth):
    enc, _total = _encounter(client, auth, "41")
    cash = 15.00
    wechat = 15.00
    response = client.post(
        "/payments/",
        json={
            "encounter_id": enc["id"],
            "allocations": [
                {"channel": "cash", "amount": cash},
                {"channel": "wechat", "amount": wechat},
            ],
        },
        headers=auth["cashier"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["channel"] == "mixed"
    assert body["self_pay_amount"] == 30.0
    assert len(body["allocations"]) == 2


def test_discount_requires_admin_and_reason(client, auth):
    enc, total = _encounter(client, auth, "42")
    denied = client.post(
        "/payments/",
        json={"encounter_id": enc["id"], "discount_amount": 5, "discount_reason": "员工"},
        headers=auth["cashier"],
    )
    assert denied.status_code == 400
    assert "折扣权限" in denied.json()["detail"]

    enc2, total2 = _encounter(client, auth, "43")
    approved = client.post(
        "/payments/",
        json={"encounter_id": enc2["id"], "discount_amount": 5, "discount_reason": "员工"},
        headers=auth["admin"],
    )
    assert approved.status_code == 201, approved.text
    body = approved.json()
    assert body["discount_amount"] == 5
    assert body["self_pay_amount"] == round(
        body["amount"] - body["insurance_amount"] - 5, 2
    )
    assert body["discount_by"] == "admin"
    receipt = client.get(f"/print/receipt/{body['id']}")
    assert "优惠/减免" in receipt.text
