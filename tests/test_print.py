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
    assert "处方状态" in html
    assert "watermark" in html
    assert "打印时间" in html
    assert "打印人" in html
    headers = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers", headers=auth["doctor"]
    ).json()
    rx_no = headers[0]["prescription_no"]
    assert rx_no in html
    assert f"RX{encounter['id']:06d}" not in html
    logs = client.get("/print/logs", headers=auth["admin"]).json()
    assert any(
        row["document_type"] == "prescription" and row["ref_id"] == encounter["id"]
        for row in logs
    )


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


def test_print_requires_login_when_anonymous_read_disabled(client, auth, monkeypatch):
    from app import settings

    encounter, _ = setup_paid_encounter(client, auth)
    monkeypatch.setattr(settings, "ALLOW_ANONYMOUS_READ", False)
    assert client.get(f"/print/prescription/{encounter['id']}").status_code == 401
    ok = client.get(f"/print/prescription/{encounter['id']}", headers=auth["doctor"])
    assert ok.status_code == 200


def test_print_one_time_token(client, auth, monkeypatch):
    from app import settings

    encounter, payment = setup_paid_encounter(client, auth)
    monkeypatch.setattr(settings, "ALLOW_ANONYMOUS_READ", False)
    no_token = client.get(f"/print/prescription/{encounter['id']}")
    assert no_token.status_code == 401
    created = client.post(
        "/print/tokens",
        params={"kind": "prescription", "ref_id": encounter["id"]},
        headers=auth["admin"],
    )
    assert created.status_code == 200, created.text
    token = created.json()["token"]
    first = client.get(
        f"/print/prescription/{encounter['id']}", params={"token": token}
    )
    assert first.status_code == 200, first.text
    second = client.get(
        f"/print/prescription/{encounter['id']}", params={"token": token}
    )
    assert second.status_code == 401


def test_medical_record_reprint_banner(client, auth):
    encounter, _payment = setup_paid_encounter(client, auth)
    first = client.get(f"/print/medical-record/{encounter['id']}")
    assert first.status_code == 200
    assert "补打" not in first.text
    second = client.get(f"/print/medical-record/{encounter['id']}")
    assert second.status_code == 200
    assert "补打 第2次" in second.text


def test_western_prescription_reprint_banner(client, auth):
    encounter, _payment = setup_paid_encounter(client, auth)
    first = client.get(f"/print/western-prescription/{encounter['id']}")
    assert first.status_code == 200
    assert "补打" not in first.text
    second = client.get(f"/print/western-prescription/{encounter['id']}")
    assert "补打 第2次" in second.text



def test_reprint_banner_helper():
    from app.modules.print.router import _reprint_banner

    assert "首次打印" in _reprint_banner(1)
    assert "补打 第2次" in _reprint_banner(2)


def test_signed_record_print_has_verification_code(client, auth):
    import re

    encounter, _payment = setup_paid_encounter(client, auth)
    signed = client.post(
        f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["doctor"]
    )
    assert signed.status_code == 200, signed.text
    html = client.get(f"/print/medical-record/{encounter['id']}").text
    assert "已签名" in html
    match = re.search(r"验签码：([0-9A-F]{12})", html)
    assert match, html
    verify = client.get(
        f"/print/verify-medical-record/{encounter['id']}",
        params={"code": match.group(1)},
        headers=auth["admin"],
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["valid"] is True


def test_admin_print_profile_applies_to_print(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    saved = client.post(
        "/admin/print-profile",
        data={
            "clinic_name": "测试机构打印抬头",
            "clinic_address": "测试地址",
            "clinic_phone": "010-12345678",
            "theme_color": "#123456",
            "font_family": "SimSun, serif",
            "paper_size": "A5",
            "margin_mm": 10,
            "header_note": "机构自定义说明",
            "footer_note": "机构页脚",
            "doctor_label": "主诊医师",
            "reviewer_label": "审方药师",
            "dispenser_label": "配药药师",
            "checker_label": "发药核对",
            "custom_css": ".clinic { letter-spacing: 8px; }",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 302
    encounter, payment = setup_paid_encounter(client, auth)
    html = client.get(f"/print/prescription/{encounter['id']}").text
    assert "测试机构打印抬头" in html
    assert "机构自定义说明" in html
    assert "机构页脚" in html
    assert "letter-spacing: 8px" in html
    assert "A5" in html

    # 收据也套用同一套机构打印外观
    receipt = client.get(f"/print/receipt/{payment['id']}").text
    assert "测试机构打印抬头" in receipt
    assert "机构页脚" in receipt
    assert "letter-spacing: 8px" in receipt


def test_admin_print_preview_all_templates(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/print-preview")
    assert page.status_code == 200, page.text
    assert "门诊病历" in page.text
    for kind, marker in (
        ("record", "门诊病历"),
        ("western", "处方笺"),
        ("tcm", "中药处方"),
        ("full", "演示患者"),
    ):
        response = client.get(f"/admin/print-preview/{kind}")
        assert response.status_code == 200, (kind, response.text)
        assert marker in response.text


def test_admin_print_preview_all_documents(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    cases = {
        "record": "门诊病历",
        "western": "处方笺",
        "tcm": "中药处方",
        "full": "演示患者",
        "prescription-header": "处方笺",
        "receipt": "收费收据",
        "retail": "零售小票",
        "dispense-slip": "取药凭证",
        "dispense-label": "发药袋标签",
        "nursing-label": "输液",
        "lab-report": "检验报告单",
        "imaging-report": "检查报告单",
    }
    for kind, marker in cases.items():
        response = client.get(f"/admin/print-preview/{kind}")
        assert response.status_code == 200, (kind, response.text)
        assert marker in response.text, (kind, marker)

    page = client.get("/admin/print-preview")
    assert page.status_code == 200
    for marker in ("取药凭证", "检验报告单", "收费收据", "发药袋标签"):
        assert marker in page.text


def test_admin_print_profile_live_preview(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/print-profile")
    assert page.status_code == 200
    assert 'id="print-preview-frame"' in page.text
    assert "/admin/print-preview/draft" in page.text

    response = client.post(
        "/admin/print-preview/draft",
        data={
            "kind": "receipt",
            "clinic_name": "实时预览机构",
            "clinic_address": "实时地址",
            "clinic_phone": "010-12345678",
            "theme_color": "#ff0000",
            "font_family": '"SimSun", serif',
            "paper_size": "A5",
            "margin_mm": "10",
            "header_note": "实时页眉",
            "footer_note": "实时页脚",
            "doctor_label": "医师",
            "reviewer_label": "审核药师",
            "dispenser_label": "调配药师",
            "checker_label": "核对药师",
            "custom_css": "body { letter-spacing: 1px; }",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200, response.text
    assert "实时预览机构" in response.text
    assert "实时页脚" in response.text
    assert "letter-spacing" in response.text
