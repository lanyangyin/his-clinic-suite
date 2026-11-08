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
