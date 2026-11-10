def test_material_and_charge_insurance_attributes(client, auth):
    material = client.post(
        "/materials/items/",
        json={
            "code": "MAT-INS-01",
            "name": "医保耗材",
            "unit": "个",
            "price": 12,
            "manufacturer": "某厂家",
            "registration_no": "械注准 20260001",
            "insurance_code": "C123456",
            "insurance_name": "医保耗材通用名",
            "insurance_category": "乙",
            "insurance_match_status": "matched",
        },
        headers=auth["admin"],
    )
    assert material.status_code == 201, material.text
    body = material.json()
    assert body["insurance_code"] == "C123456"
    assert body["insurance_category"] == "乙"

    charge = client.post(
        "/charges/items/",
        json={
            "code": "CHG-INS-01",
            "name": "医保服务项目",
            "category": "treatment",
            "price": 30,
            "insurance_code": "S123456",
            "insurance_name": "医保服务项目通用名",
            "insurance_category": "甲",
            "insurance_match_status": "matched",
            "unit": "次",
        },
        headers=auth["admin"],
    )
    assert charge.status_code == 201, charge.text
    assert charge.json()["insurance_code"] == "S123456"
    assert charge.json()["unit"] == "次"


def test_inbound_snapshot_keeps_insurance_attributes(client, auth):
    supplier = client.post(
        "/suppliers/",
        json={"code": "INS-SUP", "name": "属性供应商"},
        headers=auth["admin"],
    ).json()
    material = client.post(
        "/materials/items/",
        json={
            "code": "MAT-INS-02",
            "name": "入库医保耗材",
            "unit": "个",
            "price": 8,
            "insurance_code": "C999",
            "insurance_name": "入库耗材医保名",
            "insurance_category": "丙",
            "insurance_match_status": "matched",
        },
        headers=auth["admin"],
    ).json()
    order = client.post(
        "/inbound/orders",
        json={
            "order_type": "consumable",
            "supplier_id": supplier["id"],
            "items": [
                {
                    "kind": "material",
                    "material_id": material["id"],
                    "quantity": 5,
                    "insurance_code": "C999",
                    "insurance_name": "入库耗材医保名",
                    "insurance_category": "丙",
                    "insurance_match_status": "matched",
                }
            ],
        },
        headers=auth["warehouse"],
    )
    assert order.status_code == 201, order.text
    item = order.json()["items"][0]
    assert item["insurance_code"] == "C999"
    assert item["insurance_name"] == "入库耗材医保名"
    assert item["insurance_category"] == "丙"
    assert item["insurance_match_status"] == "matched"


def test_diagnosis_dictionary_category(client, auth):
    response = client.post(
        "/dict/diagnosis_icd10/entries",
        json={"code": "J06.9", "name": "急性上呼吸道感染", "category": "诊断"},
        headers=auth["admin"],
    )
    assert response.status_code == 201, response.text
    assert response.json()["category"] == "诊断"
