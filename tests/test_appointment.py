from datetime import date, timedelta


def setup(client, auth, phone="13800138000", capacity=2):
    patient = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234", "phone": phone},
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
    schedule_date = (date.today() + timedelta(days=10)).isoformat()
    schedule = client.post(
        "/schedules/",
        json={"doctor_id": doctor["id"], "schedule_date": schedule_date, "period": "morning", "capacity": capacity},
        headers=auth["admin"],
    ).json()
    return patient, doctor, schedule


def test_appointment_create_occupies_slot_and_sends_sms(client, auth):
    patient, doctor, schedule = setup(client, auth)
    r = client.post(
        "/appointments/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "booked"
    assert body["created_by"] == "cashier"

    schedule_now = client.get(f"/schedules/{schedule['id']}").json()
    assert schedule_now["booked"] == 1

    messages = client.get("/sms/messages?template=appointment", headers=auth["admin"]).json()
    assert len(messages) == 1
    assert messages[0]["phone"] == patient["phone"]
    assert "预约成功" in messages[0]["content"]


def test_duplicate_active_appointment_rejected(client, auth):
    patient, doctor, schedule = setup(client, auth)
    payload = {"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]}
    client.post("/appointments/", json=payload, headers=auth["cashier"])
    dup = client.post("/appointments/", json=payload, headers=auth["cashier"])
    assert dup.status_code == 400
    assert dup.json()["detail"] == "该患者已预约此排班"

    # 取消后可以重新预约（号源释放）
    appt = client.get("/appointments/").json()[0]
    client.post(f"/appointments/{appt['id']}/cancel", headers=auth["cashier"])
    again = client.post("/appointments/", json=payload, headers=auth["cashier"])
    assert again.status_code == 201


def test_check_in_creates_registration(client, auth):
    patient, doctor, schedule = setup(client, auth)
    appt = client.post(
        "/appointments/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    ).json()

    r = client.post(f"/appointments/{appt['id']}/check-in", headers=auth["cashier"])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "checked_in"
    assert body["registration_id"] is not None
    assert body["checked_in_at"] is not None

    regs = client.get(f"/registrations/?patient_id={patient['id']}").json()
    assert len(regs) == 1
    assert regs[0]["schedule_id"] == schedule["id"]
    # 取号不重复占号
    assert client.get(f"/schedules/{schedule['id']}").json()["booked"] == 1

    again = client.post(f"/appointments/{appt['id']}/check-in", headers=auth["cashier"])
    assert again.status_code == 400
    assert again.json()["detail"] == "该预约状态不可取号"


def test_cancel_releases_slot(client, auth):
    patient, doctor, schedule = setup(client, auth)
    appt = client.post(
        "/appointments/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    ).json()
    assert client.get(f"/schedules/{schedule['id']}").json()["booked"] == 1

    r = client.post(f"/appointments/{appt['id']}/cancel", headers=auth["cashier"])
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert client.get(f"/schedules/{schedule['id']}").json()["booked"] == 0

    again = client.post(f"/appointments/{appt['id']}/cancel", headers=auth["cashier"])
    assert again.status_code == 400


def test_no_show_releases_slot(client, auth):
    patient, doctor, schedule = setup(client, auth)
    appt = client.post(
        "/appointments/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    ).json()
    r = client.post(f"/appointments/{appt['id']}/no-show", headers=auth["cashier"])
    assert r.status_code == 200
    assert r.json()["status"] == "no_show"
    assert client.get(f"/schedules/{schedule['id']}").json()["booked"] == 0


def test_appointment_validation(client, auth):
    patient, doctor, schedule = setup(client, auth)
    wrong_doctor = client.post(
        "/appointments/",
        json={"patient_id": patient["id"], "doctor_id": 999, "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    assert wrong_doctor.status_code == 400
    assert wrong_doctor.json()["detail"] == "医生不存在"

    missing_schedule = client.post(
        "/appointments/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": 999},
        headers=auth["cashier"],
    )
    assert missing_schedule.status_code == 400
    assert missing_schedule.json()["detail"] == "排班不存在"

    # 排班已满：两个不同患者占满 capacity=2
    for index in range(2):
        p = client.post(
            "/patients/",
            json={"name": f"占号患者{index}", "id_number": f"11010119900101{index:04d}"},
            headers=auth["cashier"],
        ).json()
        client.post(
            "/appointments/",
            json={"patient_id": p["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
            headers=auth["cashier"],
        )
    # 第三个患者尝试预约已满排班
    patient2 = client.post(
        "/patients/", json={"name": "李四", "id_number": "110101199501011234"},
        headers=auth["cashier"],
    ).json()
    full = client.post(
        "/appointments/",
        json={"patient_id": patient2["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    assert full.status_code == 400
    assert full.json()["detail"] == "该时段号源已满"


def test_appointment_list_and_missing(client, auth):
    patient, doctor, schedule = setup(client, auth)
    client.post(
        "/appointments/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    rows = client.get(f"/appointments/?patient_id={patient['id']}").json()
    assert len(rows) == 1
    assert client.get("/appointments/?status=checked_in").json() == []
    assert client.get("/appointments/999").status_code == 404
    assert client.post("/appointments/999/check-in", headers=auth["cashier"]).status_code == 400


def test_payment_has_invoice_no(client, auth):
    patient, doctor, schedule = setup(client, auth)
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1}, headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    assert payment["invoice_no"]
    assert payment["invoice_no"].startswith("INV")
    assert len(payment["invoice_no"]) == 17  # INV + 8 位日期 + 6 位流水

    html = client.get(f"/print/receipt/{payment['id']}").text
    assert payment["invoice_no"] in html
