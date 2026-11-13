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
