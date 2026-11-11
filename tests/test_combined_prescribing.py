def test_one_doctor_prescribes_western_injection_and_tcm(client, auth):
    dept = client.post(
        "/departments/", json={"name": "中西医结合科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "中西医医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/", json={"name": "中西医患者", "id_number": "110101199001019999"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()

    western = client.post(
        "/drugs/", json={"name": "演示西药", "base_price": 10}, headers=auth["admin"]
    ).json()
    injection = client.post(
        "/drugs/",
        json={"name": "演示注射剂", "base_price": 20, "dosage_form": "注射剂"},
        headers=auth["admin"],
    ).json()
    herb = client.post(
        "/tcm/herbs",
        json={"code": "H001", "name": "丹参", "price_per_g": 0.1},
        headers=auth["admin"],
    ).json()

    for drug in (western, injection):
        response = client.post(
            f"/encounters/{enc['id']}/prescriptions",
            json={"drug_id": drug["id"], "quantity": 1, "route": "静滴" if drug is injection else "口服"},
            headers=auth["doctor"],
        )
        assert response.status_code == 201, response.text

    tcm = client.post(
        f"/tcm/encounters/{enc['id']}/prescriptions",
        json={
            "formula_name": "演示方",
            "packs": 1,
            "items": [{"herb_id": herb["id"], "dose_g": 10}],
        },
        headers=auth["doctor"],
    )
    assert tcm.status_code == 201, tcm.text
    assert tcm.json()["total_amount"] == 1.0
    prescriptions = client.get(
        f"/encounters/{enc['id']}/prescriptions", headers=auth["doctor"]
    )
    assert prescriptions.status_code == 200
    assert len(prescriptions.json()) == 2
    summary = client.get(f"/charges/encounters/{enc['id']}/summary")
    assert summary.json()["total_pending"] >= 31
