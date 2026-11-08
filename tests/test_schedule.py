def make_patient(client, auth, id_number="110101199001011234"):
    return client.post(
        "/patients/", json={"name": "张三", "id_number": id_number},
        headers=auth["cashier"],
    ).json()


def make_doctor(client, auth, name="王医生"):
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    return client.post(
        "/doctors/",
        json={"name": name, "department_id": department["id"]},
        headers=auth["admin"],
    ).json()


def make_schedule(client, auth, doctor_id, capacity=2, schedule_date="2026-11-10", period="morning"):
    return client.post(
        "/schedules/",
        json={
            "doctor_id": doctor_id,
            "schedule_date": schedule_date,
            "period": period,
            "capacity": capacity,
        },
        headers=auth["admin"],
    )


def test_create_schedule(client, auth):
    doctor = make_doctor(client, auth)
    r = make_schedule(client, auth, doctor["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["doctor_id"] == doctor["id"]
    assert body["capacity"] == 2
    assert body["booked"] == 0
    assert body["period"] == "morning"


def test_duplicate_schedule_rejected(client, auth):
    doctor = make_doctor(client, auth)
    make_schedule(client, auth, doctor["id"])
    r = make_schedule(client, auth, doctor["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该医生该时段已有排班"


def test_schedule_missing_doctor(client, auth):
    r = make_schedule(client, auth, 999)
    assert r.status_code == 400
    assert r.json()["detail"] == "医生不存在"


def test_schedule_invalid_period(client, auth):
    doctor = make_doctor(client, auth)
    r = make_schedule(client, auth, doctor["id"], period="evening")
    assert r.status_code == 422


def test_registration_with_schedule_booked(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    schedule = make_schedule(client, auth, doctor["id"]).json()

    r = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 201
    assert r.json()["schedule_id"] == schedule["id"]

    got = client.get(f"/schedules/{schedule['id']}").json()
    assert got["booked"] == 1


def test_registration_schedule_full_rejected(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    schedule = make_schedule(client, auth, doctor["id"], capacity=1).json()

    first = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    assert first.status_code == 201

    second = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "该时段号源已满"


def test_registration_schedule_doctor_mismatch(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    other_doctor = make_doctor(client, auth, name="林医生")
    schedule = make_schedule(client, auth, doctor["id"]).json()

    r = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": other_doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "排班与医生不匹配"


def test_registration_schedule_missing(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    r = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": 999},
        headers=auth["cashier"],
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "排班不存在"


def test_registration_without_schedule_still_works(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    r = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 201
    assert r.json()["schedule_id"] is None


def test_list_doctor_schedules(client, auth):
    doctor = make_doctor(client, auth)
    make_schedule(client, auth, doctor["id"], schedule_date="2026-11-10", period="morning")
    make_schedule(client, auth, doctor["id"], schedule_date="2026-11-10", period="afternoon")
    make_schedule(client, auth, doctor["id"], schedule_date="2026-11-11", period="morning")

    r = client.get(f"/doctors/{doctor['id']}/schedules")
    assert r.status_code == 200
    assert len(r.json()) == 3

    r = client.get(f"/doctors/{doctor['id']}/schedules?schedule_date=2026-11-10")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_schedule_missing(client):
    assert client.get("/schedules/999").status_code == 404


def test_list_schedules_missing_doctor(client):
    assert client.get("/doctors/999/schedules").status_code == 404


def test_role_protection(client, auth):
    doctor = make_doctor(client, auth)
    payload = {"doctor_id": doctor["id"], "schedule_date": "2026-11-10", "period": "morning", "capacity": 5}
    r = client.post("/schedules/", json=payload, headers=auth["doctor"])
    assert r.status_code == 403
    r = client.post("/schedules/", json=payload)
    assert r.status_code == 401
