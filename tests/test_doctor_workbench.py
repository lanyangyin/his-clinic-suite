"""医生门诊工作台：队列、就诊摘要、费用预览。"""


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "工作台患者", "id_number": "110101199201019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "工作台内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "工作台医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "工作台诊断"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/",
        json={"name": "工作台药品", "base_price": 12.0, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    return patient, reg, encounter, doctor


def test_doctor_worklist_and_summary(client, auth):
    patient, reg, encounter, doctor = _setup(client, auth)
    worklist = client.get("/encounters/worklist", headers=auth["doctor"])
    assert worklist.status_code == 200
    rows = worklist.json()
    row = next(item for item in rows if item["encounter_id"] == encounter["id"])
    assert row["patient_name"] == "工作台患者"
    assert row["doctor_name"] == "工作台医生"
    assert row["registration_status"] == "visited"
    assert row["pending_amount"] > 0

    summary = client.get(
        f"/encounters/{encounter['id']}/summary", headers=auth["doctor"]
    )
    assert summary.status_code == 200
    data = summary.json()
    assert data["patient_name"] == "工作台患者"
    assert data["diagnosis"] == "工作台诊断"
    assert data["record_signed"] is False
    assert data["prescription_count"] == 1
    assert data["total_amount"] > 0
    assert data["pending_amount"] > 0
    assert data["charges"]


def test_doctor_workbench_permissions(client, auth):
    _, _, encounter, _ = _setup(client, auth)
    assert client.get("/encounters/worklist", headers=auth["cashier"]).status_code == 403
    assert (
        client.get(
            f"/encounters/{encounter['id']}/summary", headers=auth["cashier"]
        ).status_code
        == 403
    )
