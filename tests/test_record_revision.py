def _setup_signed_record(client, auth):
    patient = client.post(
        "/patients/", json={"name": "修订患者", "id_number": "110101199001017777"},
        headers=auth["cashier"],
    ).json()
    dept = client.post("/departments/", json={"name": "修订科"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": "修订医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/", json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "高血压"},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/encounters/{enc['id']}/medical-record",
        json={"chief_complaint": "头晕", "treatment_advice": "监测血压"},
        headers=auth["doctor"],
    )
    signed = client.post(
        f"/encounters/{enc['id']}/medical-record/sign", headers=auth["doctor"]
    )
    assert signed.status_code == 200, signed.text
    return enc


def test_medical_record_revision_approve_unlocks(client, auth):
    enc = _setup_signed_record(client, auth)
    blocked = client.put(
        f"/encounters/{enc['id']}/medical-record",
        json={"chief_complaint": "改主诉"},
        headers=auth["doctor"],
    )
    assert blocked.status_code == 400
    created = client.post(
        f"/encounters/{enc['id']}/medical-record/revisions",
        json={"reason": "主诉记录不完整，需补充"},
        headers=auth["doctor"],
    )
    assert created.status_code == 201, created.text
    duplicate = client.post(
        f"/encounters/{enc['id']}/medical-record/revisions",
        json={"reason": "重复"},
        headers=auth["doctor"],
    )
    assert duplicate.status_code == 400
    rows = client.get(
        "/encounters/medical-record-revisions", params={"status": "pending"},
        headers=auth["admin"],
    ).json()
    assert any(row["id"] == created.json()["id"] for row in rows)
    approved = client.post(
        f"/encounters/medical-record-revisions/{created.json()['id']}/review",
        json={"approve": True, "note": "同意补充"},
        headers=auth["admin"],
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    updated = client.put(
        f"/encounters/{enc['id']}/medical-record",
        json={"chief_complaint": "头晕 3 天"},
        headers=auth["doctor"],
    )
    assert updated.status_code == 200, updated.text
    versions = client.get(
        f"/encounters/{enc['id']}/medical-record/versions", headers=auth["doctor"]
    ).json()
    assert any(row["action"] == "unlock_revision" for row in versions)


def test_revision_reject_requires_note(client, auth):
    enc = _setup_signed_record(client, auth)
    created = client.post(
        f"/encounters/{enc['id']}/medical-record/revisions",
        json={"reason": "需要修订"},
        headers=auth["doctor"],
    ).json()
    rejected = client.post(
        f"/encounters/medical-record-revisions/{created['id']}/review",
        json={"approve": False, "note": ""},
        headers=auth["admin"],
    )
    assert rejected.status_code == 400


def test_revision_admin_page_approve(client, auth):
    enc = _setup_signed_record(client, auth)
    created = client.post(
        f"/encounters/{enc['id']}/medical-record/revisions",
        json={"reason": "管理台审批测试"},
        headers=auth["doctor"],
    ).json()
    client.cookies.clear()
    assert client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    ).status_code == 302
    page = client.get("/admin/record-revisions")
    assert page.status_code == 200
    assert "管理台审批测试" in page.text
    reviewed = client.post(
        f"/admin/record-revisions/{created['id']}/review",
        data={"approve": "true", "note": "同意"},
        follow_redirects=False,
    )
    assert reviewed.status_code == 302
    refreshed = client.get(
        "/encounters/medical-record-revisions",
        params={"status": "approved"},
        headers=auth["admin"],
    ).json()
    assert any(row["id"] == created["id"] for row in refreshed)
