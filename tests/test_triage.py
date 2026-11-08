def make_registration(client, auth):
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
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
    return client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()


def make_ticket(client, auth, registration_id):
    return client.post(
        "/triage/tickets", json={"registration_id": registration_id},
        headers=auth["nurse"],
    )


def test_create_ticket(client, auth):
    reg = make_registration(client, auth)
    r = make_ticket(client, auth, reg["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "waiting"
    assert body["registration_id"] == reg["id"]


def test_duplicate_ticket_rejected(client, auth):
    reg = make_registration(client, auth)
    make_ticket(client, auth, reg["id"])
    r = make_ticket(client, auth, reg["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该挂号已在分诊队列中"


def test_ticket_missing_registration(client, auth):
    r = make_ticket(client, auth, 999)
    assert r.status_code == 404
    assert r.json()["detail"] == "挂号记录不存在"


def test_call_ticket(client, auth):
    reg = make_registration(client, auth)
    ticket = make_ticket(client, auth, reg["id"]).json()
    r = client.post(f"/triage/tickets/{ticket['id']}/call", headers=auth["nurse"])
    assert r.status_code == 200
    assert r.json()["status"] == "called"
    assert r.json()["called_at"] is not None

    # 重复叫号
    again = client.post(f"/triage/tickets/{ticket['id']}/call", headers=auth["nurse"])
    assert again.status_code == 400
    assert again.json()["detail"] == "仅候诊中的叫号单可以叫号"


def test_pass_ticket_only_after_call(client, auth):
    reg = make_registration(client, auth)
    ticket = make_ticket(client, auth, reg["id"]).json()

    # 候诊直接过号 -> 400
    r = client.post(f"/triage/tickets/{ticket['id']}/pass", headers=auth["nurse"])
    assert r.status_code == 400
    assert r.json()["detail"] == "仅已叫号的叫号单可以过号"

    client.post(f"/triage/tickets/{ticket['id']}/call", headers=auth["nurse"])
    r = client.post(f"/triage/tickets/{ticket['id']}/pass", headers=auth["nurse"])
    assert r.status_code == 200
    assert r.json()["status"] == "passed"
    assert r.json()["passed_at"] is not None


def test_queue_lists_waiting_in_order(client, auth):
    ticket_ids = []
    for i in range(3):
        reg = make_registration(client, auth)
        ticket_ids.append(make_ticket(client, auth, reg["id"]).json()["id"])

    r = client.get("/triage/queue")
    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == ticket_ids

    # 叫号后从候诊队列消失
    client.post(f"/triage/tickets/{ticket_ids[0]}/call", headers=auth["nurse"])
    r = client.get("/triage/queue")
    assert ticket_ids[0] not in [t["id"] for t in r.json()]


def test_encounter_completes_ticket(client, auth):
    reg = make_registration(client, auth)
    ticket = make_ticket(client, auth, reg["id"]).json()

    r = client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    )
    assert r.status_code == 201

    got = client.get(f"/triage/tickets/{ticket['id']}").json()
    assert got["status"] == "done"
    assert got["done_at"] is not None


def test_get_ticket_missing(client):
    assert client.get("/triage/tickets/999").status_code == 404


def test_role_protection(client, auth):
    reg = make_registration(client, auth)
    # 医生不能入队
    r = client.post(
        "/triage/tickets", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    )
    assert r.status_code == 403
    # 未登录不能叫号
    ticket = make_ticket(client, auth, reg["id"]).json()
    r = client.post(f"/triage/tickets/{ticket['id']}/call")
    assert r.status_code == 401
