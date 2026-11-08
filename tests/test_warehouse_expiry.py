from datetime import date, timedelta


def make_drug(client, auth, name="效期测试药"):
    return client.post(
        "/drugs/", json={"name": name, "base_price": 10.0}, headers=auth["admin"]
    ).json()


def purchase(client, auth, drug, batch, expiry, quantity=5):
    return client.post(
        "/warehouse/purchase",
        json={
            "drug_id": drug["id"],
            "batch_no": batch,
            "expiry": expiry.isoformat(),
            "quantity": quantity,
        },
        headers=auth["admin"],
    )


def test_expiry_alerts(client, auth):
    today = date.today()
    drug = make_drug(client, auth)
    purchase(client, auth, drug, "EXP-OLD", today - timedelta(days=10), 2)
    purchase(client, auth, drug, "EXP-NEAR", today + timedelta(days=30), 3)
    purchase(client, auth, drug, "EXP-FAR", today + timedelta(days=400), 5)

    r = client.get("/warehouse/expiry-alerts?days=90", headers=auth["warehouse"])
    assert r.status_code == 200
    alerts = r.json()
    assert alerts["days"] == 90
    assert [row["batch_no"] for row in alerts["expired"]] == ["EXP-OLD"]
    assert alerts["expired"][0]["days_left"] < 0
    assert alerts["expired"][0]["quantity"] == 2
    assert [row["batch_no"] for row in alerts["near_expiry"]] == ["EXP-NEAR"]
    assert alerts["near_expiry"][0]["days_left"] == 30

    wider = client.get("/warehouse/expiry-alerts?days=800", headers=auth["pharmacist"]).json()
    assert {row["batch_no"] for row in wider["near_expiry"]} == {"EXP-NEAR", "EXP-FAR"}

    assert client.get("/warehouse/expiry-alerts", headers=auth["cashier"]).status_code == 403


def test_expiry_alerts_admin_page(client, auth):
    today = date.today()
    drug = make_drug(client, auth, "页面效期药")
    purchase(client, auth, drug, "PAGE-EXP", today - timedelta(days=1), 2)

    client.cookies.clear()
    client.post(
        "/admin/login", data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/expiry-alerts?days=90")
    assert page.status_code == 200
    assert "效期预警" in page.text
    assert "PAGE-EXP" in page.text
    assert "已过期" in page.text


def test_fefo_auto_allocation(client, auth):
    today = date.today()
    drug = make_drug(client, auth, "FEFO药")
    purchase(client, auth, drug, "FEFO-LATE", today + timedelta(days=400), 5)
    purchase(client, auth, drug, "FEFO-EARLY", today + timedelta(days=30), 5)

    order = client.post(
        "/warehouse/outbound-orders",
        json={"items": [{"kind": "drug", "drug_id": drug["id"], "quantity": 7}]},
        headers=auth["pharmacist"],
    )
    assert order.status_code == 201
    order = order.json()
    assert order["items"][0]["batch_no"] == ""
    client.post(f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"])
    issued = client.post(
        f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["warehouse"]
    )
    assert issued.status_code == 200

    warehouse = {
        row["batch_no"]: row["quantity"]
        for row in client.get(f"/warehouse/stocks?drug_id={drug['id']}", headers=auth["admin"]).json()
    }
    pharmacy = {
        row["batch_no"]: row["quantity"]
        for row in client.get(f"/pharmacy/stocks?drug_id={drug['id']}", headers=auth["admin"]).json()
    }
    assert warehouse == {"FEFO-LATE": 3, "FEFO-EARLY": 0}
    assert pharmacy == {"FEFO-EARLY": 5, "FEFO-LATE": 2}

    ledger = client.get("/stock/ledger?ref_type=outbound", headers=auth["admin"]).json()
    assert len(ledger) == 4
    assert sum(row["quantity"] for row in ledger) == 14  # 两批各 out+in，共 7×2


def test_fefo_excludes_expired(client, auth):
    today = date.today()
    drug = make_drug(client, auth, "过期FEFO药")
    purchase(client, auth, drug, "FEFO-EXPIRED", today - timedelta(days=1), 5)

    order = client.post(
        "/warehouse/outbound-orders",
        json={"items": [{"kind": "drug", "drug_id": drug["id"], "quantity": 1}]},
        headers=auth["pharmacist"],
    ).json()
    client.post(f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"])
    issue = client.post(
        f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["warehouse"]
    )
    assert issue.status_code == 400
    assert "库存不足" in issue.json()["detail"]
    stocks = client.get(f"/warehouse/stocks?drug_id={drug['id']}", headers=auth["admin"]).json()
    assert stocks[0]["quantity"] == 5
