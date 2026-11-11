def test_patient_special_history_visible_in_encounter_summary(client, auth):
    patient = client.post(
        "/patients/",
        json={
            "name": "慢病患者",
            "id_number": "110101199001018888",
            "special_history": "2型糖尿病 8 年；高血压 5 年",
        },
        headers=auth["cashier"],
    )
    assert patient.status_code == 201, patient.text
    body = patient.json()
    assert body["special_history"] == "2型糖尿病 8 年；高血压 5 年"

    dept = client.post(
        "/departments/", json={"name": "慢病科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "慢病医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": body["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    summary = client.get(
        f"/encounters/{enc['id']}/summary", headers=auth["doctor"]
    )
    assert summary.status_code == 200
    assert summary.json()["special_history"] == "2型糖尿病 8 年；高血压 5 年"
