"""GSP：验收、温湿度、不良反应、召回、人员资质。"""
from datetime import date, timedelta


def test_gsp_acceptance_storage_adverse_recall(client, auth):
    supplier = client.post(
        "/suppliers/",
        json={"code": "GSP-SUP", "name": "GSP供应商"},
        headers=auth["admin"],
    ).json()
    acceptance = client.post(
        "/gsp/acceptances",
        json={
            "supplier_id": supplier["id"],
            "delivery_no": "GSP-D-001",
            "transport_temp": 22.5,
            "items": [
                {
                    "kind": "drug",
                    "name": "GSP药品",
                    "batch_no": "GSP-B1",
                    "expiry": (date.today() + timedelta(days=365)).isoformat(),
                    "quantity": 100,
                    "result": "qualified",
                }
            ],
        },
        headers=auth["pharmacist"],
    )
    assert acceptance.status_code == 201, acceptance.text
    body = acceptance.json()
    assert body["acceptance_no"].startswith("GSPA")
    assert body["result"] == "qualified"
    assert body["items"][0]["name"] == "GSP药品"

    unqualified = client.post(
        "/gsp/acceptances",
        json={
            "supplier_name": "冷链供应商",
            "transport_temp": 35,
            "transport_ok": False,
            "items": [{"name": "冷链药品", "quantity": 1}],
        },
        headers=auth["warehouse"],
    )
    assert unqualified.status_code == 201
    assert unqualified.json()["result"] == "unqualified"

    normal = client.post(
        "/gsp/storage-logs",
        json={"area": "药房", "temperature": 22, "humidity": 50},
        headers=auth["pharmacist"],
    )
    assert normal.status_code == 201
    assert normal.json()["result"] == "normal"
    abnormal = client.post(
        "/gsp/storage-logs",
        json={"area": "药房", "temperature": 32, "humidity": 80},
        headers=auth["pharmacist"],
    )
    assert abnormal.status_code == 201
    assert abnormal.json()["result"] == "abnormal"

    adverse = client.post(
        "/gsp/adverse-reactions",
        json={
            "patient_name": "GSP患者",
            "drug_name": "GSP药品",
            "batch_no": "GSP-B1",
            "reaction": "皮疹",
            "severity": "moderate",
        },
        headers=auth["pharmacist"],
    )
    assert adverse.status_code == 201
    assert adverse.json()["reported_by"] == "pharmacist"

    recall = client.post(
        "/gsp/recalls",
        json={
            "drug_name": "GSP药品",
            "batch_no": "GSP-B1",
            "reason": "批次质量异常",
            "level": "2",
        },
        headers=auth["pharmacist"],
    )
    assert recall.status_code == 201
    recall_body = recall.json()
    assert recall_body["status"] == "initiated"
    completed = client.post(
        f"/gsp/recalls/{recall_body['id']}/complete", headers=auth["pharmacist"]
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    personnel = client.post(
        "/gsp/personnel",
        json={
            "name": "GSP药师",
            "role": "质量负责人",
            "certificate_no": "CERT-1",
            "valid_until": (date.today() - timedelta(days=1)).isoformat(),
        },
        headers=auth["pharmacist"],
    )
    assert personnel.status_code == 201
    assert personnel.json()["status"] == "expired"

    alerts = client.get("/gsp/alerts", headers=auth["pharmacist"]).json()
    assert alerts["unqualified_acceptances"] >= 1
    assert alerts["abnormal_storage"] >= 1
    assert alerts["expiring_personnel"] >= 1


def test_gsp_permissions(client, auth):
    assert (
        client.get("/gsp/acceptances", headers=auth["cashier"]).status_code == 403
    )
    assert client.get("/gsp/alerts", headers=auth["doctor"]).status_code == 403


def test_gsp_admin_page(client, auth):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/gsp")
    assert page.status_code == 200
    assert "GSP" in page.text
    assert "验收记录" in page.text
    assert "温湿度" in page.text
