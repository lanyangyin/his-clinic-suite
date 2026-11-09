"""病案档案：建档→归档→借阅→复印→封存→销毁。"""


def _patient(client, auth):
    return client.post(
        "/patients/",
        json={"name": "档案患者", "id_number": "110101197001011234"},
        headers=auth["cashier"],
    ).json()


def test_archive_full_lifecycle(client, auth):
    patient = _patient(client, auth)
    created = client.post(
        "/archive/records",
        json={
            "patient_id": patient["id"],
            "record_type": "outpatient",
            "note": "门诊病案",
        },
        headers=auth["archive"],
    )
    assert created.status_code == 201
    record = created.json()
    assert record["archive_no"].startswith("BA")
    assert record["status"] == "draft"

    archived = client.post(
        f"/archive/records/{record['id']}/archive",
        json={
            "storage_location": "A区-03架-02层",
            "page_count": 18,
            "completeness": "complete",
        },
        headers=auth["archive"],
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["storage_location"] == "A区-03架-02层"

    borrowed = client.post(
        f"/archive/records/{record['id']}/borrow",
        json={"borrower": "王医生", "department": "内科", "purpose": "复诊调阅", "due_days": 7},
        headers=auth["archive"],
    )
    assert borrowed.status_code == 201
    borrowing = borrowed.json()
    assert borrowing["status"] == "borrowed"
    assert client.get(
        f"/archive/records/{record['id']}", headers=auth["archive"]
    ).json()["status"] == "borrowed"

    # 借出状态不能复印
    blocked_copy = client.post(
        f"/archive/records/{record['id']}/copy",
        json={"applicant": "患者本人", "relationship": "本人", "copies": 1},
        headers=auth["archive"],
    )
    assert blocked_copy.status_code == 400

    returned = client.post(
        f"/archive/borrowings/{borrowing['id']}/return", headers=auth["archive"]
    )
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    assert client.get(
        f"/archive/records/{record['id']}", headers=auth["archive"]
    ).json()["status"] == "archived"

    copied = client.post(
        f"/archive/records/{record['id']}/copy",
        json={
            "applicant": "患者本人",
            "id_number": "110101197001011234",
            "relationship": "本人",
            "purpose": "医保报销",
            "contents": "出院记录、检验报告",
            "copies": 2,
        },
        headers=auth["archive"],
    )
    assert copied.status_code == 201
    copy = copied.json()
    assert copy["status"] == "pending"
    completed = client.post(
        f"/archive/copies/{copy['id']}/complete",
        json={"fee": 4.0},
        headers=auth["archive"],
    )
    assert completed.status_code == 200
    assert completed.json()["fee"] == 4.0
    assert completed.json()["operator"] == "archive"

    sealed = client.post(
        f"/archive/records/{record['id']}/seal",
        json={"reason": "医疗纠纷封存", "witness": "医务科"},
        headers=auth["archive"],
    )
    assert sealed.status_code == 201
    assert sealed.json()["action"] == "seal"
    assert client.get(
        f"/archive/records/{record['id']}", headers=auth["archive"]
    ).json()["status"] == "sealed"

    destroyed_blocked = client.post(
        f"/archive/records/{record['id']}/destroy",
        json={"reason": "到期", "approved_by": "医务科"},
        headers=auth["archive"],
    )
    assert destroyed_blocked.status_code == 400

    unsealed = client.post(
        f"/archive/records/{record['id']}/unseal",
        json={"reason": "封存期满", "witness": "医务科"},
        headers=auth["archive"],
    )
    assert unsealed.status_code == 201
    assert unsealed.json()["action"] == "unseal"

    destroyed = client.post(
        f"/archive/records/{record['id']}/destroy",
        json={"reason": "保存期满", "approved_by": "医务科", "note": "销毁清册 2026-001"},
        headers=auth["archive"],
    )
    assert destroyed.status_code == 200
    assert client.get(
        f"/archive/records/{record['id']}", headers=auth["archive"]
    ).json()["status"] == "destroyed"

    history = client.get(
        f"/archive/records/{record['id']}/history", headers=auth["archive"]
    ).json()
    assert len(history["borrowings"]) == 1
    assert len(history["copies"]) == 1
    assert [row["action"] for row in history["seals"]] == ["unseal", "seal"]
    assert len(history["destructions"]) == 1


def test_archive_incomplete_cannot_archive(client, auth):
    patient = _patient(client, auth)
    record = client.post(
        "/archive/records",
        json={"patient_id": patient["id"]},
        headers=auth["archive"],
    ).json()
    response = client.post(
        f"/archive/records/{record['id']}/archive",
        json={"storage_location": "A-01", "page_count": 10, "completeness": "incomplete"},
        headers=auth["archive"],
    )
    assert response.status_code == 400
    assert "完整性" in response.json()["detail"]


def test_archive_role_protection(client, auth):
    patient = _patient(client, auth)
    response = client.post(
        "/archive/records",
        json={"patient_id": patient["id"]},
        headers=auth["cashier"],
    )
    assert response.status_code == 403
    # 医生只能查询，不能建档
    assert client.get("/archive/records", headers=auth["doctor"]).status_code == 200
