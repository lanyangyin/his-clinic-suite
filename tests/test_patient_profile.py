"""患者 360：基本信息、就诊、预约、档案、费用统计。"""
from datetime import date


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "360患者", "id_number": "110101199401019999", "phone": "13800000003"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "360内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "360医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    schedule = client.post(
        "/schedules/",
        json={
            "doctor_id": doctor["id"],
            "schedule_date": date.today().isoformat(),
            "period": "morning",
            "capacity": 5,
        },
        headers=auth["admin"],
    ).json()
    appointment = client.post(
        "/appointments/",
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "schedule_id": schedule["id"],
        },
        headers=auth["cashier"],
    ).json()
    checked = client.post(
        f"/appointments/{appointment['id']}/check-in", headers=auth["cashier"]
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": checked["registration_id"], "diagnosis": "360诊断"},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/medical-record",
        json={"chief_complaint": "头晕", "present_illness": "1 天"},
        headers=auth["doctor"],
    )
    drug = client.post(
        "/drugs/",
        json={"name": "360药品", "base_price": 8.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    ).json()
    archive = client.post(
        "/archive/records",
        json={"patient_id": patient["id"], "encounter_id": encounter["id"]},
        headers=auth["archive"],
    ).json()
    return patient, appointment, encounter, payment, archive


def test_patient_profile_aggregates(client, auth):
    patient, appointment, encounter, payment, archive = _setup(client, auth)
    response = client.get(
        f"/patients/{patient['id']}/profile", headers=auth["doctor"]
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["patient"]["name"] == "360患者"
    assert data["stats"]["visit_count"] == 1
    assert data["stats"]["appointment_count"] == 1
    assert data["stats"]["archive_count"] == 1
    assert data["stats"]["prescription_count"] == 1
    assert data["stats"]["total_paid"] > 0
    assert data["stats"]["last_visit"] is not None
    assert data["appointments"][0]["id"] == appointment["id"]
    assert data["archives"][0]["archive_no"] == archive["archive_no"]
    assert data["encounters"][0]["id"] == encounter["id"]
    assert data["encounters"][0]["payments"][0]["id"] == payment["id"]


def test_patient_profile_missing_and_permissions(client, auth):
    assert (
        client.get("/patients/99999/profile", headers=auth["doctor"]).status_code
        == 404
    )
    patient, _, _, _, _ = _setup(client, auth)
    assert (
        client.get(
            f"/patients/{patient['id']}/profile", headers=auth["cashier"]
        ).status_code
        == 403
    )
