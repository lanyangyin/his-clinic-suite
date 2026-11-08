def setup_doctor_activity(client, auth):
    """为医生 1 构造工作量：2 次接诊、2 条处方、1 笔收费、1 住院、1 医嘱。"""
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
    other_doctor = client.post(
        "/doctors/",
        json={"name": "林医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()

    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()

    # 两次接诊（一次开方+收费，一次仅接诊）
    reg1 = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc1 = client.post(
        "/encounters/", json={"registration_id": reg1["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/encounters/{enc1['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    client.post("/payments/", json={"encounter_id": enc1["id"]}, headers=auth["cashier"])

    reg2 = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc2 = client.post(
        "/encounters/", json={"registration_id": reg2["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/encounters/{enc2['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )

    # 住院 + 医嘱
    ward = client.post("/wards/", json={"name": "内科病区"}, headers=auth["admin"]).json()
    bed = client.post(
        "/beds/", json={"ward_id": ward["id"], "code": "101"}, headers=auth["admin"]
    ).json()
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": bed["id"]},
        headers=auth["cashier"],
    ).json()
    client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "standing", "quantity": 1},
        headers=auth["doctor"],
    )

    return doctor, other_doctor


def test_doctor_performance(client, auth):
    doctor, other = setup_doctor_activity(client, auth)
    r = client.get("/performance/doctors", headers=auth["admin"])
    assert r.status_code == 200
    rows = {row["doctor_id"]: row for row in r.json()}
    assert len(rows) == 2

    wang = rows[doctor["id"]]
    assert wang["doctor_name"] == "王医生"
    assert wang["encounters"] == 2
    assert wang["prescriptions"] == 2
    assert wang["outpatient_revenue"] == 20.0  # 10 * 2
    assert wang["admissions"] == 1
    assert wang["orders"] == 1

    lin = rows[other["id"]]
    assert lin["encounters"] == 0
    assert lin["outpatient_revenue"] == 0.0


def test_doctor_performance_filter(client, auth):
    doctor, other = setup_doctor_activity(client, auth)
    r = client.get(f"/performance/doctors?doctor_id={doctor['id']}", headers=auth["admin"])
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["doctor_id"] == doctor["id"]
    assert rows[0]["encounters"] == 2


def test_performance_empty(client, auth):
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    )
    r = client.get("/performance/doctors", headers=auth["admin"])
    assert r.status_code == 200
    assert r.json()[0]["encounters"] == 0


def test_role_protection(client, auth):
    assert client.get("/performance/doctors", headers=auth["doctor"]).status_code == 403
    assert client.get("/performance/doctors").status_code == 401
