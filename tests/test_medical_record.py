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
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "上呼吸道感染"},
        headers=auth["doctor"],
    ).json()
    return encounter, doctor


def make_record(client, auth, encounter_id, **overrides):
    payload = {
        "chief_complaint": "发热咳嗽 3 天",
        "present_illness": "3 天前受凉后出现发热，最高 38.5℃，伴咳嗽、咽痛。",
        "past_history": "既往体健。",
        "physical_exam": "咽充血，双肺呼吸音清。",
        "treatment_advice": "多饮水，注意休息。",
    }
    payload.update(overrides)
    return client.post(
        f"/encounters/{encounter_id}/medical-record", json=payload,
        headers=auth["doctor"],
    )


def test_create_medical_record(client, auth):
    encounter, doctor = make_encounter(client, auth)
    r = make_record(client, auth, encounter["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["chief_complaint"] == "发热咳嗽 3 天"
    assert body["written_by"] == "doctor"
    assert body["encounter_id"] == encounter["id"]


def test_duplicate_record_rejected(client, auth):
    encounter, doctor = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])
    r = make_record(client, auth, encounter["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊已有病历"


def test_record_requires_chief_complaint(client, auth):
    encounter, doctor = make_encounter(client, auth)
    r = make_record(client, auth, encounter["id"], chief_complaint="")
    assert r.status_code == 422


def test_record_missing_encounter(client, auth):
    r = make_record(client, auth, 999)
    assert r.status_code == 404
    assert r.json()["detail"] == "就诊记录不存在"


def test_get_medical_record(client, auth):
    encounter, doctor = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])
    r = client.get(f"/encounters/{encounter['id']}/medical-record")
    assert r.status_code == 200
    assert "发热" in r.json()["chief_complaint"]


def test_get_missing_record(client, auth):
    encounter, doctor = make_encounter(client, auth)
    assert client.get(f"/encounters/{encounter['id']}/medical-record").status_code == 404


def test_update_medical_record(client, auth):
    encounter, doctor = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])
    r = client.put(
        f"/encounters/{encounter['id']}/medical-record",
        json={"treatment_advice": "建议复查血常规"},
        headers=auth["doctor"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["treatment_advice"] == "建议复查血常规"
    assert "发热" in body["chief_complaint"]  # 未修改字段保持原值
    assert body["updated_at"] is not None


def test_record_locked_after_payment(client, auth):
    encounter, doctor = make_encounter(client, auth)
    make_record(client, auth, encounter["id"])

    # 收费关闭就诊
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert client.get(f"/encounters/{encounter['id']}").json()["status"] == "closed"

    # 关闭后不能新增或修改
    r = make_record(client, auth, encounter["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "就诊已关闭，不能书写病历"

    r = client.put(
        f"/encounters/{encounter['id']}/medical-record",
        json={"treatment_advice": "x"},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "就诊已关闭，不能修改病历"


def test_update_missing_record(client, auth):
    encounter, doctor = make_encounter(client, auth)
    r = client.put(
        f"/encounters/{encounter['id']}/medical-record",
        json={"treatment_advice": "x"},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊还没有病历"


def test_role_protection(client, auth):
    encounter, doctor = make_encounter(client, auth)
    r = client.post(
        f"/encounters/{encounter['id']}/medical-record",
        json={"chief_complaint": "x"},
        headers=auth["cashier"],
    )
    assert r.status_code == 403
    r = client.post(
        f"/encounters/{encounter['id']}/medical-record",
        json={"chief_complaint": "x"},
    )
    assert r.status_code == 401
