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


def test_lab_item_admin_page(client, auth):
    _login_admin(client, auth)
    created = client.post(
        "/admin/lab-items",
        data={
            "code": "ADM-WBC",
            "name": "管理台白细胞",
            "price": "12",
            "specimen_type": "血液",
            "unit": "10^9/L",
            "reference_low": "4",
            "reference_high": "10",
            "tat_minutes": "30",
            "insurance_ratio": "0.8",
        },
        follow_redirects=False,
    )
    assert created.status_code in (302, 303)
    page = client.get("/admin/lab-items")
    assert page.status_code == 200
    assert "管理台白细胞" in page.text


def test_archive_admin_page_creates_record(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "管理台档案患者", "id_number": "110101197001019999"},
        headers=auth["cashier"],
    ).json()
    _login_admin(client, auth)
    created = client.post(
        "/admin/archive/records",
        data={"patient_id": patient["id"], "record_type": "outpatient", "note": "管理台建档"},
        follow_redirects=False,
    )
    assert created.status_code in (302, 303)
    page = client.get("/admin/archive")
    assert page.status_code == 200
    assert "管理台档案患者" in page.text
    assert "病案档案" in page.text
