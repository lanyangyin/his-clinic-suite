from datetime import date, timedelta


def _otc_drug(client, auth, name="OTC 创可贴"):
    return client.post(
        "/drugs/",
        json={"name": name, "base_price": 3, "unit": "片", "is_otc": True},
        headers=auth["admin"],
    ).json()


def test_otc_retail_sale_deducts_stock_and_refunds(client, auth):
    drug = _otc_drug(client, auth)
    stock = client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "OTC-B1",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 10,
        },
        headers=auth["pharmacist"],
    )
    assert stock.status_code == 201, stock.text

    catalog = client.get("/pharmacy/retail-catalog", headers=auth["pharmacist"])
    assert catalog.status_code == 200
    assert any(row["id"] == drug["id"] for row in catalog.json()["drugs"])

    sale = client.post(
        "/pharmacy/retail-sales",
        json={
            "customer_name": "散客",
            "channel": "cash",
            "items": [{"kind": "drug", "drug_id": drug["id"], "quantity": 2}],
        },
        headers=auth["pharmacist"],
    )
    assert sale.status_code == 201, sale.text
    body = sale.json()
    assert body["sale_no"].startswith("LS")
    assert body["total_amount"] == 6
    assert body["items"][0]["batch_no"] == "OTC-B1"
    assert (
        client.get(
            "/pharmacy/stocks", params={"drug_id": drug["id"]},
            headers=auth["pharmacist"],
        ).json()[0]["quantity"]
        == 8
    )

    receipt = client.get(f"/print/retail/{body['id']}")
    assert receipt.status_code == 200
    assert "零售" in receipt.text
    assert "OTC 创可贴" in receipt.text

    refunded = client.post(
        f"/pharmacy/retail-sales/{body['id']}/refund",
        headers=auth["pharmacist"],
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"
    assert (
        client.get(
            "/pharmacy/stocks", params={"drug_id": drug["id"]},
            headers=auth["pharmacist"],
        ).json()[0]["quantity"]
        == 10
    )


def test_prescription_drug_cannot_be_retailed(client, auth):
    drug = client.post(
        "/drugs/",
        json={"name": "处方药不可零售", "base_price": 10, "is_otc": False},
        headers=auth["admin"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "RX-B1",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 5,
        },
        headers=auth["pharmacist"],
    )
    response = client.post(
        "/pharmacy/retail-sales",
        json={"items": [{"kind": "drug", "drug_id": drug["id"], "quantity": 1}]},
        headers=auth["pharmacist"],
    )
    assert response.status_code == 400
    assert "处方药" in response.json()["detail"]


def test_material_retail_sale(client, auth):
    item = client.post(
        "/materials/items/",
        json={"code": "MASK-01", "name": "医用口罩", "unit": "个", "price": 1.5},
        headers=auth["admin"],
    ).json()
    stock = client.post(
        "/materials/stock-in",
        json={"item_id": item["id"], "warehouse": "药房", "quantity": 20},
        headers=auth["admin"],
    )
    assert stock.status_code == 201, stock.text
    sale = client.post(
        "/pharmacy/retail-sales",
        json={
            "items": [
                {"kind": "material", "material_id": item["id"], "quantity": 5}
            ]
        },
        headers=auth["pharmacist"],
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["total_amount"] == 7.5
    refunded = client.post(
        f"/pharmacy/retail-sales/{sale.json()['id']}/refund",
        headers=auth["pharmacist"],
    )
    assert refunded.status_code == 200
