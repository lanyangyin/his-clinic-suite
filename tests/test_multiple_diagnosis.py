def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "多诊断患者", "id_number": "110101199701019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "多诊断科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "多诊断医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter_response = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "高血压"},
        headers=auth["doctor"],
    )
    assert encounter_response.status_code == 201, encounter_response.text
    encounter = encounter_response.json()
    return patient, encounter


def test_primary_diagnosis_created(client, auth):
    _, encounter = _setup(client, auth)
    rows = client.get(
        f"/encounters/{encounter['id']}/diagnoses", headers=auth["doctor"]
    ).json()
    assert len(rows) == 1
    assert rows[0]["diagnosis"] == "高血压"
    assert rows[0]["diagnosis_type"] == "primary"
    assert rows[0]["sort_no"] == 0


def test_replace_diagnoses_keeps_order(client, auth):
    _, encounter = _setup(client, auth)
    response = client.put(
        f"/encounters/{encounter['id']}/diagnoses",
        json=[
            {"diagnosis": "高血压", "note": "主要"},
            {"diagnosis": "2型糖尿病", "note": "合并症"},
            {"diagnosis": "高脂血症"},
        ],
        headers=auth["doctor"],
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["diagnosis"] for row in rows] == ["高血压", "2型糖尿病", "高脂血症"]
    assert [row["diagnosis_type"] for row in rows] == [
        "primary",
        "secondary",
        "secondary",
    ]
    assert [row["sort_no"] for row in rows] == [0, 1, 2]

    encounter = client.get(
        f"/encounters/{encounter['id']}", headers=auth["doctor"]
    ).json()
    assert encounter["diagnosis"] == "高血压"

    printed = client.get(f"/print/medical-record/{encounter['id']}")
    assert printed.status_code == 200
    assert "高血压" in printed.text
    assert "2型糖尿病" in printed.text


def test_duplicate_and_empty_diagnosis_rejected(client, auth):
    _, encounter = _setup(client, auth)
    duplicate = client.put(
        f"/encounters/{encounter['id']}/diagnoses",
        json=[{"diagnosis": "高血压"}, {"diagnosis": "高血压"}],
        headers=auth["doctor"],
    )
    assert duplicate.status_code == 400
    assert "重复" in duplicate.json()["detail"]

    empty = client.put(
        f"/encounters/{encounter['id']}/diagnoses",
        json=[],
        headers=auth["doctor"],
    )
    assert empty.status_code == 200
    rows = client.get(
        f"/encounters/{encounter['id']}/diagnoses", headers=auth["doctor"]
    ).json()
    assert rows == []


def test_closed_encounter_diagnosis_rejected(client, auth):
    _, encounter = _setup(client, auth)
    drug = client.post(
        "/drugs/",
        json={"name": "多诊断收费药", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    paid = client.post(
        "/payments/",
        json={"encounter_id": encounter["id"]},
        headers=auth["cashier"],
    )
    assert paid.status_code == 201, paid.text
    response = client.put(
        f"/encounters/{encounter['id']}/diagnoses",
        json=[{"diagnosis": "高血压"}],
        headers=auth["doctor"],
    )
    assert response.status_code == 409
    assert "已收费" in response.json()["detail"]
