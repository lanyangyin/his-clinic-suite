"""中药处方与煎药室：开方→审方→发药→浸泡→煎煮→包装→发放。"""


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "中药患者", "id_number": "110101198501019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "中医科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "中医医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "风寒感冒"},
        headers=auth["doctor"],
    ).json()
    herb_a = client.post(
        "/tcm/herbs",
        json={
            "code": "TCM-GC",
            "name": "桂枝",
            "price_per_g": 0.1,
            "toxicity": "none",
        },
        headers=auth["admin"],
    ).json()
    herb_b = client.post(
        "/tcm/herbs",
        json={
            "code": "TCM-BS",
            "name": "白芍",
            "price_per_g": 0.2,
        },
        headers=auth["admin"],
    ).json()
    return patient, encounter, herb_a, herb_b


def _prescribe(client, auth, encounter, herb_a, herb_b, service="decoct"):
    return client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={
            "formula_name": "桂枝汤",
            "usage": "internal",
            "packs": 3,
            "decoct_service": service,
            "decoction_method": "常规煎煮，先煎",
            "items": [
                {"herb_id": herb_a["id"], "dose_g": 9, "special": "none"},
                {"herb_id": herb_b["id"], "dose_g": 6, "special": "last"},
            ],
        },
        headers=auth["doctor"],
    )


