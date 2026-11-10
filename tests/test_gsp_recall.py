def setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "召回测试患者", "id_number": "110101199001016666"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "召回测试科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "召回测试医生", "department_id": dept["id"]},
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
        "/drugs/", json={"name": "召回测试药", "base_price": 10},
        headers=auth["admin"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"], "batch_no": "RECALL-01",
            "expiry": "2027-12-31", "quantity": 5,
        },
        headers=auth["pharmacist"],
    )
    client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": enc["id"]}, headers=auth["cashier"]
    )
    return patient, enc, drug


def test_active_recall_blocks_dispense(client, auth):
    patient, enc, drug = setup(client, auth)
    recall = client.post(
        "/gsp/recalls",
        json={
            "drug_name": drug["name"], "batch_no": "RECALL-01",
            "reason": "批次质量问题", "level": "1",
        },
        headers=auth["pharmacist"],
    )
    assert recall.status_code == 201, recall.text
    blocked = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": enc["id"], "receiver_name": patient["name"]},
        headers=auth["pharmacist"],
    )
    assert blocked.status_code == 400
    assert "召回" in blocked.json()["detail"]

    stock = client.get(
        f"/pharmacy/stocks?drug_id={drug['id']}", headers=auth["pharmacist"]
    ).json()
    assert sum(row["quantity"] for row in stock) == 5

    client.post(
        f"/gsp/recalls/{recall.json()['id']}/complete", headers=auth["pharmacist"]
    )
    dispensed = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": enc["id"], "receiver_name": patient["name"]},
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    stock = client.get(
        f"/pharmacy/stocks?drug_id={drug['id']}", headers=auth["pharmacist"]
    ).json()
    assert sum(row["quantity"] for row in stock) == 4
