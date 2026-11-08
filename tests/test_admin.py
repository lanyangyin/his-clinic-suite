def login(client, username="admin", password="admin123"):
    return client.post(
        "/admin/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_login_page(client, auth):
    client.cookies.clear()
    r = client.get("/admin/login")
    assert r.status_code == 200
    assert "HIS 门诊部管理台" in r.text
    assert "登录" in r.text


def test_admin_requires_login(client, auth):
    client.cookies.clear()
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/login"


def test_login_success_and_dashboard(client, auth):
    client.cookies.clear()
    r = login(client)
    assert r.status_code == 302
    assert r.headers["location"] == "/admin"

    page = client.get("/admin")
    assert page.status_code == 200
    assert "运营概览" in page.text
    assert "患者总数" in page.text
    assert "最近操作" in page.text


def test_login_wrong_password(client, auth):
    client.cookies.clear()
    r = login(client, password="wrong")
    assert r.status_code == 400
    assert "账号或密码错误" in r.text


def test_login_non_admin_rejected(client, auth):
    client.cookies.clear()
    r = login(client, username="doctor", password="doctor123")
    assert r.status_code == 400
    assert "不是管理员" in r.text


def test_department_create(client, auth):
    client.cookies.clear()
    assert login(client).status_code == 302
    r = client.post(
        "/admin/master/departments", data={"name": "内科"}, follow_redirects=False
    )
    assert r.status_code == 302
    page = client.get("/admin/master/departments")
    assert "内科" in page.text


def test_doctor_create(client, auth):
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    client.cookies.clear()
    assert login(client).status_code == 302
    r = client.post(
        "/admin/master/doctors",
        data={"name": "王医生", "department_id": department["id"]},
        follow_redirects=False,
    )
    assert r.status_code == 302
    page = client.get("/admin/master/doctors")
    assert "王医生" in page.text
    assert "内科" in page.text


def test_drug_create(client, auth):
    client.cookies.clear()
    assert login(client).status_code == 302
    r = client.post(
        "/admin/master/drugs",
        data={
            "name": "阿莫西林",
            "spec": "0.25g*24粒",
            "unit": "盒",
            "base_price": "12.5",
            "insurance_ratio": "0.8",
            "antibiotic_level": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    page = client.get("/admin/master/drugs")
    assert "阿莫西林" in page.text
    assert "12.50" in page.text


def test_charge_item_create(client, auth):
    client.cookies.clear()
    assert login(client).status_code == 302
    r = client.post(
        "/admin/master/charge-items",
        data={
            "code": "REG",
            "name": "挂号费",
            "category": "registration",
            "price": "10",
            "insurance_ratio": "0.7",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    page = client.get("/admin/master/charge-items")
    assert "REG" in page.text
    assert "挂号费" in page.text


def test_user_create(client, auth):
    client.cookies.clear()
    assert login(client).status_code == 302
    r = client.post(
        "/admin/users",
        data={
            "username": "cashier2",
            "password": "pass123456",
            "role": "cashier",
            "display_name": "新收费员",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    page = client.get("/admin/users")
    assert "cashier2" in page.text


def test_audit_page(client, auth):
    # 先产生一条写操作审计日志
    client.post(
        "/patients/",
        json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    )
    client.cookies.clear()
    assert login(client).status_code == 302
    page = client.get("/admin/audit")
    assert page.status_code == 200
    assert "审计日志" in page.text
    assert "/patients/" in page.text

    filtered = client.get("/admin/audit?username=cashier")
    assert filtered.status_code == 200
    assert "cashier" in filtered.text


def test_reports_page(client, auth):
    client.cookies.clear()
    assert login(client).status_code == 302
    page = client.get("/admin/reports")
    assert page.status_code == 200
    assert "科室收入" in page.text
    assert "处方点评汇总" in page.text
    assert "抗菌药物使用率" in page.text


def test_logout(client, auth):
    client.cookies.clear()
    assert login(client).status_code == 302
    r = client.get("/admin/logout", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/login"
    assert client.get("/admin", follow_redirects=False).status_code == 302


def _make_inbound_order(client, auth):
    supplier = client.post(
        "/suppliers/", json={"code": "SUP-ADMIN", "name": "管理台供应商"},
        headers=auth["admin"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "管理台入库药", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    order = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "supplier_id": supplier["id"],
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "ADMIN-B1",
                    "expiry": "2027-12-31",
                    "quantity": 5,
                }
            ],
        },
        headers=auth["warehouse"],
    ).json()
    return order


def test_inbound_admin_pages(client, auth):
    order = _make_inbound_order(client, auth)
    client.cookies.clear()
    assert login(client).status_code == 302

    page = client.get("/admin/inbound")
    assert page.status_code == 200
    assert "入库单" in page.text
    assert order["order_no"] in page.text

    detail = client.get(f"/admin/inbound/{order['id']}")
    assert detail.status_code == 200
    assert order["order_no"] in detail.text
    assert "ADMIN-B1" in detail.text

    item_id = order["items"][0]["id"]
    checked = client.post(
        f"/admin/inbound/{order['id']}/check",
        data={f"rejected_{item_id}": "1", f"reason_{item_id}": "包装破损"},
        follow_redirects=False,
    )
    assert checked.status_code == 302

    stocked = client.post(
        f"/admin/inbound/{order['id']}/stock", follow_redirects=False
    )
    assert stocked.status_code == 302
    detail = client.get(f"/admin/inbound/{order['id']}")
    assert "stocked" in detail.text or "已入库" in detail.text


def test_stock_ledger_admin_page(client, auth):
    drug = client.post(
        "/drugs/", json={"name": "台账管理台药", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "LEDGER-B1",
                    "expiry": "2027-12-31",
                    "quantity": 3,
                }
            ],
        },
        headers=auth["warehouse"],
    ).json()
    client.post(f"/inbound/orders/{inbound['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{inbound['id']}/stock", headers=auth["warehouse"])

    client.cookies.clear()
    assert login(client).status_code == 302
    page = client.get("/admin/stock-ledger")
    assert page.status_code == 200
    assert "库存流水台账" in page.text
    assert "LEDGER-B1" in page.text
    filtered = client.get("/admin/stock-ledger?ref_type=inbound&warehouse=总库")
    assert filtered.status_code == 200
    assert "inbound" in filtered.text


def test_warehouse_admin_pages(client, auth):
    # 先造总库库存：入库单
    drug = client.post(
        "/drugs/", json={"name": "库房测试药", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "WH-B1",
                    "expiry": "2027-12-31",
                    "quantity": 10,
                }
            ],
        },
        headers=auth["warehouse"],
    ).json()
    client.post(f"/inbound/orders/{inbound['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{inbound['id']}/stock", headers=auth["warehouse"])

    order = client.post(
        "/warehouse/outbound-orders",
        json={
            "target_type": "pharmacy",
            "target_name": "药房",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "WH-B1",
                    "quantity": 4,
                }
            ],
        },
        headers=auth["pharmacist"],
    ).json()

    client.cookies.clear()
    assert login(client).status_code == 302
    page = client.get("/admin/warehouse")
    assert page.status_code == 200
    assert "库房管理" in page.text
    assert "WH-B1" in page.text
    assert order["outbound_no"] in page.text

    detail = client.get(f"/admin/warehouse/outbound/{order['id']}")
    assert detail.status_code == 200
    assert "审核通过" in detail.text

    approved = client.post(
        f"/admin/warehouse/outbound/{order['id']}/approve", follow_redirects=False
    )
    assert approved.status_code == 302

    item_id = order["items"][0]["id"]
    partial = client.post(
        f"/admin/warehouse/outbound/{order['id']}/issue",
        data={f"qty_{item_id}": "2"},
        follow_redirects=False,
    )
    assert partial.status_code == 302
    detail = client.get(f"/admin/warehouse/outbound/{order['id']}")
    assert "partially_issued" in detail.text

    issued = client.post(
        f"/admin/warehouse/outbound/{order['id']}/issue", follow_redirects=False
    )
    assert issued.status_code == 302

    detail = client.get(f"/admin/warehouse/outbound/{order['id']}")
    assert "issued" in detail.text
    stocks = client.get(f"/pharmacy/stocks?drug_id={drug['id']}").json()
    assert stocks[0]["quantity"] == 4


def test_insurance_catalog_admin_page(client, auth):
    client.cookies.clear()
    assert login(client).status_code == 302

    page = client.get("/admin/insurance-catalog")
    assert page.status_code == 200
    assert "医保药品目录" in page.text

    content = (
        "国家医保药品代码,药品名称,剂型,规格,生产厂家,单位,医保类别\n"
        "XA01ADM001,管理台测试药,片剂,0.1g*10片,演示药业,盒,甲\n"
    ).encode("utf-8")
    imported = client.post(
        "/admin/insurance-catalog/import",
        files={"file": ("catalog.csv", content, "text/csv")},
        follow_redirects=False,
    )
    assert imported.status_code == 302

    page = client.get("/admin/insurance-catalog")
    assert "管理台测试药" in page.text
    assert "V0001" in page.text

