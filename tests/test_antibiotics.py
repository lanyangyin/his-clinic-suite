def make_encounter(client, auth):
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
    return client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感染"},
        headers=auth["doctor"],
    ).json()


def make_drug(client, auth, name="阿莫西林胶囊", level=0, price=12.5):
    return client.post(
        "/drugs/",
        json={"name": name, "base_price": price, "antibiotic_level": level},
        headers=auth["admin"],
    ).json()


def prescribe(client, auth, encounter_id, drug_id, quantity=1):
    return client.post(
        f"/encounters/{encounter_id}/prescriptions",
        json={"drug_id": drug_id, "quantity": quantity},
        headers=auth["doctor"],
    )


def test_non_antibiotic_allowed(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, level=0)
    r = prescribe(client, auth, encounter["id"], drug["id"])
    assert r.status_code == 201


def test_level1_antibiotic_allowed(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, level=1)
    r = prescribe(client, auth, encounter["id"], drug["id"])
    assert r.status_code == 201


def test_level2_antibiotic_allowed(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, level=2)
    r = prescribe(client, auth, encounter["id"], drug["id"])
    assert r.status_code == 201


def test_level3_antibiotic_blocked(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, level=3)
    r = prescribe(client, auth, encounter["id"], drug["id"])
    assert r.status_code == 400
    assert "会诊审批" in r.json()["detail"]


def test_invalid_antibiotic_level_rejected(client, auth):
    r = client.post(
        "/drugs/",
        json={"name": "X药", "base_price": 1.0, "antibiotic_level": 4},
        headers=auth["admin"],
    )
    assert r.status_code == 422


def test_duplicate_drug_in_same_prescription_blocked(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, level=0)
    first = prescribe(client, auth, encounter["id"], drug["id"], quantity=2)
    assert first.status_code == 201
    second = prescribe(client, auth, encounter["id"], drug["id"], quantity=1)
    assert second.status_code == 400
    assert second.json()["detail"] == "该药品已在处方中，请勿重复开立"


def test_different_drugs_allowed(client, auth):
    encounter = make_encounter(client, auth)
    drug_a = make_drug(client, auth, name="A药", price=1.0)
    drug_b = make_drug(client, auth, name="B药", price=2.0)
    assert prescribe(client, auth, encounter["id"], drug_a["id"]).status_code == 201
    assert prescribe(client, auth, encounter["id"], drug_b["id"]).status_code == 201


def test_duplicate_check_per_encounter(client, auth):
    """同一药品在不同就诊中可分别开立。"""
    encounter_a = make_encounter(client, auth)
    drug = make_drug(client, auth)
    assert prescribe(client, auth, encounter_a["id"], drug["id"]).status_code == 201

    # 新患者新就诊，同药可开
    patient = client.post(
        "/patients/", json={"name": "李四", "id_number": "110101199501011234"},
        headers=auth["cashier"],
    ).json()
    department = client.get("/departments/1").json()
    doctor = client.get("/doctors/1").json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter_b = client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感染"},
        headers=auth["doctor"],
    ).json()
    assert prescribe(client, auth, encounter_b["id"], drug["id"]).status_code == 201


def test_drug_detail_includes_level(client, auth):
    drug = make_drug(client, auth, level=2)
    got = client.get(f"/drugs/{drug['id']}").json()
    assert got["antibiotic_level"] == 2
