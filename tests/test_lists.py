def setup_data(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234"},
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
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0, "insurance_ratio": 0.8},
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
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()

    ward = client.post("/wards/", json={"name": "内科病区"}, headers=auth["admin"]).json()
    bed = client.post(
        "/beds/", json={"ward_id": ward["id"], "code": "101"}, headers=auth["admin"]
    ).json()
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": bed["id"]},
        headers=auth["cashier"],
    ).json()
    return {
        "patient": patient,
        "department": department,
        "doctor": doctor,
        "drug": drug,
        "reg": reg,
        "encounter": encounter,
        "payment": payment,
        "ward": ward,
        "admission": admission,
    }


def test_patients_list_and_filters(client, auth):
    data = setup_data(client, auth)
    rows = client.get("/patients/").json()
    assert len(rows) == 1
    by_name = client.get("/patients/?name=张三").json()
    assert len(by_name) == 1
    by_id = client.get(f"/patients/?id_number={data['patient']['id_number']}").json()
    assert len(by_id) == 1
    assert client.get("/patients/?name=不存在").json() == []


def test_registrations_list_and_filters(client, auth):
    data = setup_data(client, auth)
    rows = client.get("/registrations/").json()
    assert len(rows) == 1
    by_patient = client.get(
        f"/registrations/?patient_id={data['patient']['id']}"
    ).json()
    assert len(by_patient) == 1
    by_doctor = client.get(f"/registrations/?doctor_id={data['doctor']['id']}").json()
    assert len(by_doctor) == 1
    visited = client.get("/registrations/?status=visited").json()
    assert len(visited) == 1
    assert client.get("/registrations/?status=cancelled").json() == []


def test_encounters_list(client, auth):
    data = setup_data(client, auth)
    rows = client.get("/encounters/").json()
    assert len(rows) == 1
    by_patient = client.get(f"/encounters/?patient_id={data['patient']['id']}").json()
    assert len(by_patient) == 1
    assert client.get("/encounters/?patient_id=999").json() == []


def test_payments_list(client, auth):
    data = setup_data(client, auth)
    rows = client.get("/payments/").json()
    assert len(rows) == 1
    assert client.get("/payments/?status=paid").json()[0]["id"] == data["payment"]["id"]
    assert client.get("/payments/?status=refunded").json() == []
    by_encounter = client.get(
        f"/payments/?encounter_id={data['encounter']['id']}"
    ).json()
    assert len(by_encounter) == 1


def test_admissions_and_wards_list(client, auth):
    data = setup_data(client, auth)
    rows = client.get("/admissions/").json()
    assert len(rows) == 1
    active = client.get("/admissions/?status=in").json()
    assert len(active) == 1
    assert client.get("/admissions/?status=discharged").json() == []
    wards = client.get("/wards/").json()
    assert len(wards) == 1
    assert wards[0]["id"] == data["ward"]["id"]


def test_drugs_list(client, auth):
    data = setup_data(client, auth)
    rows = client.get("/drugs/").json()
    assert len(rows) == 1
    assert client.get("/drugs/?name=A药").json()[0]["id"] == data["drug"]["id"]
    assert client.get("/drugs/?name=不存在").json() == []


def test_doctors_list(client, auth):
    data = setup_data(client, auth)
    rows = client.get("/doctors/").json()
    assert len(rows) == 1
    by_dep = client.get(f"/doctors/?department_id={data['department']['id']}").json()
    assert len(by_dep) == 1
    assert client.get("/doctors/?department_id=999").json() == []
