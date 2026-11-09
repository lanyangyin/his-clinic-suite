"""手术/治疗收费与耗材扣减。"""
from datetime import date, timedelta


def _material(client, auth):
    item = client.post(
        "/materials/items/",
        json={
            "code": "PM-001",
            "name": "无菌敷料",
            "spec": "10cm",
            "unit": "片",
            "price": 5.0,
            "category": "consumable",
        },
        headers=auth["admin"],
    ).json()
    client.post(
        "/materials/stock-in",
        json={"item_id": item["id"], "warehouse": "总库", "quantity": 10},
        headers=auth["admin"],
    )
    return item


def _patient_encounter(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "收费耗材患者", "id_number": "110101199901019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "收费耗材科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "收费耗材医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "操作"},
        headers=auth["doctor"],
    ).json()
    return patient, encounter


def _charge_item(client, auth, code="SURG", price=300.0):
    return client.post(
        "/charges/items/",
        json={
            "code": code,
            "name": "手术/治疗费",
            "category": "treatment",
            "price": price,
            "insurance_ratio": 0.0,
        },
        headers=auth["admin"],
    ).json()


def test_surgery_charge_and_material_deduction(client, auth):
    patient, encounter = _patient_encounter(client, auth)
    material = _material(client, auth)
    charge_item = _charge_item(client, auth, "SURG-1", 300.0)
    room = client.post(
        "/surgery/rooms", json={"code": "OR-PM", "name": "收费手术间"},
        headers=auth["surgery"],
    ).json()
    case = client.post(
        "/surgery/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "room_id": room["id"],
            "procedure_name": "清创缝合",
            "charge_item_id": charge_item["id"],
        },
        headers=auth["surgery"],
    ).json()
    assert case["price"] == 300.0
    charges = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()
    assert any("手术：" in row["item_name"] and row["amount"] == 300.0 for row in charges)

    client.post(
        f"/surgery/cases/{case['id']}/safety",
        json={"phase": "sign_in", "checklist": "ok"},
        headers=auth["surgery"],
    )
    client.post(f"/surgery/cases/{case['id']}/start", headers=auth["surgery"])
    used = client.post(
        f"/surgery/cases/{case['id']}/materials",
        json={"material_id": material["id"], "quantity": 2, "warehouse": "总库"},
        headers=auth["surgery"],
    )
    assert used.status_code == 201, used.text
    assert used.json()["amount"] == 10.0
    stock = client.get(
        f"/materials/stocks?item_id={material['id']}", headers=auth["admin"]
    ).json()
    assert sum(row["quantity"] for row in stock if row["warehouse"] == "总库") == 8
    charges = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()
    assert any("材料：" in row["item_name"] and row["amount"] == 10.0 for row in charges)


def test_treatment_room_charge_and_material_deduction(client, auth):
    patient, encounter = _patient_encounter(client, auth)
    material = _material(client, auth)
    charge_item = _charge_item(client, auth, "TR-PM", 80.0)
    room = client.post(
        "/treatment-room/rooms", json={"code": "TR-PM", "name": "收费治疗室"},
        headers=auth["treatment"],
    ).json()
    case = client.post(
        "/treatment-room/cases",
        json={
            "patient_id": patient["id"],
            "encounter_id": encounter["id"],
            "room_id": room["id"],
            "procedure_name": "清创缝合",
            "charge_item_id": charge_item["id"],
        },
        headers=auth["treatment"],
    ).json()
    client.post(
        f"/treatment-room/cases/{case['id']}/start",
        json={"consent": True, "anesthesia": "局麻", "findings": "裂伤"},
        headers=auth["treatment"],
    )
    used = client.post(
        f"/treatment-room/cases/{case['id']}/materials",
        json={"material_id": material["id"], "quantity": 3, "warehouse": "总库"},
        headers=auth["treatment"],
    )
    assert used.status_code == 201, used.text
    assert used.json()["amount"] == 15.0
    charges = client.get(
        f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]
    ).json()
    assert any("治疗室：" in row["item_name"] for row in charges)
    assert any("材料：" in row["item_name"] and row["amount"] == 15.0 for row in charges)
