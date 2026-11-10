"""护士站输液/医嘱执行：同步、配药、开始、巡视、完成、跳过。"""


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "输液患者", "id_number": "110101199001019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "输液内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "输液医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "急性支气管炎"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/",
        json={"name": "输液用抗生素", "base_price": 30.0, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    oral = client.post(
        "/drugs/",
        json={"name": "口服药", "base_price": 5.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={
            "drug_id": drug["id"],
            "quantity": 2,
            "dosage": "1g",
            "frequency": "qd",
            "route": "静滴",
            "days": 1,
        },
        headers=auth["doctor"],
    )
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={
            "drug_id": oral["id"],
            "quantity": 1,
            "dosage": "1片",
            "route": "口服",
            "days": 3,
        },
        headers=auth["doctor"],
    )
    treat = client.post(
        "/charges/items/",
        json={
            "code": "INFUSION",
            "name": "静脉输液",
            "category": "treatment",
            "price": 15.0,
            "insurance_ratio": 0.0,
        },
        headers=auth["admin"],
    ).json()
    client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": treat["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    return patient, encounter


def test_nursing_sync_and_execution(client, auth):
    patient, encounter = _setup(client, auth)
    synced = client.post(
        f"/nursing/encounters/{encounter['id']}/sync", headers=auth["nurse"]
    )
    assert synced.status_code == 200
    orders = synced.json()
    assert len(orders) == 2
    names = {row["item_name"] for row in orders}
    assert "输液用抗生素" in names
    assert "口服药" not in names
    assert any(row["order_type"] == "infusion" for row in orders)

    again = client.post(
        f"/nursing/encounters/{encounter['id']}/sync", headers=auth["nurse"]
    ).json()
    assert again == []

    work = client.get(
        "/nursing/orders",
        params={"encounter_id": encounter["id"]},
        headers=auth["nurse"],
    ).json()
    assert len(work) == 2
    assert work[0]["patient_name"] == "输液患者"

    infusion = next(row for row in orders if row["order_type"] == "infusion")
    blocked = client.post(
        f"/nursing/orders/{infusion['id']}/start",
        json={"seat_no": "输液-01", "rate_ml_h": 60},
        headers=auth["nurse"],
    )
    assert blocked.status_code == 400
    assert "配药" in blocked.json()["detail"]
    prepared = client.post(
        f"/nursing/orders/{infusion['id']}/prepare",
        json={
            "solvent": "0.9%氯化钠 250ml",
            "dose": "1g",
            "batch_no": "B20261109",
            "checked_by": "李护士",
            "expires_minutes": 120,
        },
        headers=auth["nurse"],
    )
    assert prepared.status_code == 201
    assert prepared.json()["solvent"] == "0.9%氯化钠 250ml"

    started = client.post(
        f"/nursing/orders/{infusion['id']}/start",
        json={"seat_no": "输液-08", "rate_ml_h": 60},
        headers=auth["nurse"],
    )
    assert started.status_code == 200
    assert started.json()["status"] == "executing"
    assert started.json()["seat_no"] == "输液-08"

    observed = client.post(
        f"/nursing/orders/{infusion['id']}/observe",
        json={"rate_ml_h": 50, "note": "滴速调慢", "adverse_reaction": ""},
        headers=auth["nurse"],
    )
    assert observed.status_code == 201
    assert observed.json()["rate_ml_h"] == 50

    completed = client.post(
        f"/nursing/orders/{infusion['id']}/complete",
        json={"note": "输完拔针", "adverse_reaction": ""},
        headers=auth["nurse"],
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    detail = client.get(
        f"/nursing/orders/{infusion['id']}/detail", headers=auth["nurse"]
    ).json()
    assert len(detail["preparations"]) == 1
    assert len(detail["observations"]) == 1

    other = next(row for row in orders if row["id"] != infusion["id"])
    skipped = client.post(
        f"/nursing/orders/{other['id']}/skip",
        json={"reason": "患者拒绝"},
        headers=auth["nurse"],
    )
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"


def test_nursing_role_protection(client, auth):
    _, encounter = _setup(client, auth)
    response = client.post(
        f"/nursing/encounters/{encounter['id']}/sync", headers=auth["doctor"]
    )
    assert response.status_code == 403
    assert client.get("/nursing/orders", headers=auth["cashier"]).status_code == 403
