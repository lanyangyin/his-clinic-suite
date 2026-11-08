def make_setup(client, auth):
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
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    item = client.post(
        "/charges/items/",
        json={"code": "INFUSION", "name": "静脉输液", "category": "treatment", "price": 15.0, "insurance_ratio": 0.7},
        headers=auth["admin"],
    ).json()
    return patient, doctor, reg, encounter, item


def test_create_treatment_and_charge(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    r = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": item["id"], "quantity": 2, "note": "左氧氟沙星 0.2g"},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["item_name"] == "静脉输液"
    assert body["ordered_by"] == "doctor"

    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    treatment_charges = [c for c in charges if c["charge_type"] == "treatment"]
    assert len(treatment_charges) == 1
    assert treatment_charges[0]["amount"] == 30.0


def test_treatment_rejected_on_closed_encounter(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1}, headers=auth["doctor"],
    )
    client.post("/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"])
    r = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "就诊已收费，不能再开治疗单"


def test_treatment_rejects_non_treatment_item(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    lab = client.post(
        "/charges/items/",
        json={"code": "LABX", "name": "化验费", "category": "lab", "price": 20.0},
        headers=auth["admin"],
    ).json()
    r = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": lab["id"]}, headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该项目不是治疗类收费项目"


def test_execute_treatment(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    order = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    r = client.post(f"/treatments/{order['id']}/execute", headers=auth["nurse"])
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert r.json()["executed_by"] == "nurse"

    again = client.post(f"/treatments/{order['id']}/execute", headers=auth["nurse"])
    assert again.status_code == 400
    assert again.json()["detail"] == "该治疗单已执行或已取消"


def test_cancel_treatment_refunds_charge(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    order = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    r = client.post(f"/treatments/{order['id']}/cancel", headers=auth["doctor"])
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    treatment_charges = [c for c in charges if c["charge_type"] == "treatment"]
    assert treatment_charges[0]["status"] == "refunded"

    execute = client.post(f"/treatments/{order['id']}/execute", headers=auth["nurse"])
    assert execute.status_code == 400


def test_treatment_list_and_missing(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    )
    rows = client.get(f"/treatments/encounters/{encounter['id']}").json()
    assert len(rows) == 1
    assert client.get("/treatments/999").status_code == 404
    assert client.post("/treatments/999/execute", headers=auth["nurse"]).status_code == 400


def test_treatment_permissions(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    # 收费员不能开治疗单
    r = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": item["id"]}, headers=auth["cashier"],
    )
    assert r.status_code == 403
    order = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    # 医生不能执行
    assert client.post(f"/treatments/{order['id']}/execute", headers=auth["doctor"]).status_code == 403


def test_prescription_dosage_fields(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    drug = client.post(
        "/drugs/", json={"name": "阿莫西林", "base_price": 12.5}, headers=auth["admin"]
    ).json()
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={
            "drug_id": drug["id"],
            "quantity": 2,
            "dosage": "0.5g",
            "frequency": "tid",
            "route": "口服",
            "days": 5,
        },
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["dosage"] == "0.5g"
    assert body["frequency"] == "tid"
    assert body["route"] == "口服"
    assert body["days"] == 5

    # 默认值
    drug2 = client.post(
        "/drugs/", json={"name": "B药", "base_price": 5.0}, headers=auth["admin"]
    ).json()
    default = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug2["id"], "quantity": 1}, headers=auth["doctor"],
    ).json()
    assert default["days"] == 1
    assert default["dosage"] == ""

    html = client.get(f"/print/prescription/{encounter['id']}").text
    assert "0.5g" in html
    assert "tid" in html
    assert "口服" in html


def test_treatment_bad_item(client, auth):
    patient, doctor, reg, encounter, item = make_setup(client, auth)
    r = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": 999}, headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "治疗项目不存在或已停用"
