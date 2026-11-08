def test_sms_send_and_list(client, auth):
    r = client.post(
        "/sms/send",
        json={"phone": "13900139000", "content": "测试短信", "template": "custom"},
        headers=auth["admin"],
    )
    assert r.status_code == 201
    assert r.json()["status"] == "sent"

    rows = client.get("/sms/messages", headers=auth["admin"]).json()
    assert len(rows) == 1
    assert rows[0]["phone"] == "13900139000"

    unauthorized = client.get("/sms/messages", headers=auth["cashier"])
    assert unauthorized.status_code == 403


def test_report_ready_sms(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234", "phone": "13800138000"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "王医生", "department_id": department["id"]},
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
        json={"result": "正常"},
        headers=auth["lab"],
    )

    messages = client.get("/sms/messages?template=report_ready", headers=auth["admin"]).json()
    assert len(messages) == 1
    assert messages[0]["phone"] == "13800138000"
    assert "检验报告已出" in messages[0]["content"]


def test_no_sms_without_phone(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "无手机患者", "id_number": "110101199501011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "王医生", "department_id": department["id"]},
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
    img_item = client.post(
        "/pacs/items/",
        json={"code": "CXR", "name": "胸部正位片", "body_part": "胸部", "price": 80.0},
        headers=auth["admin"],
    ).json()
    img = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": img_item["id"]},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/pacs/requests/{img['id']}/report",
        json={"report": "正常", "image_url": "http://pacs/x.dcm"},
        headers=auth["radiology"],
    )
    assert client.get("/sms/messages", headers=auth["admin"]).json() == []
