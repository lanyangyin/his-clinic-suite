def make_employee(client, auth, no="EMP001", name="张医生"):
    return client.post(
        "/hr/employees/",
        json={"employee_no": no, "name": name, "role": "doctor", "hired_at": "2024-03-01"},
        headers=auth["admin"],
    )


def make_shift(client, auth, employee_id, day="2026-11-10", shift_type="morning"):
    return client.post(
        "/hr/shifts",
        json={"employee_id": employee_id, "shift_date": day, "shift_type": shift_type},
        headers=auth["admin"],
    )


def test_create_shift(client, auth):
    employee = make_employee(client, auth).json()
    r = make_shift(client, auth, employee["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["shift_type"] == "morning"
    assert body["employee_name"] == "张医生"
    assert body["shift_date"] == "2026-11-10"


def test_duplicate_shift_rejected(client, auth):
    employee = make_employee(client, auth).json()
    make_shift(client, auth, employee["id"])
    r = make_shift(client, auth, employee["id"], shift_type="night")
    assert r.status_code == 400
    assert r.json()["detail"] == "该员工当日已有排班"


def test_shift_invalid_type(client, auth):
    employee = make_employee(client, auth).json()
    r = make_shift(client, auth, employee["id"], shift_type="weekend")
    assert r.status_code == 422


def test_shift_for_resigned_employee(client, auth):
    employee = make_employee(client, auth).json()
    client.post(f"/hr/employees/{employee['id']}/resign", headers=auth["admin"])
    r = make_shift(client, auth, employee["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该员工已离职，不能排班"


def test_shift_missing_employee(client, auth):
    r = make_shift(client, auth, 999)
    assert r.status_code == 404


def test_list_shifts_with_filters(client, auth):
    employee = make_employee(client, auth).json()
    for day in ("2026-11-10", "2026-11-11", "2026-11-12"):
        make_shift(client, auth, employee["id"], day=day)
    rows = client.get(f"/hr/shifts?employee_id={employee['id']}").json()
    assert len(rows) == 3
    ranged = client.get(
        f"/hr/shifts?employee_id={employee['id']}&start_date=2026-11-11&end_date=2026-11-12"
    ).json()
    assert [row["shift_date"] for row in ranged] == ["2026-11-11", "2026-11-12"]


def test_delete_shift(client, auth):
    employee = make_employee(client, auth).json()
    shift = make_shift(client, auth, employee["id"]).json()
    r = client.delete(f"/hr/shifts/{shift['id']}", headers=auth["admin"])
    assert r.status_code == 204
    assert client.get(f"/hr/shifts?employee_id={employee['id']}").json() == []
    # 再删 → 404
    r = client.delete(f"/hr/shifts/{shift['id']}", headers=auth["admin"])
    assert r.status_code == 404


def test_role_protection(client, auth):
    employee = make_employee(client, auth).json()
    r = client.post(
        "/hr/shifts",
        json={"employee_id": employee["id"], "shift_date": "2026-11-10", "shift_type": "morning"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    r = client.post(
        "/hr/shifts",
        json={"employee_id": employee["id"], "shift_date": "2026-11-10", "shift_type": "morning"},
    )
    assert r.status_code == 401
