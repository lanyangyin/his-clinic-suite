"""治疗室：清创/换药排队、知情同意、处置记录、计费。"""


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "清创患者", "id_number": "110101199601019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "治疗室外科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "治疗室医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "手部裂伤"},
        headers=auth["doctor"],
    ).json()
    room = client.post(
        "/treatment-room/rooms",
        json={"code": "TR-1", "name": "清创室"},
        headers=auth["treatment"],
    ).json()
    item = client.post(
        "/charges/items/",
        json={
            "code": "DEBRIDE",
            "name": "清创缝合",
            "category": "treatment",
            "price": 80.0,
            "insurance_ratio": 0.0,
        },
        headers=auth["admin"],
    ).json()
    case = client.post(
        "/treatment-room/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "room_id": room["id"],
            "procedure_name": "清创缝合",
            "diagnosis": "右手掌裂伤",
            "priority": "urgent",
            "charge_item_id": item["id"],
        },
        headers=auth["treatment"],
    ).json()
    return patient, encounter, room, item, case


def test_treatment_room_full_flow(client, auth):
    patient, encounter, room, item, case = _setup(client, auth)
    assert case["case_no"].startswith("TR")
    assert case["status"] == "waiting"
    assert case["price"] == 80.0

    charges = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    )
    assert charges.status_code == 200
    assert any("治疗室" in row["item_name"] for row in charges.json())

    no_consent = client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={"consent": False},
        headers=auth["treatment"],
    )
    assert no_consent.status_code == 400
    assert "知情同意" in no_consent.json()["detail"]

    started = client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={"consent": True, "consent_signer": "患者本人", "consent_relation": "本人", "consent_signature_path": "data/test_consent.png", "anesthesia": "利多卡因局麻", "findings": "掌侧 3cm 裂伤"},
        headers=auth["treatment"],
    )
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"
    assert started.json()["consent"] is True

    incomplete = client.post(
        f"/treatment-room/cases/{case['id']}/complete",
        json={"procedure_detail": ""},
        headers=auth["treatment"],
    )
    assert incomplete.status_code == 422

    completed = client.post(
        f"/treatment-room/cases/{case['id']}/complete",
        json={
            "findings": "掌侧 3cm 裂伤，边缘整齐",
            "procedure_detail": "清创后 3-0 丝线缝合 4 针",
            "sutures": "3-0 丝线 4 针",
            "dressing": "无菌敷料包扎",
            "materials": "缝合包 1 个",
            "complications": "",
        },
        headers=auth["treatment"],
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None
    assert "4 针" in completed.json()["sutures"]

    work = client.get(
        "/treatment-room/cases", headers=auth["treatment"]
    ).json()
    assert any(row["id"] == case["id"] for row in work)


def test_treatment_room_cancel_and_permissions(client, auth):
    _, _, _, _, case = _setup(client, auth)
    cancelled = client.post(
        f"/treatment-room/cases/{case['id']}/cancel", headers=auth["treatment"]
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert (
        client.get("/treatment-room/cases", headers=auth["cashier"]).status_code
        == 403
    )


def test_treatment_room_templates(client, auth):
    templates = client.get(
        "/treatment-room/templates", headers=auth["treatment"]
    )
    assert templates.status_code == 200
    rows = templates.json()
    codes = {row["code"] for row in rows}
    assert "debridement" in codes
    assert "circumcision" in codes
    assert "burn" in codes

    patient, encounter, room, _, _ = _setup(client, auth)
    case = client.post(
        "/treatment-room/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "room_id": room["id"],
            "procedure_name": "包皮环切",
            "template_code": "circumcision",
            "template_data": {
                "indication": "包皮过长",
                "technique": "环切缝合",
                "anesthesia": "局麻",
                "suture": "可吸收线",
            },
        },
        headers=auth["treatment"],
    )
    assert case.status_code == 201, case.text
    body = case.json()
    assert body["template_code"] == "circumcision"
    assert "包皮过长" in body["template_data"]

    detail = client.get(
        f"/treatment-room/cases/{body['id']}", headers=auth["treatment"]
    )
    assert detail.status_code == 200
    assert detail.json()["template_code"] == "circumcision"


def test_treatment_followup_and_daily_report(client, auth):
    patient, encounter, room, _, _ = _setup(client, auth)
    case = client.post(
        "/treatment-room/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "room_id": room["id"],
            "procedure_name": "清创缝合",
            "template_code": "debridement",
            "template_data": {"site": "右手掌", "size": "3cm"},
        },
        headers=auth["treatment"],
    ).json()
    client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={"consent": True, "consent_signer": "患者本人", "consent_relation": "本人", "consent_signature_path": "data/test_consent.png", "anesthesia": "局麻", "findings": "裂伤"},
        headers=auth["treatment"],
    )
    client.post(
        f"/treatment-room/cases/{case['id']}/complete",
        json={"procedure_detail": "清创缝合 3 针", "sutures": "3-0 丝线 3 针"},
        headers=auth["treatment"],
    )

    followups = client.get(
        "/treatment-room/follow-ups", headers=auth["treatment"]
    ).json()
    assert any(row["case_id"] == case["id"] for row in followups)
    fu = next(row for row in followups if row["case_id"] == case["id"])
    assert fu["purpose"] == "换药"
    assert fu["patient_name"] == "清创患者"

    done = client.post(
        f"/treatment-room/follow-ups/{fu['id']}/complete", headers=auth["treatment"]
    )
    assert done.status_code == 200
    assert done.json()["status"] == "completed"

    report = client.get(
        f"/treatment-room/report?report_date={fu['due_date']}",
        headers=auth["treatment"],
    )
    # 报告按处置创建日期统计，这里只验证结构和字段
    assert report.status_code == 200
    body = report.json()
    assert "by_template" in body
    assert "by_room" in body
    assert "followups_due" in body


