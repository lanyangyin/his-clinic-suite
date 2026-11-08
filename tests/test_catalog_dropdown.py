def import_catalog(client, auth):
    content = (
        "国家医保药品代码,药品名称,剂型,规格,生产厂家,单位,医保类别\n"
        "DD001,下拉目录药,片剂,0.5g*10片,演示药业,盒,甲\n"
    ).encode("utf-8")
    r = client.post(
        "/insurance/catalog/import",
        files={"file": ("dropdown.csv", content, "text/csv")},
        headers=auth["admin"],
    )
    assert r.status_code == 200, r.text


def test_ensure_drug_from_catalog_idempotent(client, auth):
    import_catalog(client, auth)
    first = client.post(
        "/insurance/catalog/DD001/ensure-drug", headers=auth["warehouse"]
    )
    assert first.status_code == 200, first.text
    drug = first.json()
    assert drug["name"] == "下拉目录药"
    assert drug["insurance_code"] == "DD001"
    assert drug["insurance_category"] == "甲"
    assert drug["insurance_match_status"] == "matched"
    assert drug["spec"] == "0.5g*10片"

    second = client.post(
        "/insurance/catalog/DD001/ensure-drug", headers=auth["warehouse"]
    )
    assert second.status_code == 200
    assert second.json()["id"] == drug["id"]

    assert client.post(
        "/insurance/catalog/NOPE/ensure-drug", headers=auth["warehouse"]
    ).status_code == 400
    assert client.post(
        "/insurance/catalog/DD001/ensure-drug", headers=auth["cashier"]
    ).status_code == 403


def test_catalog_drug_can_be_inbound(client, auth):
    import_catalog(client, auth)
    drug = client.post(
        "/insurance/catalog/DD001/ensure-drug", headers=auth["warehouse"]
    ).json()

    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "DD-B1",
                    "expiry": "2028-12-31",
                    "quantity": 3,
                    "unit_price": 12.5,
                }
            ],
        },
        headers=auth["warehouse"],
    )
    assert inbound.status_code == 201, inbound.text
    order = inbound.json()
    client.post(f"/inbound/orders/{order['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{order['id']}/stock", headers=auth["warehouse"])

    stocks = client.get(
        f"/warehouse/stocks?drug_id={drug['id']}", headers=auth["admin"]
    ).json()
    assert stocks[0]["quantity"] == 3
