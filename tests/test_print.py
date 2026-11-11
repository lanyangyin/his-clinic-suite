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


def test_print_record_and_tcm_pages(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "打印患者", "id_number": "110101199001015678"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "打印科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "打印医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "血瘀证"},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/medical-record",
        json={"chief_complaint": "胸闷", "treatment_advice": "忌生冷"},
        headers=auth["doctor"],
    )
    drug = client.post(
        "/drugs/", json={"name": "打印西药", "base_price": 5},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    herb = client.post(
        "/tcm/herbs",
        json={"code": "H-PRINT", "name": "桃仁", "price_per_g": 0.1},
        headers=auth["admin"],
    ).json()
    tcm_created = client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={
            "formula_name": "血府逐瘀汤",
            "packs": 3,
            "decoct_service": "decoct",
            "items": [{"herb_id": herb["id"], "dose_g": 10}],
        },
        headers=auth["doctor"],
    )
    assert tcm_created.status_code == 201, tcm_created.text
    lab_item = client.post(
        "/lab/items/",
        json={"code": "L-PRINT", "name": "白细胞", "price": 10, "unit": "×10^9/L"},
        headers=auth["admin"],
    ).json()
    lab_request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": lab_item["id"]},
        headers=auth["doctor"],
    ).json()
    for action in ("collect", "receive", "start"):
        assert client.post(
            f"/lab/requests/{lab_request['id']}/{action}", headers=auth["lab"]
        ).status_code == 200
    assert client.post(
        f"/lab/requests/{lab_request['id']}/report",
        json={"result": "12.5", "result_value": 12.5, "result_unit": "×10^9/L"},
        headers=auth["lab"],
    ).status_code == 200
    full = client.get(f"/print/prescription/{encounter['id']}")
    assert full.status_code == 200
    assert "门诊病历" in full.text
    assert "处方笺" in full.text
    assert "血府逐瘀汤" in full.text
    assert "桃仁" in full.text
    assert "白细胞" in full.text
    assert "12.5" in full.text
    assert "邹治国中西医结合诊所" in full.text
    assert "data-barcode" not in full.text
    assert "<svg" in full.text

    record = client.get(f"/print/medical-record/{encounter['id']}")
    assert record.status_code == 200
    assert "门诊病历" in record.text
    assert "处方笺" not in record.text

    western = client.get(f"/print/western-prescription/{encounter['id']}")
    assert western.status_code == 200
    assert "处方笺" in western.text
    assert "门诊病历" not in western.text

    tcm = client.get(f"/print/tcm-prescription/{encounter['id']}")
    assert tcm.status_code == 200
    assert "血府逐瘀汤" in tcm.text
    assert "桃仁" in tcm.text

    western_code = f"RX{encounter['id']:06d}"
    lookup = client.get(
        f"/encounters/by-barcode/{western_code}", headers=auth["cashier"]
    )
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()["encounter_id"] == encounter["id"]
    assert lookup.json()["patient_name"] == "打印患者"
    assert lookup.json()["is_paid"] is False
    assert lookup.json()["is_dispensed"] is False
    assert "未收费" in lookup.json()["status_text"]
    tcm_code = tcm_created.json()["prescription_no"]
    tcm_lookup = client.get(
        f"/encounters/by-barcode/{tcm_code}", headers=auth["pharmacist"]
    )
    assert tcm_lookup.status_code == 200
    assert tcm_lookup.json()["code_type"] == "tcm"
    assert client.get(
        "/encounters/by-barcode/BAD-CODE", headers=auth["cashier"]
    ).status_code == 404
    assert client.get(
        f"/encounters/by-barcode/{western_code}", headers=auth["lab"]
    ).status_code == 403


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


def test_barcode_svg(client):
    response = client.get("/print/barcode/RX000200.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text.startswith("<svg")
    assert "rect" in response.text
    assert "RX000200" in response.text


def test_barcode_rejects_non_ascii(client):
    response = client.get("/print/barcode/处方.svg")
    assert response.status_code == 400


def test_barcode_status_paid(client, auth):
    encounter, _payment = setup_paid_encounter(client, auth)
    code = f"RX{encounter['id']:06d}"
    lookup = client.get(f"/encounters/by-barcode/{code}", headers=auth["cashier"])
    assert lookup.status_code == 200
    body = lookup.json()
    assert body["is_paid"] is True
    assert body["is_dispensed"] is False
    assert body["pending_amount"] == 0
    assert body["status_text"] == "已收费，可发药"
