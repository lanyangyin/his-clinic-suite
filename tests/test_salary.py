def make_employee(client, auth, no="EMP001", name="张医生"):
    return client.post(
        "/hr/employees/",
        json={
            "employee_no": no,
            "name": name,
            "role": "doctor",
            "hired_at": "2024-03-01",
        },
        headers=auth["admin"],
    )


def make_request(client, auth, employee_id, month="2026-11", base=8000.0, bonus=1500.0):
    return client.post(
        "/hr/salary-requests",
        json={
            "employee_id": employee_id,
            "month": month,
            "base_amount": base,
            "bonus_amount": bonus,
        },
        headers=auth["admin"],
    )


def test_create_salary_request(client, auth):
    employee = make_employee(client, auth).json()
    r = make_request(client, auth, employee["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["total_amount"] == 9500.0
    assert body["requested_by"] == "admin"
    assert body["employee_name"] == "张医生"


def test_duplicate_month_rejected(client, auth):
    employee = make_employee(client, auth).json()
    make_request(client, auth, employee["id"])
    r = make_request(client, auth, employee["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该员工该月已有薪资申请"


def test_salary_for_missing_employee(client, auth):
    r = make_request(client, auth, 999)
    assert r.status_code == 404


def test_salary_for_resigned_employee(client, auth):
    employee = make_employee(client, auth).json()
    client.post(f"/hr/employees/{employee['id']}/resign", headers=auth["admin"])
    r = make_request(client, auth, employee["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该员工已离职"


def test_invalid_month_format(client, auth):
    employee = make_employee(client, auth).json()
    r = make_request(client, auth, employee["id"], month="2026-13")
    assert r.status_code == 422


def test_approve_salary_request(client, auth):
    employee = make_employee(client, auth).json()
    request = make_request(client, auth, employee["id"]).json()
    r = client.post(
        f"/hr/salary-requests/{request['id']}/approve", headers=auth["admin"]
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["reviewed_by"] == "admin"
    assert body["reviewed_at"] is not None

    # 重复批准
    again = client.post(
        f"/hr/salary-requests/{request['id']}/approve", headers=auth["admin"]
    )
    assert again.status_code == 400
    assert again.json()["detail"] == "该薪资申请已处理"


def test_reject_salary_request(client, auth):
    employee = make_employee(client, auth).json()
    request = make_request(client, auth, employee["id"]).json()
    r = client.post(
        f"/hr/salary-requests/{request['id']}/reject",
        json={"note": "绩效数据待复核"},
        headers=auth["admin"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert body["review_note"] == "绩效数据待复核"

    # 已驳回不能再批准
    again = client.post(
        f"/hr/salary-requests/{request['id']}/approve", headers=auth["admin"]
    )
    assert again.status_code == 400


def test_list_and_filters(client, auth):
    employee = make_employee(client, auth).json()
    make_request(client, auth, employee["id"], month="2026-10")
    make_request(client, auth, employee["id"], month="2026-11")
    rows = client.get(f"/hr/salary-requests?employee_id={employee['id']}").json()
    assert len(rows) == 2
    month_rows = client.get(f"/hr/salary-requests?month=2026-11").json()
    assert len(month_rows) == 1
    pending = client.get("/hr/salary-requests?status=pending").json()
    assert len(pending) == 2


def test_get_missing_salary_request(client):
    assert client.get("/hr/salary-requests/999").status_code == 404


def test_role_protection(client, auth):
    employee = make_employee(client, auth).json()
    # 医生不能发起申请
    r = client.post(
        "/hr/salary-requests",
        json={"employee_id": employee["id"], "month": "2026-11", "base_amount": 100},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    # 未登录不能批准
    request = make_request(client, auth, employee["id"]).json()
    r = client.post(f"/hr/salary-requests/{request['id']}/approve")
    assert r.status_code == 401
