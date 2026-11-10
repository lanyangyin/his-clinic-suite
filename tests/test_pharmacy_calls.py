"""药房叫号与发药核对。"""
from datetime import date, timedelta


def _paid_prescription(client, auth):
    drug = client.post(
        "/drugs/", json={"name": "叫号药品", "base_price": 10},
        headers=auth["admin"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "CALL-B1",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 50,
        },
        headers=auth["pharmacist"],
    )
    dept = client.post(
        "/departments/", json={"name": "叫号科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "叫号医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/",
        json={"name": "叫号患者", "id_number": "110101199901019999"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "叫号诊断"},
        headers=auth["doctor"],
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
    return patient, encounter, drug


def test_pharmacy_call_and_verified_dispense(client, auth):
    patient, encounter, _ = _paid_prescription(client, auth)
    worklist = client.get("/pharmacy/worklist", headers=auth["pharmacist"])
    assert worklist.status_code == 200
    row = next(r for r in worklist.json() if r["encounter_id"] == encounter["id"])
    assert row["patient_name"] == "叫号患者"
    assert row["call_status"] == "waiting"

    called = client.post(
        f"/pharmacy/calls/{encounter['id']}",
        json={"window_no": "2号窗", "note": "请取药"},
        headers=auth["pharmacist"],
    )
    assert called.status_code == 200, called.text
    queue_no = called.json()["queue_no"]
    assert queue_no.startswith("Q")

    after_call = client.get("/pharmacy/worklist", headers=auth["pharmacist"]).json()
    called_row = next(r for r in after_call if r["encounter_id"] == encounter["id"])
    assert called_row["call_status"] == "called"
    assert called_row["window_no"] == "2号窗"

    dispensed = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "note": "核对无误"},
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    body = dispensed.json()
    assert body["verified_by"] == "pharmacist"
    assert body["verified_at"] is not None

    final = client.get("/pharmacy/worklist", headers=auth["pharmacist"]).json()
    assert all(r["encounter_id"] != encounter["id"] for r in final)

    duplicate = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert duplicate.status_code == 400

    assert (
        client.get("/pharmacy/worklist", headers=auth["cashier"]).status_code == 403
    )
