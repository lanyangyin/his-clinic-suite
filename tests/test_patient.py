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
        headers=auth["nurse"],
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


def test_patient_reads_require_login_when_anonymous_read_disabled(client, auth, monkeypatch):
    from app import settings

    monkeypatch.setattr(settings, "ALLOW_ANONYMOUS_READ", False)
    assert client.get("/patients/").status_code == 401
    ok = client.get("/patients/", headers=auth["cashier"])
    assert ok.status_code == 200


def test_patient_merge_moves_registration_and_redirects(client, auth):
    source = client.post(
        "/patients/", json={"name": "合并源", "id_number": "110101199202020011"},
        headers=auth["cashier"],
    ).json()
    target = client.post(
        "/patients/", json={"name": "合并目标", "id_number": "110101199202020022"},
        headers=auth["cashier"],
    ).json()
    dept = client.post("/departments/", json={"name": "合并科"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": "合并医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/", json={"patient_id": source["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    merged = client.post(
        f"/patients/{source['id']}/merge",
        json={"target_id": target["id"], "reason": "同人重复建档"},
        headers=auth["admin"],
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["id"] == target["id"]
    assert client.get(f"/patients/{source['id']}").json()["id"] == target["id"]
    moved = client.get(f"/registrations/{registration['id']}").json()
    assert moved["patient_id"] == target["id"]
    again = client.post(
        f"/patients/{source['id']}/merge",
        json={"target_id": target["id"], "reason": "重复"},
        headers=auth["admin"],
    )
    assert again.status_code == 400
