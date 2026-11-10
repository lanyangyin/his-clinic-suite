def setup(client, auth):
    admin = auth["admin"]
    client.post(
        "/dict/diagnosis_icd10/entries",
        json={"code": "J06.9", "name": "急性上呼吸道感染"},
        headers=admin,
    )
    client.post(
        "/dict/diagnosis_icd10/entries",
        json={"code": "I10", "name": "高血压"},
        headers=admin,
    )
    patient = client.post(
        "/patients/",
        json={"name": "诊断编码患者", "id_number": "110101199001018888"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "诊断编码科"}, headers=admin
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "诊断编码医生", "department_id": dept["id"]},
        headers=admin,
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    return patient, doctor, reg


def test_dictionary_seed_via_api_and_create_with_code(client, auth):
    patient, doctor, reg = setup(client, auth)
    entries = client.get(
        "/dict/diagnosis_icd10/entries", params={"active_only": True}
    ).json()
    assert any(row["code"] == "J06.9" for row in entries)

    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis_code": "J06.9"},
        headers=auth["doctor"],
    )
    assert encounter.status_code == 201, encounter.text
    body = encounter.json()
    assert body["diagnosis_code"] == "J06.9"
    assert body["diagnosis"] == "急性上呼吸道感染"

    summary = client.get(
        f"/encounters/{body['id']}/summary", headers=auth["doctor"]
    ).json()
    assert summary["diagnosis_code"] == "J06.9"


def test_create_with_name_fills_code(client, auth):
    patient, doctor, reg = setup(client, auth)
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "高血压"},
        headers=auth["doctor"],
    ).json()
    assert encounter["diagnosis_code"] == "I10"


def test_invalid_code_rejected(client, auth):
    patient, doctor, reg = setup(client, auth)
    response = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis_code": "X99.9"},
        headers=auth["doctor"],
    )
    assert response.status_code == 400
    assert "诊断编码" in response.json()["detail"]


def test_update_diagnosis(client, auth):
    patient, doctor, reg = setup(client, auth)
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis_code": "J06.9"},
        headers=auth["doctor"],
    ).json()
    updated = client.put(
        f"/encounters/{encounter['id']}/diagnosis",
        json={"diagnosis_code": "I10"},
        headers=auth["doctor"],
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["diagnosis_code"] == "I10"
    assert updated.json()["diagnosis"] == "高血压"
