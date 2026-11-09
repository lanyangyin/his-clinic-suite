"""LIS 标本流转、结构化报告、审核、危急值、工作列表。"""


def _encounter(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "检验患者", "id_number": "110101198801011234", "phone": "13800000001"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "检验内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "检验医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": registration["id"], "diagnosis": "发热"},
        headers=auth["doctor"],
    ).json()
    item = client.post(
        "/lab/items/",
        json={
            "code": "WBC",
            "name": "白细胞计数",
            "price": 15.0,
            "specimen_type": "血液",
            "unit": "10^9/L",
            "reference_low": 4.0,
            "reference_high": 10.0,
        },
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"], "priority": "urgent"},
        headers=auth["doctor"],
    ).json()
    return patient, encounter, item, request


def test_specimen_workflow_structured_report_review(client, auth):
    patient, encounter, item, request = _encounter(client, auth)
    assert request["specimen_no"].startswith("LAB")
    assert request["priority"] == "urgent"

    work = client.get(
        "/lab/worklist", params={"status": "pending"}, headers=auth["lab"]
    ).json()
    row = next(row for row in work if row["id"] == request["id"])
    assert row["patient_name"] == "检验患者"
    assert row["item_name"] == "白细胞计数"

    collected = client.post(
        f"/lab/requests/{request['id']}/collect", json={}, headers=auth["nurse"]
    )
    assert collected.status_code == 200
    assert collected.json()["status"] == "collected"

    received = client.post(
        f"/lab/requests/{request['id']}/receive", headers=auth["lab"]
    )
    assert received.json()["status"] == "received"

    started = client.post(
        f"/lab/requests/{request['id']}/start", headers=auth["lab"]
    )
    assert started.json()["status"] == "testing"

    reported = client.post(
        f"/lab/requests/{request['id']}/report",
        json={
            "result_value": 12.5,
            "result_unit": "10^9/L",
            "reference_low": 4.0,
            "reference_high": 10.0,
            "critical_flag": True,
            "critical_notified_to": "检验医生",
        },
        headers=auth["lab"],
    )
    assert reported.status_code == 200
    body = reported.json()
    assert body["status"] == "reported"
    assert body["result_value"] == 12.5
    assert body["abnormal_flag"] == "H"
    assert body["critical_flag"] is True
    assert body["critical_notified_at"] is not None
    assert body["report_no"].startswith("RPT")

    printed = client.get(f"/print/lab-report/{request['id']}")
    assert printed.status_code == 200
    assert "检验报告单" in printed.text
    assert "12.5" in printed.text
    assert "危急值" in printed.text

    reviewed = client.post(
        f"/lab/requests/{request['id']}/review", headers=auth["lab"]
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["reviewed_by"] == "lab"


def test_critical_without_notification_cannot_review(client, auth):
    _, _, _, request = _encounter(client, auth)
    client.post(f"/lab/requests/{request['id']}/report",
                json={"result_value": 99, "critical_flag": True},
                headers=auth["lab"])
    response = client.post(
        f"/lab/requests/{request['id']}/review", headers=auth["lab"]
    )
    assert response.status_code == 400
    assert "危急值" in response.json()["detail"]


def test_specimen_reject_and_recollect(client, auth):
    _, _, _, request = _encounter(client, auth)
    client.post(f"/lab/requests/{request['id']}/collect", json={}, headers=auth["nurse"])
    client.post(f"/lab/requests/{request['id']}/receive", headers=auth["lab"])
    rejected = client.post(
        f"/lab/requests/{request['id']}/reject",
        json={"reason": "标本溶血"},
        headers=auth["lab"],
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["reject_reason"] == "标本溶血"

    recollect = client.post(
        f"/lab/requests/{request['id']}/collect", json={"note": "重新采血"}, headers=auth["nurse"]
    )
    assert recollect.status_code == 200
    assert recollect.json()["status"] == "collected"
    assert recollect.json()["reject_reason"] is None


def test_worklist_permissions(client, auth):
    _, _, _, _ = _encounter(client, auth)
    assert client.get("/lab/worklist", headers=auth["doctor"]).status_code == 403
    assert client.get("/lab/worklist", headers=auth["nurse"]).status_code == 403
