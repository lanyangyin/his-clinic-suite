def test_create_patient(client, auth):
    r = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234", "phone": "13800138000"},
        headers=auth["cashier"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["name"] == "张三"
    assert body["phone"] == "13800138000"


def test_create_patient_without_login_rejected(client):
    r = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"}
    )
    assert r.status_code == 401


def test_create_patient_wrong_role_rejected(client, auth):
    r = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403


def test_duplicate_id_number_returns_existing(client, auth):
    payload = {"name": "张三", "id_number": "110101199001011234"}
    first = client.post("/patients/", json=payload, headers=auth["cashier"])
    second = client.post("/patients/", json=payload, headers=auth["cashier"])
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_get_patient(client, auth):
    client.post(
        "/patients/",
        json={"name": "李四", "id_number": "110101199501011234"},
        headers=auth["cashier"],
    )
    r = client.get("/patients/1")
    assert r.status_code == 200
    assert r.json()["name"] == "李四"


def test_get_patient_missing(client):
    r = client.get("/patients/999")
    assert r.status_code == 404
    assert r.json()["detail"] == "患者不存在"
