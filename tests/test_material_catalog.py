CSV_HEADER = (
    "医用耗材编码,耗材名称,规格,型号,生产厂家,单位,类别,耗材类型,注册证号\n"
)


def upload_catalog(client, auth):
    content = (
        CSV_HEADER
        + "MATC001,一次性注射器,5ml,5ml,演示医疗,支,耗材,耗材,械注准20260001\n"
        + "MATC002,多参数监护仪,M8,M8,演示医疗,台,设备,器械,械注准20260002\n"
    ).encode("utf-8")
    r = client.post(
        "/insurance/materials/import",
        files={"file": ("materials.csv", content, "text/csv")},
        headers=auth["admin"],
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_material_catalog_import_and_search(client, auth):
    result = upload_catalog(client, auth)
    assert result["total"] == 2
    assert result["inserted"] == 2

    rows = client.get(
        "/insurance/materials/search?q=监护", headers=auth["warehouse"]
    ).json()
    assert len(rows) == 1
    assert rows[0]["name"] == "多参数监护仪"
    assert rows[0]["material_type"] == "器械"

    devices = client.get(
        "/insurance/materials/search?category=设备", headers=auth["pharmacist"]
    ).json()
    assert [row["code"] for row in devices] == ["MATC002"]

    assert client.get(
        "/insurance/materials/search", headers=auth["cashier"]
    ).status_code == 403


def test_ensure_material_item_idempotent(client, auth):
    upload_catalog(client, auth)
    first = client.post(
        "/insurance/materials/MATC001/ensure-item", headers=auth["warehouse"]
    )
    assert first.status_code == 200, first.text
    item = first.json()
    assert item["name"] == "一次性注射器"
    assert item["category"] == "consumable"
    assert item["insurance_code"] == "MATC001"

    second = client.post(
        "/insurance/materials/MATC001/ensure-item", headers=auth["warehouse"]
    )
    assert second.status_code == 200
    assert second.json()["id"] == item["id"]

    assert client.post(
        "/insurance/materials/NOPE/ensure-item", headers=auth["warehouse"]
    ).status_code == 400
    assert client.post(
        "/insurance/materials/MATC001/ensure-item", headers=auth["cashier"]
    ).status_code == 403


def test_catalog_material_can_be_inbound(client, auth):
    upload_catalog(client, auth)
    item = client.post(
        "/insurance/materials/MATC002/ensure-item", headers=auth["warehouse"]
    ).json()

    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "other",
            "items": [
                {
                    "kind": "material",
                    "material_id": item["id"],
                    "quantity": 2,
                    "unit_price": 1500.0,
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
        f"/materials/stocks?item_id={item['id']}", headers=auth["admin"]
    ).json()
    assert stocks[0]["quantity"] == 2
    assert stocks[0]["warehouse"] == "总库"


def test_material_catalog_admin_page(client, auth):
    client.cookies.clear()
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/insurance-materials")
    assert page.status_code == 200
    assert "医保医用耗材目录" in page.text

    content = (CSV_HEADER + "MATC003,医用棉签,10cm,10cm,演示医疗,包,耗材,耗材,\n").encode("utf-8")
    uploaded = client.post(
        "/admin/insurance-materials/import",
        files={"file": ("materials.csv", content, "text/csv")},
        follow_redirects=False,
    )
    assert uploaded.status_code == 302
    page = client.get("/admin/insurance-materials")
    assert "MATC003" in page.text
