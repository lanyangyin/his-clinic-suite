from datetime import date, timedelta
def make_patient(client, auth, id_number="110101199001011234"):
    return client.post(
        "/patients/", json={"name": "张三", "id_number": id_number}, headers=auth["cashier"]
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


def test_create_registration(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    r = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["patient_id"] == patient["id"]
    assert body["doctor_id"] == doctor["id"]
    assert body["status"] == "registered"


def test_create_registration_patient_missing(client, auth):
    doctor = make_doctor(client, auth)
    r = client.post(
        "/registrations/",
        json={"patient_id": 999, "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "患者不存在"


def test_create_registration_doctor_missing(client, auth):
    patient = make_patient(client, auth)
    r = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": 999},
        headers=auth["cashier"],
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "医生不存在"


def test_get_registration(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    r = client.get(f"/registrations/{reg['id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "registered"


def test_get_registration_missing(client):
    assert client.get("/registrations/999").status_code == 404


def test_cancel_unvisited_registration_releases_slot(client, auth):
    patient = client.post(
        "/patients/", json={"name": "取消挂号患者", "id_number": "110101199001019876"},
        headers=auth["cashier"],
    ).json()
    dept = client.post("/departments/", json={"name": "取消科"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": "取消医生", "department_id": dept["id"]}, headers=auth["admin"]
    ).json()
    schedule = client.post(
        "/schedules/",
        json={"doctor_id": doctor["id"], "schedule_date": str(date.today() + timedelta(days=7)), "period": "morning", "capacity": 1},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        headers=auth["cashier"],
    ).json()
    cancelled = client.post(f"/registrations/{reg['id']}/cancel", headers=auth["cashier"])
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/schedules/{schedule['id']}").json()["booked"] == 0
    again = client.post(f"/registrations/{reg['id']}/cancel", headers=auth["cashier"])
    assert again.status_code == 400


def test_registration_timestamps_and_cancel_audit(client, auth):
    patient = client.post(
        "/patients/", json={"name": "时间戳患者", "id_number": "110101199001017777"},
        headers=auth["cashier"],
    ).json()
    dept = client.post("/departments/", json={"name": "时间戳科"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": "时间戳医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    assert reg["created_at"] is not None
    assert reg["created_by"] == "cashier"
    cancelled = client.post(f"/registrations/{reg['id']}/cancel", headers=auth["cashier"]).json()
    assert cancelled["cancelled_at"] is not None