def test_tcm_prescription_and_decoction_flow(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    response = _prescribe(client, auth, encounter, herb_a, herb_b)
    assert response.status_code == 201, response.text
    prescription = response.json()
    assert prescription["prescription_no"].startswith("TCM")
    assert prescription["status"] == "pending"
    assert prescription["total_amount"] == 6.3  # (0.1*9+0.2*6)*3
    assert len(prescription["items"]) == 2
    assert prescription["items"][1]["special"] == "last"

    work = client.get(
        "/tcm/prescriptions", params={"status": "pending"}, headers=auth["pharmacist"]
    ).json()
    assert any(row["prescription_no"] == prescription["prescription_no"] for row in work)

    reviewed = client.post(
        f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"]
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"

    dispensed = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense",
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 200
    assert dispensed.json()["status"] == "decocting"

    orders = client.get(
        "/tcm/decoction-orders", headers=auth["decoction"]
    ).json()
    order = next(row for row in orders if row["prescription_id"] == prescription["id"])
    assert order["patient_name"] == "中药患者"

    soaked = client.post(
        f"/tcm/decoction-orders/{order['id']}/soak",
        json={"soak_minutes": 30},
        headers=auth["decoction"],
    )
    assert soaked.status_code == 200
    assert soaked.json()["status"] == "soaking"

    decocted = client.post(
        f"/tcm/decoction-orders/{order['id']}/decoct",
        json={"machine_no": "煎药机-1", "decoct_minutes": 40},
        headers=auth["decoction"],
    )
    assert decocted.status_code == 200
    assert decocted.json()["status"] == "decocting"

    packaged = client.post(
        f"/tcm/decoction-orders/{order['id']}/package",
        json={"bags": 6, "bag_volume_ml": 200, "expires_days": 7},
        headers=auth["decoction"],
    )
    assert packaged.status_code == 200, packaged.text
    body = packaged.json()
    assert body["status"] == "completed"
    assert body["bags"] == 6
    assert len(body["bags_list"]) == 6
    assert "中药患者" in body["bags_list"][0]["label"]
    headers = client.get(
        f"/encounters/{body['encounter_id']}/prescriptions/headers",
        headers=auth["pharmacist"],
    ).json()
    header = next(row for row in headers if row["id"] == prescription["prescription_id"])
    assert header["status"] == "dispensed", header

    issued = client.post(
        f"/tcm/decoction-orders/{order['id']}/issue",
        json={"pickup_method": "self", "receiver": "患者本人"},
        headers=auth["decoction"],
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "issued"

    detail = client.get(
        f"/tcm/prescriptions/{prescription['id']}", headers=auth["pharmacist"]
    ).json()
    assert detail["status"] == "completed"


def test_self_decoct_and_invalid_transitions(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    prescription = _prescribe(client, auth, encounter, herb_a, herb_b, service="self").json()
    # 未审核不能发药
    blocked = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense",
        headers=auth["pharmacist"],
    )
    assert blocked.status_code == 400
    client.post(f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"])
    dispensed = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense",
        headers=auth["pharmacist"],
    ).json()
    assert dispensed["status"] == "completed"
    orders = client.get("/tcm/decoction-orders", headers=auth["pharmacist"]).json()
    assert all(row["prescription_id"] != prescription["id"] for row in orders)


def test_tcm_permissions(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    response = _prescribe(client, auth, encounter, herb_a, herb_b)
    prescription = response.json()
    # 医生不能审核中药处方
    denied = client.post(
        f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["doctor"]
    )
    assert denied.status_code == 403
    # 药师不能开方
    assert client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={"items": [{"herb_id": herb_a["id"], "dose_g": 1}]},
        headers=auth["pharmacist"],
    ).status_code == 403


def test_tcm_links_to_unified_prescription_header(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    prescription = _prescribe(client, auth, encounter, herb_a, herb_b).json()
    assert prescription["prescription_id"]
    reviews = client.get("/pharmacy/prescription-reviews", headers=auth["pharmacist"]).json()
    assert all(row["id"] != prescription["prescription_id"] for row in reviews)
    headers = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()
    tcm_header = next(row for row in headers if row["type"] == "tcm_herb" and row["id"] == prescription["prescription_id"])
    assert tcm_header["item_count"] == 2
    center = client.get(
        f"/encounters/{encounter['id']}/prescription-center", headers=auth["doctor"]
    ).json()
    assert any(row["id"] == prescription["id"] for row in center["tcm"])
    lines = client.get(
        f"/encounters/{encounter['id']}/prescription-lines", headers=auth["doctor"]
    ).json()
    assert any(row["kind"] == "herb" for row in lines)
    client.post(f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"])
    headers = client.get(
        f"/encounters/{encounter['id']}/prescriptions/headers"
    ).json()
    assert next(row for row in headers if row["id"] == prescription["prescription_id"])["status"] == "approved"


def test_tcm_pending_item_edit_and_delete(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    prescription = _prescribe(client, auth, encounter, herb_a, herb_b).json()
    item = prescription["items"][0]
    edited = client.put(
        f"/tcm/prescriptions/{prescription['id']}/items/{item['id']}",
        json={"dose_g": 12, "special": "first", "note": "先煎"},
        headers=auth["doctor"],
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["items"][0]["dose_g"] == 12
    lines = client.get(
        f"/encounters/{encounter['id']}/prescription-lines", headers=auth["doctor"]
    ).json()
    assert any(row["kind"] == "herb" and row["quantity"] == 12 for row in lines)
    deleted = client.delete(
        f"/tcm/prescriptions/{prescription['id']}/items/{item['id']}",
        headers=auth["doctor"],
    )
    assert deleted.status_code == 204
    lines_after = client.get(
        f"/encounters/{encounter['id']}/prescription-lines", headers=auth["doctor"]
    ).json()
    herbs = [row for row in lines_after if row["kind"] == "herb"]
    assert len(herbs) == 1


def test_tcm_incompatible_pair_rejected(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    gan_cao = client.post(
        "/tcm/herbs",
        json={"code": "TCM-GANCao", "name": "甘草", "price_per_g": 0.1},
        headers=auth["admin"],
    ).json()
    gan_sui = client.post(
        "/tcm/herbs",
        json={"code": "TCM-GanSui", "name": "甘遂", "price_per_g": 0.2, "toxicity": "toxic"},
        headers=auth["admin"],
    ).json()
    response = client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={
            "formula_name": "禁忌方",
            "items": [
                {"herb_id": gan_cao["id"], "dose_g": 6},
                {"herb_id": gan_sui["id"], "dose_g": 3},
            ],
        },
        headers=auth["doctor"],
    )
    assert response.status_code == 400
    assert "配伍禁忌" in response.json()["detail"]


def test_tcm_toxic_herb_dose_limit(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    toxic = client.post(
        "/tcm/herbs",
        json={
            "code": "TCM-TOXIC", "name": "制川乌", "price_per_g": 0.2,
            "toxicity": "toxic", "max_dose_g": 3,
        },
        headers=auth["admin"],
    ).json()
    response = client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={"items": [{"herb_id": toxic["id"], "dose_g": 5}]},
        headers=auth["doctor"],
    )
    assert response.status_code == 400
    assert "超过上限" in response.json()["detail"]


def test_tcm_stock_deduct_and_insufficient_rejected(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    stocked = client.post(
        "/tcm/herbs",
        json={"code": "TCM-STOCK", "name": "库存饮片", "price_per_g": 0.1, "stock_g": 10},
        headers=auth["admin"],
    ).json()
    response = client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={"packs": 2, "items": [{"herb_id": stocked["id"], "dose_g": 8}]},
        headers=auth["doctor"],
    )
    prescription = response.json()
    # 2 剂 × 8g = 16g，库存只有 10g
    client.post(f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"])
    blocked = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense", headers=auth["pharmacist"]
    )
    assert blocked.status_code == 400
    assert "库存不足" in blocked.json()["detail"]


def test_tcm_stock_is_deducted_on_dispense(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    stocked = client.post(
        "/tcm/herbs",
        json={"code": "TCM-STOCK2", "name": "库存饮片二", "price_per_g": 0.1, "stock_g": 100},
        headers=auth["admin"],
    ).json()
    prescription = client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={"packs": 2, "items": [{"herb_id": stocked["id"], "dose_g": 8}]},
        headers=auth["doctor"],
    ).json()
    client.post(f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"])
    dispensed = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense", headers=auth["pharmacist"]
    )
    assert dispensed.status_code == 200, dispensed.text
    herbs = client.get("/tcm/herbs", headers=auth["pharmacist"]).json()
    row = next(item for item in herbs if item["id"] == stocked["id"])
    assert row["stock_g"] == 84


def test_tcm_batches_expire_first(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    herb = client.post(
        "/tcm/herbs",
        json={"code": "TCM-BATCH", "name": "批次饮片", "price_per_g": 0.1},
        headers=auth["admin"],
    ).json()
    near = client.post(
        f"/tcm/herbs/{herb['id']}/stock-batches",
        json={"batch_no": "NEAR", "quantity_g": 5, "expiry": "2026-12-01T00:00:00"},
        headers=auth["admin"],
    ).json()
    far = client.post(
        f"/tcm/herbs/{herb['id']}/stock-batches",
        json={"batch_no": "FAR", "quantity_g": 20, "expiry": "2027-12-01T00:00:00"},
        headers=auth["admin"],
    ).json()
    prescription = client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={"packs": 2, "items": [{"herb_id": herb["id"], "dose_g": 8}]},
        headers=auth["doctor"],
    ).json()
    client.post(f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"])
    assert client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense", headers=auth["pharmacist"]
    ).status_code == 200
    batches = client.get(f"/tcm/herbs/{herb['id']}/stock-batches", headers=auth["pharmacist"]).json()
    by_no = {row["batch_no"]: row for row in batches}
    assert by_no["NEAR"]["quantity_g"] == 0
    assert by_no["FAR"]["quantity_g"] == 9


def test_expired_tcm_batch_not_usable(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    herb = client.post(
        "/tcm/herbs",
        json={"code": "TCM-EXPIRED", "name": "过期饮片", "price_per_g": 0.1},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/tcm/herbs/{herb['id']}/stock-batches",
        json={"batch_no": "OLD", "quantity_g": 100, "expiry": "2020-01-01T00:00:00"},
        headers=auth["admin"],
    )
    prescription = client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={"items": [{"herb_id": herb["id"], "dose_g": 5}]},
        headers=auth["doctor"],
    ).json()
    client.post(f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"])
    blocked = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense", headers=auth["pharmacist"]
    )
    assert blocked.status_code == 400
    assert "无有效批次" in blocked.json()["detail"]


def test_tcm_batch_trace_list(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    herb = client.post(
        "/tcm/herbs",
        json={"code": "TCM-TRACE", "name": "追溯饮片", "price_per_g": 0.1},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/tcm/herbs/{herb['id']}/stock-batches",
        json={"batch_no": "TRACE-1", "quantity_g": 12, "expiry": "2027-01-01T00:00:00"},
        headers=auth["admin"],
    )
    rows = client.get("/tcm/stock-batches", headers=auth["pharmacist"]).json()
    row = next(item for item in rows if item["batch_no"] == "TRACE-1")
    assert row["herb_name"] == "追溯饮片"
    assert row["quantity_g"] == 12
    assert row["expired"] is False
