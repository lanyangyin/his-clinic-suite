def make_encounter(client, auth):
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "骨科"}, headers=auth["admin"]
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
    return client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "骨折"},
        headers=auth["doctor"],
    ).json()


def make_item(client, auth, code="STENT01", name="冠脉支架", high_value=True):
    return client.post(
        "/materials/items/",
        json={"code": code, "name": name, "spec": "3.0*18mm", "unit": "个", "price": 8800.0, "is_high_value": high_value},
        headers=auth["admin"],
    )


def stock_in(client, auth, item_id, warehouse="总库", quantity=5):
    return client.post(
        "/materials/stock-in",
        json={"item_id": item_id, "warehouse": warehouse, "quantity": quantity},
        headers=auth["admin"],
    )


def test_create_material_item(client, auth):
    r = make_item(client, auth)
    assert r.status_code == 201
    body = r.json()
    assert body["code"] == "STENT01"
    assert body["is_high_value"] is True


def test_duplicate_item_code_rejected(client, auth):
    make_item(client, auth)
    r = make_item(client, auth)
    assert r.status_code == 400
    assert r.json()["detail"] == "物资编码已存在"


def test_stock_in_merges(client, auth):
    item = make_item(client, auth).json()
    first = stock_in(client, auth, item["id"], quantity=5).json()
    second = stock_in(client, auth, item["id"], quantity=3)
    assert second.status_code == 201
    assert second.json()["id"] == first["id"]
    assert second.json()["quantity"] == 8


def test_stock_in_missing_item(client, auth):
    r = stock_in(client, auth, 999)
    assert r.status_code == 400
    assert r.json()["detail"] == "物资不存在"


def test_use_high_value_material(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    stock_in(client, auth, item["id"], quantity=5)
    r = client.post(
        "/materials/usages",
        json={"item_id": item["id"], "serial_no": "SN-0001", "encounter_id": encounter["id"], "warehouse": "总库"},
        headers=auth["nurse"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["serial_no"] == "SN-0001"
    assert body["used_by"] == "nurse"
    assert body["encounter_id"] == encounter["id"]
    # 库存扣减
    stocks = client.get(f"/materials/stocks?item_id={item['id']}").json()
    assert stocks[0]["quantity"] == 4


def test_duplicate_serial_rejected(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    stock_in(client, auth, item["id"], quantity=5)
    payload = {"item_id": item["id"], "serial_no": "SN-0001", "encounter_id": encounter["id"], "warehouse": "总库"}
    client.post("/materials/usages", json=payload, headers=auth["nurse"])
    r = client.post("/materials/usages", json=payload, headers=auth["nurse"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该序列号已使用"


def test_use_non_high_value_rejected(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth, code="GAUZE01", name="纱布", high_value=False).json()
    stock_in(client, auth, item["id"], quantity=10)
    r = client.post(
        "/materials/usages",
        json={"item_id": item["id"], "serial_no": "SN-0002", "encounter_id": encounter["id"], "warehouse": "总库"},
        headers=auth["nurse"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该物资不是高值耗材，无需追溯"


def test_use_insufficient_stock_rejected(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    stock_in(client, auth, item["id"], warehouse="骨科病区", quantity=0)
    r = client.post(
        "/materials/usages",
        json={"item_id": item["id"], "serial_no": "SN-0003", "encounter_id": encounter["id"], "warehouse": "骨科病区"},
        headers=auth["nurse"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该库房物资库存不足"


def test_use_missing_encounter(client, auth):
    item = make_item(client, auth).json()
    stock_in(client, auth, item["id"], quantity=5)
    r = client.post(
        "/materials/usages",
        json={"item_id": item["id"], "serial_no": "SN-0004", "encounter_id": 999, "warehouse": "总库"},
        headers=auth["nurse"],
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "就诊记录不存在"


def test_usage_audit_trail(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    stock_in(client, auth, item["id"], quantity=5)
    client.post(
        "/materials/usages",
        json={"item_id": item["id"], "serial_no": "SN-0005", "encounter_id": encounter["id"], "warehouse": "总库"},
        headers=auth["nurse"],
    )
    r = client.get(f"/materials/usages?item_id={item['id']}")
    assert r.status_code == 200
    usages = r.json()
    assert len(usages) == 1
    assert usages[0]["serial_no"] == "SN-0005"


def test_role_protection(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    # 未登录不能使用耗材
    r = client.post(
        "/materials/usages",
        json={"item_id": item["id"], "serial_no": "SN-9999", "encounter_id": encounter["id"], "warehouse": "总库"},
    )
    assert r.status_code == 401


def test_role_protection_explicit(client, auth):
    item = make_item(client, auth).json()
    r = client.post(
        "/materials/stock-in",
        json={"item_id": item["id"], "warehouse": "总库", "quantity": 1},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
