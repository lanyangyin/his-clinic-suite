def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "复诊流程患者", "id_number": "110101199801019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "复诊流程科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "复诊流程医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    return patient, doctor


def test_follow_up_links_previous_visit(client, auth):
    patient, doctor = _setup(client, auth)
    first = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    assert first["visit_type"] == "initial"
    assert first["original_registration_id"] is None

    first_encounter = client.post(
        "/encounters/",
        json={"registration_id": first["id"], "diagnosis": "上呼吸道感染"},
        headers=auth["doctor"],
    ).json()
    assert first_encounter["visit_type"] == "initial"

    follow = client.post(
        "/registrations/",
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "visit_type": "follow_up",
            "original_registration_id": first["id"],
        },
        headers=auth["cashier"],
    )
    assert follow.status_code == 201, follow.text
    follow = follow.json()
    assert follow["visit_type"] == "follow_up"
    assert follow["original_registration_id"] == first["id"]

    follow_encounter = client.post(
        "/encounters/",
        json={"registration_id": follow["id"], "diagnosis": "上呼吸道感染复诊"},
        headers=auth["doctor"],
    ).json()
    assert follow_encounter["visit_type"] == "follow_up"
    assert follow_encounter["original_encounter_id"] == first_encounter["id"]

    worklist = client.get("/encounters/worklist", headers=auth["doctor"]).json()
    row = next(item for item in worklist if item["registration_id"] == follow["id"])
    assert row["visit_type"] == "follow_up"
    assert row["original_registration_id"] == first["id"]


def test_follow_up_requires_previous_visit(client, auth):
    patient, doctor = _setup(client, auth)
    response = client.post(
        "/registrations/",
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "visit_type": "follow_up",
        },
        headers=auth["cashier"],
    )
    assert response.status_code == 400
    assert "没有历史就诊" in response.json()["detail"]


def test_follow_up_has_no_registration_fee(client, auth):
    patient, doctor = _setup(client, auth)
    for code, name in (("REG", "挂号费"), ("CONSULT", "诊疗费")):
        client.post(
            "/charges/items/",
            json={
                "code": code,
                "name": name,
                "category": "registration" if code == "REG" else "consultation",
                "price": 10.0,
                "insurance_ratio": 0.0,
            },
            headers=auth["admin"],
        )
    first = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    first_enc = client.post(
        "/encounters/",
        json={"registration_id": first["id"], "diagnosis": "高血压"},
        headers=auth["doctor"],
    ).json()
    first_charges = client.get(
        f"/charges/encounters/{first_enc['id']}", headers=auth["cashier"]
    ).json()
    assert any(row["item_name"] == "挂号费" for row in first_charges)

    follow = client.post(
        "/registrations/",
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "visit_type": "follow_up",
            "original_registration_id": first["id"],
        },
        headers=auth["cashier"],
    ).json()
    follow_enc = client.post(
        "/encounters/",
        json={"registration_id": follow["id"], "diagnosis": "高血压复诊"},
        headers=auth["doctor"],
    ).json()
    follow_charges = client.get(
        f"/charges/encounters/{follow_enc['id']}", headers=auth["cashier"]
    ).json()
    assert not any(row["item_name"] == "挂号费" for row in follow_charges)
    assert any(row["item_name"] == "诊疗费" for row in follow_charges)


def test_follow_up_can_convert_to_initial_before_visit(client, auth):
    patient, doctor = _setup(client, auth)
    first = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    client.post(
        "/encounters/",
        json={"registration_id": first["id"], "diagnosis": "高血压"},
        headers=auth["doctor"],
    )
    follow = client.post(
        "/registrations/",
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "visit_type": "follow_up",
            "original_registration_id": first["id"],
        },
        headers=auth["cashier"],
    ).json()
    converted = client.put(
        f"/registrations/{follow['id']}/visit-type",
        json={"visit_type": "initial"},
        headers=auth["cashier"],
    )
    assert converted.status_code == 200, converted.text
    assert converted.json()["visit_type"] == "initial"
    assert converted.json()["original_registration_id"] is None

    # 已接诊后不能再改类型
    client.post(
        "/encounters/",
        json={"registration_id": follow["id"], "diagnosis": "高血压"},
        headers=auth["doctor"],
    )
    rejected = client.put(
        f"/registrations/{follow['id']}/visit-type",
        json={"visit_type": "follow_up"},
        headers=auth["cashier"],
    )
    assert rejected.status_code == 400
    assert "已接诊" in rejected.json()["detail"]
