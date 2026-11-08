from datetime import date


def setup_department(client, auth, name):
    department = client.post(
        "/departments/", json={"name": name}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": f"{name}医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    return department, doctor


def make_visit(client, auth, patient, doctor, drug, qty=1):
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": qty}, headers=auth["doctor"],
    )
    return encounter


def test_department_revenue(client, auth):
    client.post(
        "/charges/items/",
        json={"code": "REG", "name": "挂号费", "category": "registration", "price": 10.0},
        headers=auth["admin"],
    )
    client.post(
        "/charges/items/",
        json={"code": "CONSULT", "name": "诊疗费", "category": "consultation", "price": 20.0},
        headers=auth["admin"],
    )
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 12.5}, headers=auth["admin"]
    ).json()

    internal, doctor_a = setup_department(client, auth, "内科")
    pediatrics, doctor_b = setup_department(client, auth, "儿科")

    enc_a = make_visit(client, auth, patient, doctor_a, drug, qty=2)
    enc_b = make_visit(client, auth, patient, doctor_b, drug, qty=1)
    client.post("/payments/", json={"encounter_id": enc_a["id"]}, headers=auth["cashier"])
    client.post("/payments/", json={"encounter_id": enc_b["id"]}, headers=auth["cashier"])

    rows = client.get("/reports/departments/revenue", headers=auth["admin"]).json()
    by_name = {row["department_name"]: row for row in rows}
    assert set(by_name) == {"内科", "儿科"}
    internal_row = by_name["内科"]
    assert internal_row["encounter_count"] == 1
    assert internal_row["paid_amount"] == 10.0 + 20.0 + 25.0
    assert internal_row["registration_amount"] == 10.0
    assert internal_row["consultation_amount"] == 20.0
    assert internal_row["drug_amount"] == 25.0
    assert by_name["儿科"]["drug_amount"] == 12.5


def test_department_revenue_date_filter(client, auth):
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    internal, doctor_a = setup_department(client, auth, "内科")
    enc = make_visit(client, auth, patient, doctor_a, drug)
    client.post("/payments/", json={"encounter_id": enc["id"]}, headers=auth["cashier"])

    today = date.today().isoformat()
    past = "2020-01-01"
    assert len(client.get(f"/reports/departments/revenue?start_date={today}&end_date={today}", headers=auth["admin"]).json()) == 1
    assert client.get(f"/reports/departments/revenue?end_date={past}", headers=auth["admin"]).json() == []


def test_reports_permissions(client, auth):
    assert client.get("/reports/departments/revenue", headers=auth["cashier"]).status_code == 403
