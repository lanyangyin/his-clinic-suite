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
