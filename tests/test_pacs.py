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
