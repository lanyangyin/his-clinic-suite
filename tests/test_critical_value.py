def setup_lab(client, auth, notified_to="急诊医生"):
    patient = client.post(
        "/patients/",
        json={"name": "危急值患者", "id_number": "110101199001017777"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "危急值科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "危急值医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    item = client.post(
        "/lab/items/",
        json={"code": "WBC-C", "name": "白细胞危急值", "price": 20},
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/lab/encounters/{enc['id']}/lab-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()
    client.post(f"/lab/requests/{request['id']}/collect", headers=auth["lab"])
    client.post(f"/lab/requests/{request['id']}/receive", headers=auth["lab"])
    client.post(f"/lab/requests/{request['id']}/start", headers=auth["lab"])
    report = client.post(
        f"/lab/requests/{request['id']}/report",
        json={
            "result": "WBC 25.0×10^9/L",
            "result_value": 25.0,
            "result_unit": "×10^9/L",
            "critical_flag": True,
            "critical_note": "白细胞显著升高",
            "critical_notified_to": notified_to,
        },
        headers=auth["lab"],
    )
    assert report.status_code == 200, report.text
    return patient, enc, request


def test_critical_alert_requires_doctor_ack(client, auth):
    patient, enc, request = setup_lab(client, auth)
    alerts = client.get("/lab/critical-alerts", headers=auth["doctor"])
    assert alerts.status_code == 200
    row = next(item for item in alerts.json() if item["id"] == request["id"])
    assert row["critical_pending"] is True
    assert row["critical_ack_at"] is None
    assert row["critical_age_minutes"] >= 0

    ack = client.post(
        f"/lab/requests/{request['id']}/critical-ack",
        json={"note": "已电话回读并确认"},
        headers=auth["doctor"],
    )
    assert ack.status_code == 200, ack.text
    body = ack.json()
    assert body["critical_ack_by"] == "doctor"
    assert body["critical_ack_at"] is not None
    assert body["critical_pending"] is False

    alerts_after = client.get("/lab/critical-alerts", headers=auth["doctor"]).json()
    assert all(item["id"] != request["id"] for item in alerts_after)

    again = client.post(
        f"/lab/requests/{request['id']}/critical-ack",
        json={"note": "重复"},
        headers=auth["doctor"],
    )
    assert again.status_code == 400


def test_critical_ack_requires_notification(client, auth):
    patient, enc, request = setup_lab(client, auth, notified_to="")
    blocked = client.post(
        f"/lab/requests/{request['id']}/critical-ack",
        json={"note": "未通知"},
        headers=auth["doctor"],
    )
    assert blocked.status_code == 400
    assert "通知" in blocked.json()["detail"]


def test_nurse_cannot_ack_critical(client, auth):
    patient, enc, request = setup_lab(client, auth)
    response = client.post(
        f"/lab/requests/{request['id']}/critical-ack",
        json={"note": "护士确认"},
        headers=auth["nurse"],
    )
    assert response.status_code == 403
