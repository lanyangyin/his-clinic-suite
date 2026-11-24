from datetime import date, timedelta

from app import settings


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "重构患者", "id_number": "110101199001011239"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "重构门诊"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "重构医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/",
        json={"name": "重构药", "spec": "10mg", "unit": "盒", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "REFACTOR001",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 20,
        },
        headers=auth["pharmacist"],
    )
    return patient, encounter, drug


def _add(client, auth, encounter_id, drug_id, qty=1, **extra):
    return client.post(
        f"/encounters/{encounter_id}/prescriptions",
        json={"drug_id": drug_id, "quantity": qty, **extra},
        headers=auth["doctor"],
    )


def test_prescription_header_and_per_header_limit(client, auth):
    _, encounter, drug = _setup(client, auth)
    drug_ids = [drug["id"]]
    for index in range(2, 6):
        extra = client.post(
            "/drugs/",
            json={"name": f"重构药{index}", "base_price": 1.0},
            headers=auth["admin"],
        ).json()
        drug_ids.append(extra["id"])
    for drug_id in drug_ids:
        r = _add(client, auth, encounter["id"], drug_id)
        assert r.status_code == 201, r.text
    headers = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()
    assert len(headers) == 1
    assert headers[0]["item_count"] == 5
    assert headers[0]["prescription_no"].startswith("RX")
    sixth = client.post(
        "/drugs/",
        json={"name": "第六种重构药", "base_price": 1.0},
        headers=auth["admin"],
    ).json()
    blocked = _add(client, auth, encounter["id"], sixth["id"])
    assert blocked.status_code == 400
    assert "5" in blocked.json()["detail"]


def test_review_required_blocks_dispense_then_approves(client, auth, monkeypatch):
    _, encounter, drug = _setup(client, auth)
    _add(client, auth, encounter["id"], drug["id"])
    monkeypatch.setattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", True)
    second = client.post(
        "/drugs/",
        json={"name": "待审重构药", "base_price": 2.0},
        headers=auth["admin"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": second["id"],
            "batch_no": "REFACTOR002",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 10,
        },
        headers=auth["pharmacist"],
    )
    pending = _add(client, auth, encounter["id"], second["id"])
    assert pending.status_code == 201, pending.text
    assert pending.json()["prescription_status"] == "pending_review"
    pay = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert pay.status_code == 201, pay.text

    blocked = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert blocked.status_code == 400
    assert "药师审核" in blocked.text

    headers = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()
    pending_header = next(h for h in headers if h["status"] == "pending_review")
    reviewed = client.post(
        f"/encounters/{encounter['id']}/prescriptions/{pending_header['id']}/review",
        json={"approve": True, "note": "同意"},
        headers=auth["pharmacist"],
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    timeline = client.get(
        f"/approvals/history/prescription/{pending_header['id']}",
        headers=auth["pharmacist"],
    )
    assert timeline.status_code == 200
    assert any(row["action"] == "approve" for row in timeline.json())
    request = client.get(
        f"/approvals/requests/prescription/{pending_header['id']}",
        headers=auth["pharmacist"],
    )
    assert request.status_code == 200
    assert request.json()["status"] == "approved"
    assert request.json()["steps"][0]["role_required"] == "pharmacist"

    monkeypatch.setattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", False)
    dispensed = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text


def test_dispense_items_have_batch_and_return(client, auth):
    _, encounter, drug = _setup(client, auth)
    _add(client, auth, encounter["id"], drug["id"], qty=2)
    client.post("/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"])
    dispensed = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "receiver_name": "重构患者"},
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    headers = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()
    assert headers[0]["status"] == "dispensed"
    slip = client.get(
        f"/pharmacy/dispense-slips/{encounter['id']}", headers=auth["pharmacist"]
    ).json()
    assert slip["items"][0]["batch_no"] == "REFACTOR001"
    assert slip["items"][0]["quantity"] == 2
    returned = client.post(
        f"/pharmacy/dispense/{dispensed.json()['id']}/return", headers=auth["pharmacist"]
    )
    assert returned.status_code == 200, returned.text
    headers = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()
    assert headers[0]["status"] == "returned"


def test_medical_record_versions(client, auth):
    _, encounter, _ = _setup(client, auth)
    created = client.post(
        f"/encounters/{encounter['id']}/medical-record",
        json={"chief_complaint": "头痛"},
        headers=auth["doctor"],
    )
    assert created.status_code == 201, created.text
    updated = client.put(
        f"/encounters/{encounter['id']}/medical-record",
        json={"present_illness": "两天"},
        headers=auth["doctor"],
    )
    assert updated.status_code == 200, updated.text
    signed = client.post(
        f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["doctor"]
    )
    assert signed.status_code == 200, signed.text
    versions = client.get(
        f"/encounters/{encounter['id']}/medical-record/versions",
        headers=auth["doctor"],
    ).json()
    assert [row["action"] for row in versions] == ["create", "update", "sign"]
    assert versions[1]["before_json"]
    assert versions[1]["after_json"]


