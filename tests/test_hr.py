def make_employee(client, auth, no="EMP001", name="张医生", role="doctor"):
    return client.post(
        "/hr/employees/",
        json={
            "employee_no": no,
            "name": name,
            "role": role,
            "phone": "13800000000",
            "hired_at": "2024-03-01",
        },
        headers=auth["admin"],
    )


def test_create_employee(client, auth):
    r = make_employee(client, auth)
    assert r.status_code == 201
    body = r.json()
    assert body["employee_no"] == "EMP001"
    assert body["status"] == "active"
    assert body["hired_at"] == "2024-03-01"


def test_duplicate_employee_no_rejected(client, auth):
    make_employee(client, auth)
    r = make_employee(client, auth, name="李护士", role="nurse")
    assert r.status_code == 400
    assert r.json()["detail"] == "工号已存在"


def test_resign_employee(client, auth):
    employee = make_employee(client, auth).json()
    r = client.post(f"/hr/employees/{employee['id']}/resign", headers=auth["admin"])
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resigned"
    assert body["resigned_at"] is not None


def test_resign_twice_rejected(client, auth):
    employee = make_employee(client, auth).json()
    client.post(f"/hr/employees/{employee['id']}/resign", headers=auth["admin"])
    r = client.post(f"/hr/employees/{employee['id']}/resign", headers=auth["admin"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该员工已离职"


def test_resign_missing_employee(client, auth):
    r = client.post("/hr/employees/999/resign", headers=auth["admin"])
    assert r.status_code == 404


def test_list_and_filters(client, auth):
    make_employee(client, auth, no="E1", name="医生A", role="doctor")
    employee_b = make_employee(client, auth, no="E2", name="护士B", role="nurse").json()
    client.post(f"/hr/employees/{employee_b['id']}/resign", headers=auth["admin"])

    all_rows = client.get("/hr/employees/").json()
    assert len(all_rows) == 2

    active = client.get("/hr/employees/?status=active").json()
    assert len(active) == 1
    assert active[0]["name"] == "医生A"

    resigned = client.get("/hr/employees/?status=resigned").json()
    assert len(resigned) == 1
    assert resigned[0]["name"] == "护士B"


def test_list_filter_by_department(client, auth):
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    client.post(
        "/hr/employees/",
        json={
            "employee_no": "E3",
            "name": "医生C",
            "role": "doctor",
            "department_id": department["id"],
            "hired_at": "2025-01-01",
        },
        headers=auth["admin"],
    )
    rows = client.get(f"/hr/employees/?department_id={department['id']}").json()
    assert len(rows) == 1
    assert rows[0]["department_id"] == department["id"]


def test_get_missing_employee(client):
    assert client.get("/hr/employees/999").status_code == 404


def test_role_protection(client, auth):
    # 医生不能建员工档案
    r = make_employee(client, auth)
    assert r.status_code == 201
    r = client.post(
        "/hr/employees/",
        json={"employee_no": "E9", "name": "X", "role": "doctor", "hired_at": "2025-01-01"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    # 未登录不能离职
    employee = make_employee(client, auth, no="E8", name="Y").json()
    r = client.post(f"/hr/employees/{employee['id']}/resign")
    assert r.status_code == 401
