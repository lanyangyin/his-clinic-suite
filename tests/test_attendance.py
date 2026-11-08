from datetime import date

TODAY = date.today().isoformat()
MONTH = TODAY[:7]


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


def check(client, auth, employee_id, check_type="in", day=None):
    payload = {"employee_id": employee_id, "check_type": check_type}
    if day is not None:
        payload["attendance_date"] = day
    return client.post("/hr/attendance/check", json=payload, headers=auth["admin"])


def test_check_in_and_out(client, auth):
    employee = make_employee(client, auth).json()
    r = check(client, auth, employee["id"], "in")
    assert r.status_code == 201
    assert r.json()["check_type"] == "in"

    r = check(client, auth, employee["id"], "out")
    assert r.status_code == 201
    assert r.json()["check_type"] == "out"


def test_duplicate_check_rejected(client, auth):
    employee = make_employee(client, auth).json()
    check(client, auth, employee["id"], "in")
    r = check(client, auth, employee["id"], "in")
    assert r.status_code == 400
    assert r.json()["detail"] == "该员工当日该类型已打卡"


def test_invalid_check_type(client, auth):
    employee = make_employee(client, auth).json()
    r = client.post(
        "/hr/attendance/check",
        json={"employee_id": employee["id"], "check_type": "lunch"},
        headers=auth["admin"],
    )
    assert r.status_code == 422


def test_check_for_resigned_employee(client, auth):
    employee = make_employee(client, auth).json()
    client.post(f"/hr/employees/{employee['id']}/resign", headers=auth["admin"])
    r = check(client, auth, employee["id"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该员工已离职，不能打卡"


def test_check_missing_employee(client, auth):
    r = check(client, auth, 999)
    assert r.status_code == 404


def test_list_attendance(client, auth):
    employee = make_employee(client, auth).json()
    check(client, auth, employee["id"], "in")
    check(client, auth, employee["id"], "out")
    r = client.get(f"/hr/attendance/?employee_id={employee['id']}")
    assert r.status_code == 200
    assert len(r.json()) == 2
    r = client.get(f"/hr/attendance/?employee_id={employee['id']}&attendance_date={TODAY}")
    assert len(r.json()) == 2


def test_monthly_summary(client, auth):
    employee = make_employee(client, auth).json()
    check(client, auth, employee["id"], "in")
    check(client, auth, employee["id"], "out")
    r = client.get(
        f"/hr/attendance/summary?employee_id={employee['id']}&month={MONTH}"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["present_days"] == 1  # 同一天 in/out 只算 1 天
    # 另一天打卡
    check(client, auth, employee["id"], "in", day="2026-11-07")
    r = client.get(
        f"/hr/attendance/summary?employee_id={employee['id']}&month={MONTH}"
    )
    assert r.json()["present_days"] == 2


def test_summary_invalid_month(client, auth):
    employee = make_employee(client, auth).json()
    r = client.get(f"/hr/attendance/summary?employee_id={employee['id']}&month=abc")
    assert r.status_code == 400


def test_role_protection(client, auth):
    employee = make_employee(client, auth).json()
    r = client.post(
        "/hr/attendance/check",
        json={"employee_id": employee["id"], "check_type": "in"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    r = client.post(
        "/hr/attendance/check",
        json={"employee_id": employee["id"], "check_type": "in"},
    )
    assert r.status_code == 401
