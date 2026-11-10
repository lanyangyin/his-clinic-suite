from datetime import date


def payload(**overrides):
    data = {
        "name": "建档测试",
        "id_type": "id_card",
        "id_number": "110101199203041234",
        "phone": "13800138001",
        "address": "北京市东城区某街道 1 号",
        "emergency_contact_name": "家属",
        "emergency_contact_relation": "配偶",
        "emergency_contact_phone": "13900139001",
        "insurance_type": "employee",
        "allergy_status": "present",
        "allergy_detail": "青霉素",
        "privacy_consent": True,
    }
    data.update(overrides)
    return data


def test_full_profile_and_id_derivation(client, auth):
    response = client.post("/patients/", json=payload(), headers=auth["cashier"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["patient_no"].startswith("P")
    assert body["gender"] == "male"
    assert body["birth_date"] == "1992-03-04"
    assert body["age"] >= 30
    assert body["allergy_label"] == "青霉素"
    assert body["privacy_consent_at"] is not None
    assert body["address"].startswith("北京市")


def test_duplicate_check_and_existing(client, auth):
    created = client.post("/patients/", json=payload(), headers=auth["cashier"]).json()
    check = client.get(
        "/patients/duplicates",
        params={"name": "建档测试", "id_number": "110101199203041234"},
        headers=auth["cashier"],
    )
    assert check.status_code == 200
    body = check.json()
    assert body["exact"] is True
    assert body["candidates"][0]["id"] == created["id"]
    assert body["candidates"][0]["patient_no"] == created["patient_no"]


def test_update_profile(client, auth):
    created = client.post("/patients/", json=payload(), headers=auth["cashier"]).json()
    response = client.put(
        f"/patients/{created['id']}",
        json={
            "phone": "13700137001",
            "address": "新地址",
            "allergy_status": "none",
            "allergy_detail": "应被清空",
        },
        headers=auth["cashier"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["phone"] == "13700137001"
    assert body["address"] == "新地址"
    assert body["allergy_label"] == "无过敏史"
    assert body["allergy_detail"] == ""


def test_no_id_patient_allowed(client, auth):
    response = client.post(
        "/patients/",
        json={
            "name": "无名氏",
            "id_type": "none",
            "gender": "unknown",
            "birth_date": "2000-01-01",
            "phone": "13600136001",
            "privacy_consent": True,
        },
        headers=auth["cashier"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id_number"] is None
    assert body["id_type"] == "none"
    assert body["patient_no"].startswith("P")


def test_id_card_number_required(client, auth):
    response = client.post(
        "/patients/",
        json={"name": "无号码", "id_type": "id_card", "privacy_consent": True},
        headers=auth["cashier"],
    )
    assert response.status_code == 422