def test_treatment_report_admin_page(client, auth):
    _setup(client, auth)
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/treatment-report")
    assert page.status_code == 200
    assert "治疗室日报" in page.text
    assert "到期随访" in page.text


def test_treatment_template_config_and_kit(client, auth):
    patient, encounter, room, _, _ = _setup(client, auth)
    material = client.post(
        "/materials/items/",
        json={"code": "KIT-1", "name": "包皮环切包", "unit": "个", "price": 30, "category": "consumable"},
        headers=auth["admin"],
    ).json()
    client.post(
        "/materials/stock-in",
        json={"item_id": material["id"], "warehouse": "总库", "quantity": 5},
        headers=auth["admin"],
    )
    item = client.post(
        "/charges/items/",
        json={"code": "CIRC", "name": "包皮环切术", "category": "treatment", "price": 200},
        headers=auth["admin"],
    ).json()
    configured = client.put(
        "/treatment-room/templates/circumcision",
        json={
            "charge_item_id": item["id"],
            "price": 200,
            "material_id": material["id"],
            "material_quantity": 2,
            "warehouse": "总库",
            "active": True,
        },
        headers=auth["admin"],
    )
    assert configured.status_code == 200, configured.text

    templates = client.get(
        "/treatment-room/templates", headers=auth["treatment"]
    ).json()
    row = next(t for t in templates if t["code"] == "circumcision")
    assert row["configured"] is True
    assert row["charge_item_id"] == item["id"]
    assert row["material_id"] == material["id"]

    case = client.post(
        "/treatment-room/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "room_id": room["id"],
            "procedure_name": "包皮环切",
            "template_code": "circumcision",
            "template_data": {
                "indication": "包皮过长",
                "technique": "环切缝合",
                "anesthesia": "局麻",
            },
        },
        headers=auth["treatment"],
    ).json()
    assert case["price"] == 200.0
    assert case["charge_item_id"] == item["id"]

    started = client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={"consent": True, "consent_signer": "患者本人", "consent_relation": "本人", "consent_signature_path": "data/test_consent.png", "anesthesia": "局麻"},
        headers=auth["treatment"],
    )
    assert started.status_code == 200, started.text
    assert started.json()["kit_applied"] is True
    stock = client.get(
        f"/materials/stocks?item_id={material['id']}", headers=auth["admin"]
    ).json()
    assert sum(r["quantity"] for r in stock if r["warehouse"] == "总库") == 3
    charges = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()
    assert any("材料：" in row["item_name"] and row["amount"] == 60.0 for row in charges)

    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/treatment-templates")
    assert page.status_code == 200
    assert "包皮环切" in page.text


