def test_medical_record_has_personal_marital_family_and_auxiliary_exam(client, auth):
    dept = client.post(
        "/departments/", json={"name": "病历完整性科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "病历完整性医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/",
        json={"name": "病历完整性患者", "id_number": "110101199001017777"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    payload = {
        "chief_complaint": "发热 2 天",
        "present_illness": "受凉后发热",
        "past_history": "高血压 5 年",
        "personal_history": "吸烟 10 年，每日 10 支",
        "marital_history": "已婚，育有 1 子",
        "family_history": "父亲有高血压",
        "physical_exam": "咽充血，双肺呼吸音清",
        "auxiliary_exam": "外院血常规：白细胞 11.2",
        "treatment_advice": "对症治疗，3 天后复诊",
    }
    created = client.post(
        f"/encounters/{enc['id']}/medical-record", json=payload, headers=auth["doctor"]
    )
    assert created.status_code == 201, created.text
    got = client.get(f"/encounters/{enc['id']}/medical-record", headers=auth["doctor"])
    assert got.status_code == 200
    for key, value in payload.items():
        assert got.json()[key] == value
    printed = client.get(f"/print/medical-record/{enc['id']}")
    assert printed.status_code == 200
    for text in ("个人史", "婚育史", "家族史", "辅助检查（病历记录）"):
        assert text in printed.text
