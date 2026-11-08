def test_create_department(client, auth):
    r = client.post("/departments/", json={"name": "内科"}, headers=auth["admin"])
    assert r.status_code == 201
    assert r.json()["id"] == 1
    assert r.json()["name"] == "内科"


def test_duplicate_department_returns_existing(client, auth):
    first = client.post("/departments/", json={"name": "内科"}, headers=auth["admin"])
    second = client.post("/departments/", json={"name": "内科"}, headers=auth["admin"])
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_create_doctor(client, auth):
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    r = client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    )
    assert r.status_code == 201
    assert r.json()["department_id"] == department["id"]


def test_create_doctor_missing_department(client, auth):
    r = client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": 999},
        headers=auth["admin"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "科室不存在"


def test_get_doctor(client, auth):
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    r = client.get(f"/doctors/{doctor['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "王医生"


def test_get_doctor_missing(client):
    assert client.get("/doctors/999").status_code == 404


def test_get_department_missing(client):
    assert client.get("/departments/999").status_code == 404
