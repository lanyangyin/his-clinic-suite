from tests.conftest import basic_auth


def test_write_without_login_rejected(client):
    r = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "需要登录"


def test_write_wrong_password_rejected(client, auth):
    r = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234"},
        headers=basic_auth("cashier", "wrong-password"),
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "用户名或密码错误"


def test_wrong_role_rejected(client, auth):
    r = client.post(
        "/registrations/",
        json={"patient_id": 1, "doctor_id": 1},
        headers=auth["nurse"],
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "需要角色：cashier/doctor"


def test_doctor_can_register_patient(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "现场患者", "id_number": "110101199001019999"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "全科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "陈医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    r = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "registered"


def test_admin_can_do_everything(client, auth):
    r = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["admin"],
    )
    assert r.status_code == 201


def test_user_creation_requires_admin(client, auth):
    payload = {"username": "newbie", "password": "pw123456", "role": "doctor"}
    r = client.post("/users/", json=payload, headers=auth["cashier"])
    assert r.status_code == 403
    r = client.post("/users/", json=payload, headers=auth["admin"])
    assert r.status_code == 201
    assert r.json()["username"] == "newbie"


def test_duplicate_username_rejected(client, auth):
    r = client.post(
        "/users/",
        json={"username": "admin", "password": "x123456", "role": "doctor"},
        headers=auth["admin"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "用户名已存在"


def test_invalid_role_rejected(client, auth):
    r = client.post(
        "/users/",
        json={"username": "boss", "password": "x123456", "role": "boss"},
        headers=auth["admin"],
    )
    assert r.status_code == 400
    assert r.json()["detail"].startswith("非法角色")


def test_audit_logs_recorded(client, auth):
    client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    )
    logs = client.get("/audit/logs").json()
    assert len(logs) >= 1
    top = logs[0]
    assert top["username"] == "cashier"
    assert top["role"] == "cashier"
    assert top["path"] == "/patients/"
    assert top["status_code"] == 201


def test_audit_logs_record_anonymous_failures(client, auth):
    client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"}
    )
    logs = client.get("/audit/logs").json()
    anonymous = [l for l in logs if l["username"] == "anonymous"]
    assert any(l["path"] == "/patients/" and l["status_code"] == 401 for l in anonymous)


def test_doctor_can_quick_create_and_register(client, auth):
    patient = client.post(
        "/patients/",
        json={
            "name": "医生快速建档",
            "phone": "13800000001",
            "id_type": "none",
            "gender": "female",
            "address": "待补录",
            "privacy_consent": True,
        },
        headers=auth["doctor"],
    )
    assert patient.status_code == 201, patient.text
    body = patient.json()
    assert body["patient_no"]
    assert body["phone"] == "13800000001"

    department = client.post(
        "/departments/", json={"name": "医生快速挂号科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "快速挂号医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/",
        json={"patient_id": body["id"], "doctor_id": doctor["id"]},
        headers=auth["doctor"],
    )
    assert registration.status_code == 201, registration.text
