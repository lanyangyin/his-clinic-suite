def make_encounter(client, auth):
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
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    return client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()


def make_record(client, auth, encounter_id, **overrides):
    payload = {
        "chief_complaint": "发热咳嗽 3 天",
        "present_illness": "3 天前受凉后发热。",
        "past_history": "既往体健。",
        "physical_exam": "咽充血。",
        "treatment_advice": "多饮水。",
    }
    payload.update(overrides)
    return client.post(
        f"/encounters/{encounter_id}/medical-record", json=payload,
        headers=auth["doctor"],
    )


def test_sign_medical_record(client, auth):
    encounter = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])
    r = client.post(
        f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["doctor"]
    )
    assert r.status_code == 200
    body = r.json()
    assert body["signed_by"] == "doctor"
    assert body["signed_at"] is not None


def test_sign_twice_rejected(client, auth):
    encounter = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])
    client.post(f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["doctor"])
    r = client.post(
        f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["doctor"]
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "病历已签名"


def test_signed_record_cannot_be_modified(client, auth):
    encounter = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])
    client.post(f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["doctor"])
    r = client.put(
        f"/encounters/{encounter['id']}/medical-record",
        json={"treatment_advice": "新的处理意见"},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "病历已签名，不能修改"


def test_sign_missing_record(client, auth):
    encounter = make_encounter(client, auth)
    r = client.post(
        f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["doctor"]
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "病历不存在"


def test_quality_full_record(client, auth):
    encounter = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])
    r = client.get(f"/encounters/{encounter['id']}/medical-record/quality")
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 100
    assert body["passed"] is True
    assert body["missing_fields"] == []


def test_quality_partial_record(client, auth):
    encounter = make_encounter(client, auth)
    make_record(
        client, auth, encounter["id"],
        present_illness="", past_history="", physical_exam="", treatment_advice="",
    )
    r = client.get(f"/encounters/{encounter['id']}/medical-record/quality")
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 20
    assert body["passed"] is False
    assert set(body["missing_fields"]) == {"现病史", "既往史", "查体", "处理意见"}


def test_quality_missing_record(client, auth):
    encounter = make_encounter(client, auth)
    r = client.get(f"/encounters/{encounter['id']}/medical-record/quality")
    assert r.status_code == 404


def test_quality_passed_threshold(client, auth):
    encounter = make_encounter(client, auth)
    # 3/5 = 60 分 -> 及格
    make_record(
        client, auth, encounter["id"],
        past_history="", physical_exam="",
    )
    body = client.get(f"/encounters/{encounter['id']}/medical-record/quality").json()
    assert body["score"] == 60
    assert body["passed"] is True


def test_role_protection(client, auth):
    encounter = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])
    # 收费员不能签名
    r = client.post(
        f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["cashier"]
    )
    assert r.status_code == 403
    # 未登录不能签名
    r = client.post(f"/encounters/{encounter['id']}/medical-record/sign")
    assert r.status_code == 401
