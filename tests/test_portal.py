def setup_patient_with_history(client, auth):
    """建患者 → 挂号 → 接诊 → 检验（已报告）+ 影像（已报告）。"""
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
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()

    # 检验项目 + 申请 + 报告
    lab_item = client.post(
        "/lab/items/", json={"code": "CBC", "name": "血常规", "price": 20.0},
        headers=auth["admin"],
    ).json()
    lab = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": lab_item["id"]},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/lab/requests/{lab['id']}/report",
        json={"result": "白细胞 6.2×10^9/L，正常"},
        headers=auth["lab"],
    )

    # 影像项目 + 申请 + 报告
    img_item = client.post(
        "/pacs/items/", json={"code": "CXR", "name": "胸部正位片", "body_part": "胸部", "price": 80.0},
        headers=auth["admin"],
    ).json()
    img = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": img_item["id"]},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/pacs/requests/{img['id']}/report",
        json={"report": "双肺纹理增粗", "image_url": "http://pacs.local/x.dcm"},
        headers=auth["radiology"],
    )
    return patient, encounter


def test_portal_patient(client, auth):
    patient, encounter = setup_patient_with_history(client, auth)
    r = client.get(f"/portal/patients/{patient['id_number']}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "张三"
    assert body["phone"] == "13800138000"
    assert len(body["registrations"]) == 1
    assert len(body["encounters"]) == 1
    assert body["encounters"][0]["diagnosis"] == "感冒"


def test_portal_reports(client, auth):
    patient, encounter = setup_patient_with_history(client, auth)
    r = client.get(f"/portal/reports/{patient['id_number']}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["labs"]) == 1
    assert "白细胞" in body["labs"][0]["result"]
    assert len(body["imaging"]) == 1
    assert body["imaging"][0]["report"] == "双肺纹理增粗"


def test_portal_reports_excludes_pending(client, auth):
    patient, encounter = setup_patient_with_history(client, auth)
    # 追加一条未出结果的检验
    lab_item = client.post(
        "/lab/items/", json={"code": "LFT", "name": "肝功能", "price": 35.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": lab_item["id"]},
        headers=auth["doctor"],
    )
    body = client.get(f"/portal/reports/{patient['id_number']}").json()
    assert len(body["labs"]) == 1  # 只有已出结果的


def test_portal_patient_missing(client):
    r = client.get("/portal/patients/999999")
    assert r.status_code == 404
    r = client.get("/portal/reports/999999")
    assert r.status_code == 404


def test_portal_no_history(client, auth):
    client.post(
        "/patients/",
        json={"name": "李四", "id_number": "110101199501011234"},
        headers=auth["cashier"],
    )
    body = client.get("/portal/patients/110101199501011234").json()
    assert body["registrations"] == []
    assert body["encounters"] == []
    reports = client.get("/portal/reports/110101199501011234").json()
    assert reports["labs"] == []
    assert reports["imaging"] == []
