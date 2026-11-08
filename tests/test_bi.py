from datetime import date

TODAY = date.today().isoformat()


def setup_data(client, auth):
    """构造一组 BI 可统计的数据：患者/挂号/接诊/诊断/处方/收费。"""
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
    drug = client.post(
        "/drugs/", json={"name": "阿莫西林胶囊", "base_price": 12.5, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    return patient, encounter, drug, payment


def test_overview(client, auth):
    setup_data(client, auth)
    r = client.get("/bi/overview", headers=auth["admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["patients_total"] == 1
    assert body["registrations_total"] == 1
    assert body["encounters_total"] == 1
    assert body["today_paid_count"] == 1
    assert body["today_paid_amount"] == 25.0
    assert body["today_insurance_amount"] == 20.0


def test_revenue_trend(client, auth):
    setup_data(client, auth)
    r = client.get("/bi/revenue-trend?days=7", headers=auth["admin"])
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 7
    today_row = next(row for row in rows if row["date"] == TODAY)
    assert today_row["paid_count"] == 1
    assert today_row["paid_amount"] == 25.0


def test_top_diagnoses(client, auth):
    setup_data(client, auth)
    # 再开两次同样诊断的就诊
    for _ in range(2):
        patient = client.post(
            "/patients/", json={"name": "李四", "id_number": "110101199501011234"},
            headers=auth["cashier"],
        ).json()
        reg = client.post(
            "/registrations/",
            json={"patient_id": patient["id"], "doctor_id": 1},
            headers=auth["cashier"],
        ).json()
        client.post(
            "/encounters/", json={"registration_id": reg["id"], "diagnosis": "上呼吸道感染"},
            headers=auth["doctor"],
        )
    r = client.get("/bi/top-diagnoses?limit=5", headers=auth["admin"])
    assert r.status_code == 200
    rows = r.json()
    assert rows[0]["diagnosis"] == "上呼吸道感染"
    assert rows[0]["count"] == 3


def test_top_drugs(client, auth):
    setup_data(client, auth)
    r = client.get("/bi/top-drugs?limit=5", headers=auth["admin"])
    assert r.status_code == 200
    rows = r.json()
    assert rows[0]["drug_name"] == "阿莫西林胶囊"
    assert rows[0]["quantity"] == 2


def test_role_protection(client, auth):
    assert client.get("/bi/overview", headers=auth["cashier"]).status_code == 403
    assert client.get("/bi/overview").status_code == 401
