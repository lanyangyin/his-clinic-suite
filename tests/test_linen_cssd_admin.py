"""管理台：被服洗涤 / 器械灭菌页面（两条线分开）。"""


def _login_admin(client, auth):
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


def test_linen_admin_page_creates_batch(client, auth):
    _login_admin(client, auth)
    created = client.post(
        "/admin/linen/batches",
        data={
            "category": "uniform",
            "item_name": "医生工作服",
            "quantity": "6",
            "source_department": "门诊",
            "soil_level": "normal",
            "wash_method": "thermal",
            "temperature": "75",
            "duration_min": "30",
            "operator": "洗衣房",
        },
        follow_redirects=False,
    )
    assert created.status_code in (302, 303)
    page = client.get("/admin/linen")
    assert page.status_code == 200
    assert "医生工作服" in page.text
    assert "被服洗涤消毒" in page.text
    assert "器械灭菌" in page.text


def test_cssd_admin_page_creates_set(client, auth):
    _login_admin(client, auth)
    created = client.post(
        "/admin/cssd/sets",
        data={"code": "ADM-SET", "name": "清创包", "department": "门诊"},
        follow_redirects=False,
    )
    assert created.status_code in (302, 303)
    page = client.get("/admin/cssd")
    assert page.status_code == 200
    assert "清创包" in page.text
    assert "器械灭菌" in page.text
    assert "被服洗涤" in page.text
