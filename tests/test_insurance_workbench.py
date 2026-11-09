"""医保工作台：对码统计、结算统计、合规风险、事前事中。"""
from datetime import date


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "医保工作台患者", "id_number": "110101199301019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "医保工作台科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "医保工作台医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "医保测试"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/",
        json={"name": "未对码药", "base_price": 20.0, "insurance_ratio": 0.7},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/",
        json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    return patient, encounter, drug


def test_insurance_workbench_stats_and_risks(client, auth):
    _, encounter, drug = _setup(client, auth)
    today = date.today().isoformat()
    response = client.get(
        "/insurance/workbench",
        params={"start_date": today, "end_date": today},
        headers=auth["admin"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matching"]["drugs"]["unmatched"] >= 1
    assert data["matching"]["drugs"]["total"] >= 1
    assert data["settlement"]["payment_count"] >= 1
    assert data["settlement"]["total_amount"] > 0
    assert data["risk_count"] >= 1
    assert data["risks"][0]["category"] == "未对码"
    assert data["price_limit_note"]

    risks = client.get(
        f"/insurance/risks/encounter/{encounter['id']}", headers=auth["doctor"]
    )
    assert risks.status_code == 200
    body = risks.json()
    assert body["passed"] is False
    assert body["risks"][0]["drug_name"] == drug["name"]
    assert body["risks"][0]["category"] == "未对码"


def test_insurance_workbench_permissions(client, auth):
    _, encounter, _ = _setup(client, auth)
    assert client.get("/insurance/workbench", headers=auth["cashier"]).status_code == 403
    assert (
        client.get(
            f"/insurance/risks/encounter/{encounter['id']}", headers=auth["cashier"]
        ).status_code
        == 403
    )


def test_insurance_workbench_admin_page(client, auth):
    _setup(client, auth)
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/insurance-workbench")
    assert page.status_code == 200
    assert "医保工作台" in page.text
    assert "未对码" in page.text
    assert "合规风险" in page.text
