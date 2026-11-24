def make_encounter(client, auth):
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
    return client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "咳嗽"},
        headers=auth["doctor"],
    ).json()


def make_item(client, auth, code="CXR", name="胸部正位片", body_part="胸部"):
    return client.post(
        "/pacs/items/",
        json={"code": code, "name": name, "body_part": body_part, "price": 80.0},
        headers=auth["admin"],
    )


def test_create_imaging_item(client, auth):
    r = make_item(client, auth)
    assert r.status_code == 201
    assert r.json()["code"] == "CXR"
    assert r.json()["body_part"] == "胸部"


def test_duplicate_item_code_rejected(client, auth):
    make_item(client, auth)
    r = make_item(client, auth)
    assert r.status_code == 400
    assert r.json()["detail"] == "检查项目编码已存在"


def test_create_imaging_request_generates_accession(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    r = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["item_name"] == "胸部正位片"
    assert body["accession_no"].startswith("ACC")
    assert len(body["accession_no"]) == 13  # ACC + 10 位十六进制


def test_request_missing_item(client, auth):
    encounter = make_encounter(client, auth)
    r = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": 999},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "检查项目不存在"


def test_request_on_closed_encounter_rejected(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    r = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "就诊已关闭，不能开检查申请"


def test_report_imaging_result(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    request = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()

    r = client.post(
        f"/pacs/requests/{request['id']}/report",
        json={"report": "双肺纹理增粗，未见明显实变影。", "image_url": "http://pacs.local/img/ACC0001.dcm"},
        headers=auth["radiology"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "reported"
    assert "双肺纹理" in body["report"]
    assert body["image_url"].endswith(".dcm")
    assert body["reported_at"] is not None
    assert body["reported_by"] == "radiology"

    reviewed = client.post(
        f"/pacs/requests/{request['id']}/review",
        json={"approve": True, "note": "报告规范"},
        headers=auth["admin"],
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["reviewed_by"] == "admin"

    again = client.post(
        f"/pacs/requests/{request['id']}/report",
        json={"report": "x"},
        headers=auth["radiology"],
    )
    assert again.status_code == 400
    assert again.json()["detail"] == "该检查申请已出报告"


def test_report_missing_request(client, auth):
    r = client.post(
        "/pacs/requests/999/report", json={"report": "x"}, headers=auth["radiology"]
    )
    assert r.status_code == 404


def test_list_requests(client, auth):
    encounter = make_encounter(client, auth)
    item_a = make_item(client, auth, code="CXR", name="胸部正位片").json()
    item_b = make_item(client, auth, code="CTH", name="头颅 CT").json()
    for item in (item_a, item_b):
        client.post(
            f"/pacs/encounters/{encounter['id']}/imaging-requests",
            json={"item_id": item["id"]},
            headers=auth["doctor"],
        )
    r = client.get(f"/pacs/encounters/{encounter['id']}/imaging-requests")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_accession_numbers_unique(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    accessions = set()
    for _ in range(3):
        body = client.post(
            f"/pacs/encounters/{encounter['id']}/imaging-requests",
            json={"item_id": item["id"]},
            headers=auth["doctor"],
        ).json()
        accessions.add(body["accession_no"])
    assert len(accessions) == 3


def test_get_missing(client):
    assert client.get("/pacs/requests/999").status_code == 404
    assert client.get("/pacs/items/999").status_code == 404


def test_role_protection(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    # 影像技师不能开申请
    r = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["radiology"],
    )
    assert r.status_code == 403
    # 医生不能写报告
    request = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()
    r = client.post(
        f"/pacs/requests/{request['id']}/report",
        json={"report": "x"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    # 未登录不能开申请
    r = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
    )
    assert r.status_code == 401


def test_radiology_worklist_and_report(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    request = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()
    work = client.get("/pacs/worklist", headers=auth["radiology"])
    assert work.status_code == 200, work.text
    assert any(row["id"] == request["id"] for row in work.json())
    reported = client.post(
        f"/pacs/requests/{request['id']}/report",
        json={"report": "双肺纹理清晰", "image_url": "http://pacs.local/1"},
        headers=auth["radiology"],
    )
    assert reported.status_code == 200, reported.text
    assert reported.json()["status"] == "reported"


def test_structured_imaging_report(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth, code="CT-STRUCT", name="胸部 CT").json()
    request = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()
    r = client.post(
        f"/pacs/requests/{request['id']}/report",
        json={
            "findings": "双肺纹理增粗，未见明显实变。",
            "impression": "支气管炎可能，建议结合临床。",
            "template_name": "胸部CT默认模板",
            "study_uid": "1.2.3.4.5",
            "series_uid": "1.2.3.4.5.1",
            "modality": "CT",
            "measurements": "右肺上叶结节 8mm",
        },
        headers=auth["radiology"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["findings"].startswith("双肺纹理")
    assert body["impression"].startswith("支气管炎")
    assert "支气管炎" in body["report"]
    assert body["template_name"] == "胸部CT默认模板"
    assert body["study_uid"] == "1.2.3.4.5"
    assert body["series_uid"] == "1.2.3.4.5.1"
    assert body["modality"] == "CT"
    assert body["measurements"] == "右肺上叶结节 8mm"


def test_imaging_report_template(client, auth):
    created = client.post(
        "/pacs/templates",
        json={
            "name": "胸部 CT 默认模板",
            "body_part": "胸部",
            "findings": "双肺纹理清晰，未见明显实变。",
            "impression": "胸部 CT 未见明显异常。",
        },
        headers=auth["admin"],
    )
    assert created.status_code == 201, created.text
    rows = client.get("/pacs/templates", headers=auth["radiology"]).json()
    assert any(row["name"] == "胸部 CT 默认模板" for row in rows)
    duplicate = client.post(
        "/pacs/templates",
        json={"name": "胸部 CT 默认模板", "findings": "x"},
        headers=auth["admin"],
    )
    assert duplicate.status_code == 400
    denied = client.post(
        "/pacs/templates",
        json={"name": "医生不能建"},
        headers=auth["doctor"],
    )
    assert denied.status_code == 403


def test_imaging_worklist_urgent_first(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    routine = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"], "priority": "routine"},
        headers=auth["doctor"],
    ).json()
    urgent = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"], "priority": "urgent"},
        headers=auth["doctor"],
    ).json()
    assert urgent["priority"] == "urgent"
    rows = client.get("/pacs/worklist", headers=auth["radiology"]).json()
    ids = [row["id"] for row in rows]
    assert ids.index(urgent["id"]) < ids.index(routine["id"])


def test_invalid_dicom_uid_rejected(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth, code="CT-UID", name="UID 测试").json()
    request = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()
    bad = client.post(
        f"/pacs/requests/{request['id']}/report",
        json={"findings": "正常", "study_uid": "not-a-uid"},
        headers=auth["radiology"],
    )
    assert bad.status_code == 422


def test_invalid_pacs_image_url_rejected(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth, code="CT-URL", name="URL 测试").json()
    request = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()
    bad = client.post(
        f"/pacs/requests/{request['id']}/report",
        json={"findings": "正常", "image_url": "file:///etc/passwd"},
        headers=auth["radiology"],
    )
    assert bad.status_code == 422
