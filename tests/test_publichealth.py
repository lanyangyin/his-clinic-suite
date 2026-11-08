def make_encounter(client, auth):
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "感染科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    return client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "肺结核"},
        headers=auth["doctor"],
    ).json()


def make_report(client, auth, encounter_id, code="TB", name="肺结核"):
    return client.post(
        "/public-health/reports",
        json={"encounter_id": encounter_id, "disease_code": code, "disease_name": name},
        headers=auth["doctor"],
    )


def test_create_report(client, auth):
    encounter = make_encounter(client, auth)
    r = make_report(client, auth, encounter["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert body["reported_by"] == "doctor"
    assert body["submitted_at"] is None


def test_duplicate_report_rejected(client, auth):
    encounter = make_encounter(client, auth)
    make_report(client, auth, encounter["id"])
    r = make_report(client, auth, encounter["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊该疾病已创建报告卡"


def test_report_missing_encounter(client, auth):
    r = make_report(client, auth, 999)
    assert r.status_code == 404


def test_submit_report(client, auth):
    encounter = make_encounter(client, auth)
    report = make_report(client, auth, encounter["id"]).json()
    r = client.post(
        f"/public-health/reports/{report['id']}/submit", headers=auth["admin"]
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "submitted"
    assert body["submitted_at"] is not None

    # 重复上报
    again = client.post(
        f"/public-health/reports/{report['id']}/submit", headers=auth["admin"]
    )
    assert again.status_code == 400
    assert again.json()["detail"] == "该报告卡已上报"


def test_submit_missing_report(client, auth):
    r = client.post("/public-health/reports/999/submit", headers=auth["admin"])
    assert r.status_code == 404


def test_list_and_filter(client, auth):
    encounter_a = make_encounter(client, auth)
    encounter_b = make_encounter(client, auth)
    make_report(client, auth, encounter_a["id"])
    submitted = make_report(client, auth, encounter_b["id"]).json()
    client.post(
        f"/public-health/reports/{submitted['id']}/submit", headers=auth["admin"]
    )

    all_rows = client.get("/public-health/reports").json()
    assert len(all_rows) == 2
    drafts = client.get("/public-health/reports?status=draft").json()
    assert len(drafts) == 1
    assert drafts[0]["encounter_id"] == encounter_a["id"]
    done = client.get("/public-health/reports?status=submitted").json()
    assert len(done) == 1


def test_role_protection(client, auth):
    encounter = make_encounter(client, auth)
    # 收费员不能创建报告卡
    r = client.post(
        "/public-health/reports",
        json={"encounter_id": encounter["id"], "disease_code": "X", "disease_name": "X"},
        headers=auth["cashier"],
    )
    assert r.status_code == 403
    # 医生不能上报
    report = make_report(client, auth, encounter["id"]).json()
    r = client.post(
        f"/public-health/reports/{report['id']}/submit", headers=auth["doctor"]
    )
    assert r.status_code == 403
    # 未登录不能创建
    r = client.post(
        "/public-health/reports",
        json={"encounter_id": encounter["id"], "disease_code": "Y", "disease_name": "Y"},
    )
    assert r.status_code == 401