def test_patient_access_audit(client, auth):
    patient, _, _ = _setup(client, auth)
    client.get(f"/patients/{patient['id']}", headers=auth["doctor"])
    client.get(f"/patients/{patient['id']}/history", headers=auth["doctor"])
    logs = client.get(
        f"/patients/{patient['id']}/access-log", headers=auth["admin"]
    ).json()
    assert len(logs) >= 2
    assert {row["action"] for row in logs} >= {"view", "view_history"}
    assert all(row.get("ip") for row in logs)


def test_approval_inbox_includes_catalog_proposal(client, auth):
    proposal = client.post(
        "/catalog-proposals/",
        json={"kind": "drug", "name": "待审目录药", "price": 1.0, "reason": "需要"},
        headers=auth["doctor"],
    )
    assert proposal.status_code == 201
    inbox = client.get("/approvals/inbox", headers=auth["pharmacist"]).json()
    assert any(row["kind"] == "catalog_proposal" for row in inbox)


def test_review_reject_removes_rejected_lines(client, auth, monkeypatch):
    _, encounter, drug = _setup(client, auth)
    monkeypatch.setattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", True)
    added = _add(client, auth, encounter["id"], drug["id"])
    assert added.status_code == 201, added.text
    header = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()[0]
    rejected = client.post(
        f"/encounters/{encounter['id']}/prescriptions/{header['id']}/review",
        json={"approve": False, "note": "重复用药"},
        headers=auth["pharmacist"],
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["item_count"] == 0
    assert client.get(
        f"/encounters/{encounter['id']}/prescriptions"
    ).json() == []
    history = client.get(
        f"/approvals/history/prescription/{header['id']}",
        headers=auth["pharmacist"],
    ).json()
    assert any(row["action"] == "reject" for row in history)


def test_narcotic_right_and_insurance_upload(client, auth):
    _, encounter, _ = _setup(client, auth)
    drug = client.post(
        "/drugs/",
        json={
            "name": "麻精测试药",
            "base_price": 5.0,
            "controlled_level": "narcotic",
        },
        headers=auth["admin"],
    )
    assert drug.status_code == 201, drug.text
    drug = drug.json()
    denied = _add(client, auth, encounter["id"], drug["id"])
    assert denied.status_code == 400
    assert "处方权" in denied.text

    users = client.get("/users/", headers=auth["admin"]).json()
    doctor_user = next(row for row in users if row["username"] == "doctor")
    granted = client.put(
        f"/users/{doctor_user['id']}/narcotic-right",
        json={"enabled": True},
        headers=auth["admin"],
    )
    assert granted.status_code == 200, granted.text
    added = _add(client, auth, encounter["id"], drug["id"])
    assert added.status_code == 201, added.text
    assert added.json()["prescription_type"] == "narcotic"

    header = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()[0]
    uploaded = client.post(
        f"/encounters/{encounter['id']}/prescriptions/{header['id']}/insurance-upload",
        headers=auth["cashier"],
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["insurance_upload_status"] == "local"


def test_prescription_center_and_single_print(client, auth):
    _, encounter, drug = _setup(client, auth)
    added = _add(client, auth, encounter["id"], drug["id"])
    assert added.status_code == 201, added.text
    center = client.get(
        f"/encounters/{encounter['id']}/prescription-center",
        headers=auth["doctor"],
    )
    assert center.status_code == 200, center.text
    data = center.json()
    assert data["western"] and data["western"][0]["item_count"] == 1
    lines = client.get(
        f"/encounters/{encounter['id']}/prescription-lines", headers=auth["doctor"]
    ).json()
    assert lines and lines[0]["kind"] == "drug" and lines[0]["name"] == "重构药"
    header_id = data["western"][0]["id"]
    printed = client.get(f"/print/prescription-header/{header_id}")
    assert printed.status_code == 200
    assert "门诊处方" in printed.text
    assert "重构药" in printed.text


def test_multistep_approval_flow(client, auth, monkeypatch):
    _, encounter, drug = _setup(client, auth)
    flow = client.put(
        "/approvals/flows/prescription",
        json={
            "steps": [
                {"role_required": "pharmacist", "due_hours": 2, "active": True},
                {"role_required": "director", "due_hours": 24, "active": True},
            ]
        },
        headers=auth["admin"],
    )
    assert flow.status_code == 200, flow.text
    monkeypatch.setattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", True)
    added = _add(client, auth, encounter["id"], drug["id"])
    assert added.status_code == 201, added.text
    header = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()[0]
    first = client.post(
        f"/encounters/{encounter['id']}/prescriptions/{header['id']}/review",
        json={"approve": True, "note": "药师通过"},
        headers=auth["pharmacist"],
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "pending_review"
    request = client.get(
        f"/approvals/requests/prescription/{header['id']}",
        headers=auth["pharmacist"],
    ).json()
    assert request["current_step"] == 2
    final = client.post(
        "/approvals/requests/action",
        json={
            "biz_type": "prescription",
            "biz_id": header["id"],
            "action": "approve",
            "note": "院长通过",
        },
        headers=auth["director"],
    )
    assert final.status_code == 200, final.text
    assert final.json()["result"] == "approved"
    assert final.json()["request"]["status"] == "approved"
    headers = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()
    assert headers[0]["status"] == "approved"


def test_narcotic_ledger_issue_and_ampoule(client, auth):
    _, encounter, _ = _setup(client, auth)
    drug = client.post(
        "/drugs/",
        json={"name": "麻醉账册药", "base_price": 3.0, "controlled_level": "narcotic"},
        headers=auth["admin"],
    ).json()
    users = client.get("/users/", headers=auth["admin"]).json()
    doctor_user = next(row for row in users if row["username"] == "doctor")
    client.put(
        f"/users/{doctor_user['id']}/narcotic-right",
        json={"enabled": True},
        headers=auth["admin"],
    )
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "NARCO001",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 5,
        },
        headers=auth["pharmacist"],
    )
    added = _add(client, auth, encounter["id"], drug["id"])
    assert added.status_code == 201, added.text
    client.post("/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"])
    blocked = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "receiver_name": "重构患者"},
        headers=auth["pharmacist"],
    )
    assert blocked.status_code == 400, blocked.text
    assert "第二见证人" in blocked.text
    same = client.post(
        "/pharmacy/dispense",
        json={
            "encounter_id": encounter["id"],
            "receiver_name": "重构患者",
            "witness": "pharmacist",
        },
        headers=auth["pharmacist"],
    )
    assert same.status_code == 400, same.text
    dispensed = client.post(
        "/pharmacy/dispense",
        json={
            "encounter_id": encounter["id"],
            "receiver_name": "重构患者",
            "witness": "护士",
        },
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    ledger = client.get("/narcotic/ledger", headers=auth["pharmacist"]).json()
    issue = next(
        row for row in ledger
        if row["action"] == "issue" and row["batch_no"] == "NARCO001"
    )
    assert issue["witness"] == "护士"
    returned = client.post(
        f"/pharmacy/dispense/{dispensed.json()['id']}/return",
        headers=auth["pharmacist"],
    )
    assert returned.status_code == 200, returned.text
    ledger = client.get("/narcotic/ledger", headers=auth["pharmacist"]).json()
    ret = next(row for row in ledger if row["action"] == "return")
    assert ret["patient_id"] == issue["patient_id"]
    assert ret["prescription_id"] == issue["prescription_id"]
    ampoule = client.post(
        "/narcotic/ampoule-return",
        json={
            "drug_id": drug["id"],
            "patient_id": None,
            "batch_no": "NARCO001",
            "quantity": 1,
            "witness": "李护士",
        },
        headers=auth["nurse"],
    )
    assert ampoule.status_code == 200, ampoule.text
    ledger = client.get("/narcotic/ledger", headers=auth["pharmacist"]).json()
    assert any(row["action"] == "ampoule_return" for row in ledger)


def test_approval_notifications(client, auth, monkeypatch):
    _, encounter, drug = _setup(client, auth)
    monkeypatch.setattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", True)
    added = _add(client, auth, encounter["id"], drug["id"])
    assert added.status_code == 201, added.text
    notes = client.get("/notifications", headers=auth["pharmacist"]).json()
    assert any("待审批" in row["title"] for row in notes)
    dispatched = client.post("/notifications/dispatch", headers=auth["admin"])
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["processed"] >= 1
    note_id = notes[0]["id"]
    read = client.post(f"/notifications/{note_id}/read", headers=auth["pharmacist"])
    assert read.status_code == 200, read.text
    after = client.get("/notifications", headers=auth["pharmacist"]).json()
    row = next(item for item in after if item["id"] == note_id)
    assert row["read_at"] is not None
    assert row["status"] != "read"  # 送达状态不与已读混用
    import base64

    created = client.post(
        "/users/",
        json={"username": "pharmacist2", "password": "pharm2pass", "role": "pharmacist"},
        headers=auth["admin"],
    )
    assert created.status_code == 201, created.text
    token = base64.b64encode(b"pharmacist2:pharm2pass").decode()
    other = client.get(
        "/notifications", headers={"Authorization": f"Basic {token}"}
    ).json()
    other_row = next(item for item in other if item["id"] == note_id)
    assert other_row["read_at"] is None


def test_narcotic_inventory_difference(client, auth):
    _, _, drug = _setup(client, auth)
    controlled = client.post(
        "/drugs/",
        json={"name": "盘点麻精药", "base_price": 2.0, "controlled_level": "narcotic"},
        headers=auth["admin"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": controlled["id"],
            "batch_no": "COUNT001",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 5,
        },
        headers=auth["pharmacist"],
    )
    check = client.post(
        "/narcotic/inventory-checks",
        json={
            "drug_id": controlled["id"],
            "batch_no": "COUNT001",
            "counted_qty": 4,
            "reason": "破损",
        },
        headers=auth["pharmacist"],
    )
    assert check.status_code == 201, check.text
    assert check.json()["difference"] == -1
    reviewed = client.post(
        f"/narcotic/inventory-checks/{check.json()['id']}/review",
        json={"approve": True, "note": "同意调整"},
        headers=auth["director"],
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    rows = client.get("/narcotic/inventory-checks", headers=auth["pharmacist"]).json()
    assert next(row for row in rows if row["id"] == check.json()["id"])["status"] == "approved"


def test_prescription_inline_edit(client, auth, monkeypatch):
    _, encounter, drug = _setup(client, auth)
    monkeypatch.setattr(settings, "REQUIRE_PRESCRIPTION_REVIEW", True)
    added = _add(client, auth, encounter["id"], drug["id"]).json()
    edited = client.put(
        f"/encounters/{encounter['id']}/prescriptions/items/{added['id']}",
        json={"quantity": 3, "dosage": "1片", "frequency": "bid", "route": "口服", "days": 3},
        headers=auth["doctor"],
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["dosage"] == "1片"
    assert edited.json()["quantity"] == 3
    lines = client.get(
        f"/encounters/{encounter['id']}/prescription-lines", headers=auth["doctor"]
    ).json()
    assert lines[0]["quantity"] == 3
    assert lines[0]["amount"] == 30.0
    deleted = client.delete(
        f"/encounters/{encounter['id']}/prescriptions/{added['id']}",
        headers=auth["doctor"],
    )
    assert deleted.status_code == 204


def test_integration_config(client, auth):
    rows = client.get("/integrations", headers=auth["admin"]).json()
    assert any(row["key"] == "insurance_upload_url" for row in rows)
    saved = client.put(
        "/integrations",
        json={"values": {"sms_webhook_url": "http://example.invalid/sms"}},
        headers=auth["admin"],
    )
    assert saved.status_code == 200, saved.text
    row = next(row for row in saved.json() if row["key"] == "sms_webhook_url")
    assert row["configured"] is True


def test_catalog_approval_action_commits_step(client, auth):
    proposal = client.post(
        "/catalog-proposals/",
        json={"kind": "drug", "name": "审批事务药", "price": 9.9, "reason": "测试"},
        headers=auth["doctor"],
    )
    assert proposal.status_code == 201, proposal.text
    proposal_id = proposal.json()["id"]
    acted = client.post(
        "/approvals/requests/action",
        json={
            "biz_type": "catalog_proposal",
            "biz_id": proposal_id,
            "action": "approve",
            "note": "药师通过",
        },
        headers=auth["pharmacist"],
    )
    assert acted.status_code == 200, acted.text
    assert acted.json()["result"] == "pending"
    request = client.get(
        f"/approvals/requests/catalog_proposal/{proposal_id}",
        headers=auth["pharmacist"],
    ).json()
    assert request["current_step"] == 2


def test_admin_notification_page(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/notifications")
    assert page.status_code == 200, page.text
    assert "通知中心" in page.text


def test_admin_patient_merge_page(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/patient-merges")
    assert page.status_code == 200, page.text
    assert "患者合并审批" in page.text


def test_admin_refund_approvals_page(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/refund-approvals")
    assert page.status_code == 200, page.text
    assert "大额退费审批留痕" in page.text


def test_refund_approvals_csv_export(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    response = client.get("/admin/refund-approvals.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "退费单号" in response.text


def test_admin_notification_templates_page(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/notification-templates")
    assert page.status_code == 200, page.text
    assert "通知模板" in page.text
    created = client.post(
        "/admin/notification-templates",
        data={"code": "report_ready", "title": "报告已出", "body": "请取报告", "channel": "internal", "active": "1"},
        follow_redirects=False,
    )
    assert created.status_code == 302
    page = client.get("/admin/notification-templates")
    assert "report_ready" in page.text


def test_admin_tcm_adjustments_page(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/tcm-adjustments")
    assert page.status_code == 200, page.text
    assert "中药盘点调整审批" in page.text


def test_admin_inpatient_page(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/inpatient")
    assert page.status_code == 200, page.text
    assert "住院管理" in page.text
