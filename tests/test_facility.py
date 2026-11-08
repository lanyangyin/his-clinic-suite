def test_campus_crud(client, auth):
    r = client.post(
        "/campuses/",
        json={"code": "CAMP1", "name": "总院", "address": "演示路 1 号"},
        headers=auth["admin"],
    )
    assert r.status_code == 201
    campus_id = r.json()["id"]

    dup = client.post(
        "/campuses/", json={"code": "CAMP1", "name": "重复"}, headers=auth["admin"]
    )
    assert dup.status_code == 400
    assert dup.json()["detail"] == "院区编码已存在"

    rows = client.get("/campuses/").json()
    assert len(rows) == 1
    assert client.get(f"/campuses/{campus_id}").status_code == 200
    assert client.get("/campuses/999").status_code == 404


def test_room_crud_and_filters(client, auth):
    campus = client.post(
        "/campuses/", json={"code": "CAMP1", "name": "总院"}, headers=auth["admin"]
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()

    r = client.post(
        "/rooms/",
        json={"campus_id": campus["id"], "code": "101", "name": "内科诊室1", "department_id": department["id"]},
        headers=auth["admin"],
    )
    assert r.status_code == 201

    dup = client.post(
        "/rooms/",
        json={"campus_id": campus["id"], "code": "101", "name": "重复"},
        headers=auth["admin"],
    )
    assert dup.status_code == 400

    bad = client.post(
        "/rooms/", json={"campus_id": 999, "code": "102", "name": "无院区"},
        headers=auth["admin"],
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "院区不存在"

    rows = client.get(f"/rooms/?campus_id={campus['id']}").json()
    assert len(rows) == 1
    by_dep = client.get(f"/rooms/?department_id={department['id']}").json()
    assert len(by_dep) == 1
    assert client.get("/rooms/999").status_code == 404


def test_schedule_with_room(client, auth):
    campus = client.post(
        "/campuses/", json={"code": "CAMP1", "name": "总院"}, headers=auth["admin"]
    ).json()
    room = client.post(
        "/rooms/",
        json={"campus_id": campus["id"], "code": "201", "name": "诊室201"},
        headers=auth["admin"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()

    r = client.post(
        "/schedules/",
        json={
            "doctor_id": doctor["id"],
            "schedule_date": "2026-12-01",
            "period": "morning",
            "capacity": 5,
            "room_id": room["id"],
        },
        headers=auth["admin"],
    )
    assert r.status_code == 201
    assert r.json()["room_id"] == room["id"]

    bad = client.post(
        "/schedules/",
        json={
            "doctor_id": doctor["id"],
            "schedule_date": "2026-12-02",
            "period": "morning",
            "capacity": 5,
            "room_id": 999,
        },
        headers=auth["admin"],
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "诊室不存在"
