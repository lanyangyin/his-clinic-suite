"""院长驾驶舱：KPI、趋势、科室/医生、风险。"""
from datetime import date


def test_executive_dashboard(client, auth):
    dept = client.post(
        "/departments/", json={"name": "驾驶舱内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "驾驶舱医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/",
        json={"name": "驾驶舱患者", "id_number": "110101199201019999"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "高血压"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "驾驶舱降压药", "base_price": 12.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    assert payment.status_code in (200, 201)

    today = date.today().isoformat()
    response = client.get(
        "/bi/executive",
        params={"start_date": today, "end_date": today},
        headers=auth["admin"],
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["kpi"]["visits"] >= 1
    assert data["kpi"]["paid_count"] >= 1
    assert data["kpi"]["revenue"] > 0
    assert data["trend"]
    assert data["doctors"][0]["doctor_name"] == "驾驶舱医生"
    assert data["departments"]
    assert "insurance_risks" in data["risks"]

    # 权限
    assert (
        client.get("/bi/executive", headers=auth["cashier"]).status_code == 403
    )

    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/executive")
    assert page.status_code == 200
    assert "院长驾驶舱" in page.text
    assert "收入趋势" in page.text
