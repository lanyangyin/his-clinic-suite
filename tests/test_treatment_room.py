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
        json={"consent": True, "anesthesia": "利多卡因局麻", "findings": "掌侧 3cm 裂伤"},
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
        json={"consent": True, "anesthesia": "局麻", "findings": "裂伤"},
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