def test_multi_material_kit_and_cancel_return(client, auth):
    patient, encounter, room, _, _ = _setup(client, auth)
    materials = []
    for code, name in (("KIT-A", "清创包"), ("KIT-B", "无菌敷料")):
        item = client.post(
            "/materials/items/",
            json={"code": code, "name": name, "unit": "个", "price": 10, "category": "consumable"},
            headers=auth["admin"],
        ).json()
        client.post(
            "/materials/stock-in",
            json={"item_id": item["id"], "warehouse": "总库", "quantity": 10},
            headers=auth["admin"],
        )
        materials.append(item)
    charge_item = client.post(
        "/charges/items/",
        json={"code": "EXC", "name": "小肿物切除", "category": "treatment", "price": 150},
        headers=auth["admin"],
    ).json()
    configured = client.put(
        "/treatment-room/templates/excision",
        json={
            "charge_item_id": charge_item["id"],
            "price": 150,
            "materials": [
                {"material_id": materials[0]["id"], "quantity": 1, "warehouse": "总库"},
                {"material_id": materials[1]["id"], "quantity": 2, "warehouse": "总库"},
            ],
            "active": True,
        },
        headers=auth["admin"],
    )
    assert configured.status_code == 200, configured.text

    case = client.post(
        "/treatment-room/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "room_id": room["id"],
            "procedure_name": "小肿物切除",
            "template_code": "excision",
            "template_data": {"site": "背部", "size": "1cm"},
        },
        headers=auth["treatment"],
    ).json()
    assert case["price"] == 150

    started = client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={"consent": True, "consent_signer": "患者本人", "consent_relation": "本人", "consent_signature_path": "data/test_consent.png", "anesthesia": "局麻"},
        headers=auth["treatment"],
    )
    assert started.status_code == 200, started.text
    assert started.json()["kit_applied"] is True
    for item, expected in zip(materials, (9, 8)):
        stock = client.get(
            f"/materials/stocks?item_id={item['id']}", headers=auth["admin"]
        ).json()
        assert sum(r["quantity"] for r in stock if r["warehouse"] == "总库") == expected

    cancelled = client.post(
        f"/treatment-room/cases/{case['id']}/cancel", headers=auth["treatment"]
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    for item in materials:
        stock = client.get(
            f"/materials/stocks?item_id={item['id']}", headers=auth["admin"]
        ).json()
        assert sum(r["quantity"] for r in stock if r["warehouse"] == "总库") == 10
    charges = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()
    touched = [
        row
        for row in charges
        if row["item_name"] in ("治疗室：小肿物切除", "材料：清创包", "材料：无菌敷料")
    ]
    assert touched
    assert all(row["status"] == "cancelled" for row in touched)


def test_followup_result_and_photo(client, auth):
    from datetime import date, timedelta
    from pathlib import Path

    patient, encounter, _, _, _ = _setup(client, auth)
    followup = client.post(
        "/treatment-room/follow-ups",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "due_date": date.today().isoformat(),
            "purpose": "换药",
        },
        headers=auth["treatment"],
    ).json()

    photo = client.post(
        f"/treatment-room/follow-ups/{followup['id']}/photo",
        files={"file": ("wound.jpg", b"fake-jpg", "image/jpeg")},
        headers=auth["treatment"],
    )
    assert photo.status_code == 200, photo.text
    photo_path = photo.json()["photo_path"]
    assert client.get(
        f"/treatment-room/follow-ups/{followup['id']}/photo", headers=auth["treatment"]
    ).status_code == 200

    next_day = (date.today() + timedelta(days=2)).isoformat()
    done = client.post(
        f"/treatment-room/follow-ups/{followup['id']}/complete",
        json={
            "result_note": "创面干燥，无渗出",
            "healing_score": 8,
            "next_due_date": next_day,
            "next_purpose": "换药",
        },
        headers=auth["treatment"],
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "completed"
    assert body["healing_score"] == 8
    assert body["result_note"] == "创面干燥，无渗出"
    assert body["completed_by"] == "treatment"

    pending = client.get(
        "/treatment-room/follow-ups?status=pending", headers=auth["treatment"]
    ).json()
    assert any(row["due_date"] == next_day and row["patient_id"] == patient["id"] for row in pending)
    Path(photo_path).unlink(missing_ok=True)


def test_treatment_template_required_fields(client, auth):
    patient, encounter, room, _, _ = _setup(client, auth)
    missing = client.post(
        "/treatment-room/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "room_id": room["id"],
            "procedure_name": "包皮环切",
            "template_code": "circumcision",
            "template_data": {"indication": "包皮过长"},
        },
        headers=auth["treatment"],
    )
    assert missing.status_code == 400
    assert "请填写模板必填项" in missing.json()["detail"]


