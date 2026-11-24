def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "删除处方患者", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "删除处方科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "删除处方医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": registration["id"]},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "删除测试药", "base_price": 12.5}, headers=auth["admin"]
    ).json()
    item = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    ).json()
    return encounter, item


def test_delete_prescription_removes_unpaid_charge(client, auth):
    encounter, item = _setup(client, auth)
    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    assert charges

    response = client.delete(
        f"/encounters/{encounter['id']}/prescriptions/{item['id']}",
        headers=auth["doctor"],
    )
    assert response.status_code == 204, response.text
    assert client.get(f"/encounters/{encounter['id']}/prescriptions").json() == []
    assert client.get(f"/charges/encounters/{encounter['id']}").json() == []


def test_cannot_delete_prescription_after_payment(client, auth):
    encounter, item = _setup(client, auth)
    paid = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert paid.status_code == 201, paid.text
    response = client.delete(
        f"/encounters/{encounter['id']}/prescriptions/{item['id']}",
        headers=auth["doctor"],
    )
    assert response.status_code == 409


def test_batch_prescription_and_failure_rollback(client, auth):
    encounter, _item = _setup(client, auth)
    drug_a = client.post(
        "/drugs/", json={"name": "批量A药", "base_price": 2.0}, headers=auth["admin"]
    ).json()
    drug_b = client.post(
        "/drugs/", json={"name": "批量B药", "base_price": 3.0}, headers=auth["admin"]
    ).json()
    response = client.post(
        f"/encounters/{encounter['id']}/prescriptions/batch",
        json={
            "items": [
                {"drug_id": drug_a["id"], "quantity": 1},
                {"drug_id": drug_b["id"], "quantity": 2},
            ]
        },
        headers=auth["doctor"],
    )
    assert response.status_code == 201, response.text
    assert len(response.json()) == 2
    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    assert any(row["item_name"] == "批量A药" for row in charges)

    before = len(client.get(f"/encounters/{encounter['id']}/prescriptions").json())
    failed = client.post(
        f"/encounters/{encounter['id']}/prescriptions/batch",
        json={
            "items": [
                {"drug_id": drug_a["id"], "quantity": 1},
                {"drug_id": 999999, "quantity": 1},
            ]
        },
        headers=auth["doctor"],
    )
    assert failed.status_code in (400, 404)
    after = len(client.get(f"/encounters/{encounter['id']}/prescriptions").json())
    assert after == before


def test_western_prescription_five_drug_limit(client, auth):
    encounter, _item = _setup(client, auth)
    for index in range(2, 6):
        drug = client.post(
            "/drugs/",
            json={"name": f"五种上限药{index}", "base_price": 1.0},
            headers=auth["admin"],
        ).json()
        response = client.post(
            f"/encounters/{encounter['id']}/prescriptions",
            json={"drug_id": drug["id"], "quantity": 1},
            headers=auth["doctor"],
        )
        assert response.status_code == 201, response.text
    sixth = client.post(
        "/drugs/", json={"name": "第六种上限药", "base_price": 1.0}, headers=auth["admin"]
    ).json()
    blocked = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": sixth["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert blocked.status_code == 400
    assert "5" in blocked.json()["detail"]
