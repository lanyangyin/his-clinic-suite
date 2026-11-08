def setup_data(client, auth):
    """建建档患者、医生与一次就诊（含待缴费处方）。"""
    patient = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234"},
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
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0, "insurance_ratio": 0.8},
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
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    return patient, doctor, encounter


def test_kiosk_registration(client, auth):
    patient, doctor, encounter = setup_data(client, auth)
    r = client.post(
        "/kiosk/registrations",
        json={"patient_id_number": patient["id_number"], "doctor_id": doctor["id"]},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "registered"
    assert body["patient_id"] == patient["id"]


def test_kiosk_registration_patient_not_registered(client, auth):
    patient, doctor, encounter = setup_data(client, auth)
    r = client.post(
        "/kiosk/registrations",
        json={"patient_id_number": "999999999999999999", "doctor_id": doctor["id"]},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "患者未建档，请先到建档窗口办理"


def test_kiosk_registration_with_schedule(client, auth):
    patient, doctor, encounter = setup_data(client, auth)
    schedule = client.post(
        "/schedules/",
        json={"doctor_id": doctor["id"], "schedule_date": "2026-11-12", "period": "morning", "capacity": 1},
        headers=auth["admin"],
    ).json()
    r = client.post(
        "/kiosk/registrations",
        json={
            "patient_id_number": patient["id_number"],
            "doctor_id": doctor["id"],
            "schedule_id": schedule["id"],
        },
    )
    assert r.status_code == 201
    # 号源已满
    r = client.post(
        "/kiosk/registrations",
        json={
            "patient_id_number": patient["id_number"],
            "doctor_id": doctor["id"],
            "schedule_id": schedule["id"],
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该时段号源已满"


def test_kiosk_get_registration(client, auth):
    patient, doctor, encounter = setup_data(client, auth)
    reg = client.post(
        "/kiosk/registrations",
        json={"patient_id_number": patient["id_number"], "doctor_id": doctor["id"]},
    ).json()
    r = client.get(f"/kiosk/registrations/{reg['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == reg["id"]
    assert client.get("/kiosk/registrations/999").status_code == 404


def test_kiosk_payment(client, auth):
    patient, doctor, encounter = setup_data(client, auth)
    r = client.post("/kiosk/payments", json={"encounter_id": encounter["id"]})
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == 20.0
    assert body["status"] == "paid"
    assert body["insurance_amount"] == 16.0
    assert body["self_pay_amount"] == 4.0

    # 重复缴费
    again = client.post("/kiosk/payments", json={"encounter_id": encounter["id"]})
    assert again.status_code == 400
    assert again.json()["detail"] == "该就诊已收费"


def test_kiosk_payment_missing_encounter(client, auth):
    r = client.post("/kiosk/payments", json={"encounter_id": 999})
    assert r.status_code == 400
    assert r.json()["detail"] == "就诊记录不存在"
