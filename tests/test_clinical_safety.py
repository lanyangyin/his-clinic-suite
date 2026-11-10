def setup_patient_with_allergy(client, auth):
    patient = client.post(
        "/patients/",
        json={
            "name": "过敏测试患者",
            "id_type": "id_card",
            "id_number": "110101199001019999",
            "phone": "13800138009",
            "address": "测试地址",
            "emergency_contact_name": "家属",
            "emergency_contact_phone": "13900139009",
            "allergy_status": "present",
            "allergy_detail": "青霉素",
            "privacy_consent": True,
        },
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "过敏测试科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "过敏测试医生", "department_id": dept["id"]},
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
    return patient, doctor, reg, encounter


def test_allergy_hard_stop_and_override(client, auth):
    patient, doctor, reg, encounter = setup_patient_with_allergy(client, auth)
    drug = client.post(
        "/drugs/",
        json={"name": "阿莫西林胶囊", "base_price": 12.0},
        headers=auth["admin"],
    ).json()
    blocked = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert blocked.status_code == 400
    assert "过敏" in blocked.json()["detail"]
    assert "override" in blocked.json()["detail"]

    overridden = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={
            "drug_id": drug["id"],
            "quantity": 1,
            "allergy_override_reason": "皮试阴性，既往可耐受",
        },
        headers=auth["doctor"],
    )
    assert overridden.status_code == 201, overridden.text
    body = overridden.json()
    assert body["allergy_override_reason"] == "皮试阴性，既往可耐受"
    assert body["allergy_override_by"] == "doctor"
    assert "阿莫西林" in (body["allergy_warning"] or "")


def test_non_allergy_drug_not_blocked(client, auth):
    patient, doctor, reg, encounter = setup_patient_with_allergy(client, auth)
    drug = client.post(
        "/drugs/", json={"name": "维生素C片", "base_price": 3.0},
        headers=auth["admin"],
    ).json()
    response = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert response.status_code == 201
    assert response.json()["allergy_warning"] is None


def test_triage_vitals_and_doctor_worklist(client, auth):
    patient, doctor, reg, encounter = setup_patient_with_allergy(client, auth)
    ticket = client.post(
        "/triage/tickets",
        json={
            "registration_id": reg["id"],
            "triage_level": 2,
            "chief_complaint": "胸闷气促",
            "temperature": 38.6,
            "pulse": 118,
            "respiration": 26,
            "systolic": 90,
            "diastolic": 60,
            "spo2": 92,
            "pain_score": 6,
            "isolation": True,
        },
        headers=auth["nurse"],
    )
    assert ticket.status_code == 201, ticket.text
    body = ticket.json()
    assert body["triage_level"] == 2
    assert body["temperature"] == 38.6
    assert body["bp_display"] == "90/60"
    assert "SpO2 92%" in body["vital_summary"]
    assert body["isolation"] is True
    assert body["assessed_by"] == "nurse"

    queue = client.get("/triage/queue", headers=auth["nurse"]).json()
    assert queue[0]["triage_level"] == 2

    worklist = client.get("/encounters/worklist", headers=auth["doctor"]).json()
    row = next(item for item in worklist if item["registration_id"] == reg["id"])
    assert row["triage_level"] == 2
    assert row["temperature"] == 38.6
    assert row["spo2"] == 92
    assert row["isolation"] is True


def test_triage_level_range(client, auth):
    patient, doctor, reg, encounter = setup_patient_with_allergy(client, auth)
    response = client.post(
        "/triage/tickets",
        json={"registration_id": reg["id"], "triage_level": 5},
        headers=auth["nurse"],
    )
    assert response.status_code == 422