def test_treatment_report_excel_export(client, auth):
    from io import BytesIO
    from openpyxl import load_workbook

    _setup(client, auth)
    response = client.get(
        "/treatment-room/report/export.xlsx", headers=auth["treatment"]
    )
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content))
    assert "日报概览" in workbook.sheetnames
    assert "按模板" in workbook.sheetnames
    assert "待随访" in workbook.sheetnames
    assert workbook["日报概览"]["A2"].value == "日期"


def test_treatment_room_workbench(client, auth):
    from datetime import date, timedelta

    patient, encounter, _, _, case = _setup(client, auth)
    overdue = client.post(
        "/treatment-room/follow-ups",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "due_date": (date.today() - timedelta(days=2)).isoformat(),
            "purpose": "换药",
        },
        headers=auth["treatment"],
    ).json()
    data = client.get(
        "/treatment-room/workbench", headers=auth["treatment"]
    ).json()
    assert data["waiting"] >= 1
    assert data["pending_amount"] >= 80.0
    assert any(row["id"] == overdue["id"] for row in data["overdue"])
    assert any(row["id"] == case["id"] for row in data["cases"])
    assert (
        client.get("/treatment-room/workbench", headers=auth["cashier"]).status_code
        == 403
    )


def test_treatment_reconciliation_and_print_page(client, auth):
    from datetime import date

    patient, encounter, _, _, case = _setup(client, auth)
    client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={"consent": True, "consent_signer": "患者本人", "consent_relation": "本人", "consent_signature_path": "data/test_consent.png", "anesthesia": "局麻", "findings": "裂伤"},
        headers=auth["treatment"],
    )
    client.post(
        f"/treatment-room/cases/{case['id']}/complete",
        json={"procedure_detail": "清创缝合 2 针"},
        headers=auth["treatment"],
    )
    data = client.get(
        "/treatment-room/reconciliation", headers=auth["treatment"]
    ).json()
    row = next(r for r in data["rows"] if r["case_id"] == case["id"])
    assert row["fee"] == 80.0
    assert row["total"] == 80.0
    assert row["status"] == "待收费"
    assert data["totals"]["pending"] >= 80.0

    client.post(
        "/payments/", json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    paid = client.get(
        "/treatment-room/reconciliation", headers=auth["treatment"]
    ).json()
    paid_row = next(r for r in paid["rows"] if r["case_id"] == case["id"])
    assert paid_row["status"] == "已收费"
    assert paid_row["paid"] == 80.0

    assert (
        client.get("/treatment-room/reconciliation", headers=auth["doctor"]).status_code
        == 403
    )

    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/treatment-reconciliation")
    assert page.status_code == 200
    assert "治疗室收费对账" in page.text
    assert "打印" in page.text

