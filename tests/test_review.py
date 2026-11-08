from datetime import date


def setup(client, auth):
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
    abx = client.post(
        "/drugs/",
        json={"name": "头孢克肟", "base_price": 10.0, "antibiotic_level": 2},
        headers=auth["admin"],
    ).json()
    plain = client.post(
        "/drugs/", json={"name": "维生素C", "base_price": 20.0},
        headers=auth["admin"],
    ).json()
    return patient, doctor, abx, plain


def make_encounter(client, auth, patient, doctor):
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    return client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()


def test_review_summary(client, auth):
    patient, doctor, abx, plain = setup(client, auth)
    enc1 = make_encounter(client, auth, patient, doctor)
    enc2 = make_encounter(client, auth, patient, doctor)

    client.post(
        f"/encounters/{enc1['id']}/prescriptions",
        json={"drug_id": abx["id"], "quantity": 6, "route": "静滴"},
        headers=auth["doctor"],
    )
    client.post(
        f"/encounters/{enc2['id']}/prescriptions",
        json={"drug_id": plain["id"], "quantity": 1, "route": "口服"},
        headers=auth["doctor"],
    )

    summary = client.get("/review/summary", headers=auth["admin"]).json()
    assert summary["prescription_count"] == 2
    assert summary["item_count"] == 2
    assert summary["total_amount"] == 80.0
    assert summary["avg_amount"] == 40.0
    assert summary["antibiotic_prescriptions"] == 1
    assert summary["antibiotic_rate"] == 0.5
    assert summary["injection_prescriptions"] == 1
    assert summary["injection_rate"] == 0.5


def test_review_issues(client, auth):
    patient, doctor, abx, plain = setup(client, auth)
    enc1 = make_encounter(client, auth, patient, doctor)
    client.post(
        f"/encounters/{enc1['id']}/prescriptions",
        json={"drug_id": abx["id"], "quantity": 6, "route": "静滴"},
        headers=auth["doctor"],
    )

    issues = client.get("/review/issues", headers=auth["admin"]).json()
    assert len(issues) == 1
    assert issues[0]["encounter_id"] == enc1["id"]
    assert issues[0]["drug_name"] == "头孢克肟"
    assert "超量" in issues[0]["reason"]
    assert issues[0]["amount"] == 60.0


def test_review_detail(client, auth):
    patient, doctor, abx, plain = setup(client, auth)
    enc = make_encounter(client, auth, patient, doctor)
    client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={
            "drug_id": abx["id"],
            "quantity": 2,
            "dosage": "0.1g",
            "frequency": "bid",
            "route": "静滴",
            "days": 3,
        },
        headers=auth["doctor"],
    )

    detail = client.get(f"/review/encounters/{enc['id']}", headers=auth["admin"]).json()
    assert detail["patient_name"] == "张三"
    assert detail["doctor_name"] == "王医生"
    assert detail["total_amount"] == 20.0
    item = detail["items"][0]
    assert item["drug_name"] == "头孢克肟"
    assert item["antibiotic_level"] == 2
    assert item["dosage"] == "0.1g"
    assert item["route"] == "静滴"

    assert client.get("/review/encounters/999", headers=auth["admin"]).status_code == 404


def test_review_date_filter_and_permissions(client, auth):
    patient, doctor, abx, plain = setup(client, auth)
    enc = make_encounter(client, auth, patient, doctor)
    client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": abx["id"], "quantity": 1},
        headers=auth["doctor"],
    )

    today = date.today().isoformat()
    assert client.get(f"/review/summary?start_date={today}", headers=auth["pharmacist"]).status_code == 200
    assert client.get(f"/review/summary?end_date=2020-01-01", headers=auth["admin"]).json()["prescription_count"] == 0
    assert client.get("/review/summary", headers=auth["doctor"]).status_code == 403
