"""检验/检查/治疗取消与 0 元收费。"""


def _encounter(client, auth):
    patient = client.post(
        "/patients/", json={"name": "取消测试患者", "id_number": "110101199505059999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post("/departments/", json={"name": "取消测试科"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": "取消测试医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/", json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "测试"},
        headers=auth["doctor"],
    ).json()
    return encounter


def test_zero_price_lab_can_be_paid(client, auth):
    encounter = _encounter(client, auth)
    item = client.post(
        "/lab/items/", json={"code": "ZERO", "name": "零元检验", "price": 0},
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    )
    assert request.status_code == 201, request.text
    charges = client.get(f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]).json()
    assert any(c["amount"] == 0 and c["charge_type"] == "lab" for c in charges)
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    assert payment.status_code == 201, payment.text
    assert payment.json()["status"] == "paid"
    assert payment.json()["amount"] == 0


def test_cancel_lab_request_before_payment(client, auth):
    encounter = _encounter(client, auth)
    item = client.post(
        "/lab/items/", json={"code": "CANCEL", "name": "可取消检验", "price": 20},
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    cancelled = client.post(
        f"/lab/requests/{request['id']}/cancel", headers=auth["doctor"]
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    charges = client.get(f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]).json()
    assert next(c for c in charges if c["charge_type"] == "lab")["status"] == "cancelled"


def test_cancel_imaging_request_before_payment(client, auth):
    encounter = _encounter(client, auth)
    item = client.post(
        "/pacs/items/", json={"code": "IMGC", "name": "可取消检查", "price": 30},
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    cancelled = client.post(
        f"/pacs/requests/{request['id']}/cancel", headers=auth["doctor"]
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


def test_paid_lab_cancel_rejected(client, auth):
    encounter = _encounter(client, auth)
    item = client.post(
        "/lab/items/", json={"code": "PAIDC", "name": "已收费检验", "price": 20},
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    paid = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert paid.status_code == 201, paid.text
    response = client.post(
        f"/lab/requests/{request['id']}/cancel", headers=auth["doctor"]
    )
    assert response.status_code == 400
    assert "已收费" in response.json()["detail"]


def test_lab_worklist_hidden_until_paid(client, auth):
    encounter = _encounter(client, auth)
    item = client.post(
        "/lab/items/", json={"code": "PAIDONLY", "name": "收费后可见", "price": 20},
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    before = client.get("/lab/worklist", headers=auth["lab"]).json()
    assert all(row["id"] != request["id"] for row in before)
    paid = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert paid.status_code == 201, paid.text
    after = client.get("/lab/worklist", headers=auth["lab"]).json()
    assert any(row["id"] == request["id"] for row in after)


def test_imaging_worklist_hidden_until_paid(client, auth):
    encounter = _encounter(client, auth)
    item = client.post(
        "/pacs/items/", json={"code": "IMGPAID", "name": "收费后可见检查", "price": 30},
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    before = client.get("/pacs/worklist", headers=auth["radiology"]).json()
    assert all(row["id"] != request["id"] for row in before)
    paid = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert paid.status_code == 201, paid.text
    after = client.get("/pacs/worklist", headers=auth["radiology"]).json()
    assert any(row["id"] == request["id"] for row in after)


def test_lab_item_can_be_edited_and_deleted(client, auth):
    item = client.post(
        "/lab/items/", json={"code": "EDITLAB", "name": "原名", "price": 10},
        headers=auth["admin"],
    ).json()
    edited = client.put(
        f"/lab/items/{item['id']}",
        json={"code": "EDITLAB", "name": "新名", "price": 12},
        headers=auth["admin"],
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["name"] == "新名"
    assert edited.json()["price"] == 12
    deleted = client.delete(f"/lab/items/{item['id']}", headers=auth["admin"])
    assert deleted.status_code == 204


def test_charge_item_can_be_edited_and_disabled(client, auth):
    item = client.post(
        "/charges/items/",
        json={"code": "EDITCHG", "name": "原收费", "category": "other", "price": 5},
        headers=auth["admin"],
    ).json()
    edited = client.put(
        f"/charges/items/{item['id']}",
        json={"code": "EDITCHG", "name": "新收费", "category": "other", "price": 8},
        headers=auth["admin"],
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["name"] == "新收费"
    disabled = client.delete(f"/charges/items/{item['id']}", headers=auth["admin"])
    assert disabled.status_code == 200
    assert disabled.json()["active"] is False


def test_abandon_encounter_cancels_pending_items(client, auth):
    encounter = _encounter(client, auth)
    item = client.post(
        "/lab/items/", json={"code": "ABANDON", "name": "放弃检验", "price": 20},
        headers=auth["admin"],
    ).json()
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()
    abandoned = client.post(
        f"/encounters/{encounter['id']}/abandon",
        params={"reason": "患者中途离开"},
        headers=auth["doctor"],
    )
    assert abandoned.status_code == 200, abandoned.text
    assert abandoned.json()["status"] == "abandoned"
    rows = client.get(f"/lab/encounters/{encounter['id']}/lab-requests", headers=auth["doctor"]).json()
    assert rows[0]["status"] == "cancelled"
    charges = client.get(f"/charges/encounters/{encounter['id']}", headers=auth["cashier"]).json()
    assert all(row["status"] in ("cancelled", "refunded") for row in charges)
    # 已放弃就诊不能再开单
    blocked = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    )
    assert blocked.status_code in (400, 500)
