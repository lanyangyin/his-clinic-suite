def setup_encounter_with_record(client, auth):
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
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/medical-record",
        json={
            "chief_complaint": "发热 2 天",
            "present_illness": "受凉后发热。",
            "past_history": "无特殊。",
            "physical_exam": "咽红。",
            "treatment_advice": "对症治疗。",
        },
        headers=auth["doctor"],
    )
    return encounter


def issue_cert(client, auth, subject="王医生"):
    return client.post(
        "/ca/certificates", json={"subject": subject}, headers=auth["admin"]
    )


def make_seal(client, auth, encounter_id, certificate_id, role="doctor"):
    return client.post(
        "/ca/seals",
        json={"encounter_id": encounter_id, "certificate_id": certificate_id},
        headers=auth[role],
    )


def test_issue_certificate(client, auth):
    r = issue_cert(client, auth)
    assert r.status_code == 201
    body = r.json()
    assert body["subject"] == "王医生"
    assert body["status"] == "valid"
    assert len(body["public_key"]) == 128
    assert "private_key" not in body  # 私钥不外泄


def test_list_and_get_certificates(client, auth):
    cert = issue_cert(client, auth).json()
    rows = client.get("/ca/certificates").json()
    assert len(rows) == 1
    one = client.get(f"/ca/certificates/{cert['id']}")
    assert one.status_code == 200
    assert client.get("/ca/certificates/999").status_code == 404


def test_seal_record(client, auth):
    encounter = setup_encounter_with_record(client, auth)
    cert = issue_cert(client, auth).json()
    r = make_seal(client, auth, encounter["id"], cert["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["target_type"] == "medical_record"
    assert body["target_id"] == encounter["id"]
    assert len(body["signature"]) == 128


def test_duplicate_seal_rejected(client, auth):
    encounter = setup_encounter_with_record(client, auth)
    cert = issue_cert(client, auth).json()
    make_seal(client, auth, encounter["id"], cert["id"])
    r = make_seal(client, auth, encounter["id"], cert["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该病历已用此证书签章"


def test_seal_missing_record(client, auth):
    encounter = setup_encounter_with_record(client, auth)
    cert = issue_cert(client, auth).json()
    department = client.get("/departments/1").json()
    doctor = client.get("/doctors/1").json()
    patient = client.get("/patients/1").json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    empty_encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]},
        headers=auth["doctor"],
    ).json()
    r = make_seal(client, auth, empty_encounter["id"], cert["id"])
    assert r.status_code == 404
    assert r.json()["detail"] == "病历不存在"


def test_verify_seal_valid(client, auth):
    encounter = setup_encounter_with_record(client, auth)
    cert = issue_cert(client, auth).json()
    seal = make_seal(client, auth, encounter["id"], cert["id"]).json()
    r = client.get(f"/ca/seals/{seal['id']}/verify")
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_verify_seal_tampered(client, auth):
    encounter = setup_encounter_with_record(client, auth)
    cert = issue_cert(client, auth).json()
    seal = make_seal(client, auth, encounter["id"], cert["id"]).json()
    # 篡改病历内容
    client.put(
        f"/encounters/{encounter['id']}/medical-record",
        json={"treatment_advice": "被篡改的处理意见"},
        headers=auth["doctor"],
    )
    r = client.get(f"/ca/seals/{seal['id']}/verify")
    assert r.status_code == 200
    assert r.json()["valid"] is False
    assert "篡改" in r.json()["reason"]


def test_verify_missing_seal(client):
    assert client.get("/ca/seals/999/verify").status_code == 404


def test_role_protection(client, auth):
    encounter = setup_encounter_with_record(client, auth)
    # 医生不能签发证书
    r = issue_cert(client, auth, subject="越权")
    assert r.status_code == 201  # admin 辅助函数默认 admin —— 改用显式 doctor 请求
    r = client.post(
        "/ca/certificates", json={"subject": "越权"}, headers=auth["doctor"]
    )
    assert r.status_code == 403
    # 收费员不能签章
    cert = issue_cert(client, auth).json()
    r = make_seal(client, auth, encounter["id"], cert["id"], role="cashier")
    assert r.status_code == 403
    # 未登录不能签章
    r = client.post(
        "/ca/seals", json={"encounter_id": encounter["id"], "certificate_id": cert["id"]}
    )
    assert r.status_code == 401
