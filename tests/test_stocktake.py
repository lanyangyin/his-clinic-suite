"""药品/耗材盘点。"""
from datetime import date, timedelta


def test_drug_stocktake_adjusts_stock(client, auth):
    drug = client.post(
        "/drugs/",
        json={"name": "盘点药品", "base_price": 12.5},
        headers=auth["admin"],
    ).json()
    client.post(
        "/warehouse/purchase",
        json={
            "drug_id": drug["id"],
            "batch_no": "ST-B1",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 10,
        },
        headers=auth["admin"],
    )
    take = client.post(
        "/stocktakes",
        json={"kind": "drug", "title": "药品盘点", "note": "测试"},
        headers=auth["warehouse"],
    )
    assert take.status_code == 201, take.text
    body = take.json()
    assert body["take_no"].startswith("ST")
    item = next(row for row in body["items"] if row["drug_id"] == drug["id"])

    incomplete = client.post(
        f"/stocktakes/{body['id']}/complete", headers=auth["warehouse"]
    )
    assert incomplete.status_code == 400
    assert "未录入" in incomplete.json()["detail"]

    saved = client.put(
        f"/stocktakes/{body['id']}/counts",
        json={"items": [{"item_id": item["id"], "actual_quantity": 7}]},
        headers=auth["warehouse"],
    )
    assert saved.status_code == 200
    counted = next(row for row in saved.json()["items"] if row["id"] == item["id"])
    assert counted["difference"] == -3

    done = client.post(
        f"/stocktakes/{body['id']}/complete", headers=auth["warehouse"]
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    stocks = client.get(
        f"/warehouse/stocks?drug_id={drug['id']}", headers=auth["admin"]
    ).json()
    assert stocks[0]["quantity"] == 7


def test_material_stocktake_and_page(client, auth):
    item = client.post(
        "/materials/items/",
        json={"code": "ST-M1", "name": "盘点耗材", "unit": "个", "price": 8, "category": "consumable"},
        headers=auth["admin"],
    ).json()
    client.post(
        "/materials/stock-in",
        json={"item_id": item["id"], "warehouse": "总库", "quantity": 20},
        headers=auth["admin"],
    )
    take = client.post(
        "/stocktakes",
        json={"kind": "material", "warehouse": "总库", "title": "耗材盘点"},
        headers=auth["pharmacist"],
    ).json()
    line = next(row for row in take["items"] if row["material_id"] == item["id"])
    client.put(
        f"/stocktakes/{take['id']}/counts",
        json={"items": [{"item_id": line["id"], "actual_quantity": 18}]},
        headers=auth["pharmacist"],
    )
    done = client.post(
        f"/stocktakes/{take['id']}/complete", headers=auth["pharmacist"]
    )
    assert done.status_code == 200
    stocks = client.get(
        f"/materials/stocks?item_id={item['id']}", headers=auth["admin"]
    ).json()
    assert sum(row["quantity"] for row in stocks if row["warehouse"] == "总库") == 18

    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get(f"/admin/stocktakes/{take['id']}")
    assert page.status_code == 200
    assert "盘点单" in page.text

    assert (
        client.get("/stocktakes", headers=auth["cashier"]).status_code == 403
    )
