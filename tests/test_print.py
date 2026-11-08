def setup_paid_encounter(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234", "phone": "13800138000"},
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
    client.post(
        f"/encounters/{encounter['id']}/medical-record",
        json={"chief_complaint": "发热咳嗽 3 天", "treatment_advice": "多饮水"},
        headers=auth["doctor"],
    )
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
    return encounter, payment


def test_print_prescription(client, auth):
    encounter, payment = setup_paid_encounter(client, auth)
    r = client.get(f"/print/prescription/{encounter['id']}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    html = r.text
    assert "处方笺" in html
    assert "张三" in html
    assert "上呼吸道感染" in html
    assert "阿莫西林胶囊" in html
    assert "25.00" in html  # 2 * 12.5
    assert "王医生" in html


def test_print_prescription_missing(client):
    r = client.get("/print/prescription/999")
    assert r.status_code == 404


def test_print_receipt(client, auth):
    encounter, payment = setup_paid_encounter(client, auth)
    r = client.get(f"/print/receipt/{payment['id']}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    html = r.text
    assert "收费收据" in html
    assert "张三" in html
    assert "25.00" in html  # 应收
    assert "20.00" in html  # 医保 25*0.8
    assert "5.00" in html   # 自费
    assert "已支付" in html


def test_print_receipt_missing(client):
    r = client.get("/print/receipt/999")
    assert r.status_code == 404
