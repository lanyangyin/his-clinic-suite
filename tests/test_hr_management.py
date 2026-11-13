def test_hr_can_soft_delete_doctor_and_department(client, auth):
    dept = client.post(
        "/departments/", json={"name": "人事测试科"}, headers=auth["hr"]
    )
    assert dept.status_code == 201, dept.text
    dept = dept.json()
    doctor = client.post(
        "/doctors/",
        json={"name": "人事测试医生", "department_id": dept["id"]},
        headers=auth["hr"],
    )
    assert doctor.status_code == 201, doctor.text
    doctor = doctor.json()

    blocked = client.delete(f"/departments/{dept['id']}", headers=auth["hr"])
    assert blocked.status_code == 400
    assert "医生" in blocked.json()["detail"]

    dismissed = client.delete(f"/doctors/{doctor['id']}", headers=auth["hr"])
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["active"] is False

    active_doctors = client.get("/doctors/").json()
    assert all(row["id"] != doctor["id"] for row in active_doctors)
    all_doctors = client.get(
        "/doctors/", params={"include_inactive": "true"}
    ).json()
    assert any(row["id"] == doctor["id"] and not row["active"] for row in all_doctors)

    deleted = client.delete(f"/departments/{dept['id']}", headers=auth["hr"])
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["active"] is False


def test_hr_can_create_employee_and_login_account(client, auth):
    employee = client.post(
        "/hr/employees/",
        json={
            "employee_no": "HR0001",
            "name": "人事员工",
            "department_id": None,
            "role": "doctor",
            "phone": "13800000002",
            "email": "",
            "hired_at": "2026-11-14",
        },
        headers=auth["hr"],
    )
    assert employee.status_code == 201, employee.text
    employee = employee.json()

    account = client.post(
        "/users/",
        json={
            "username": "hr_created_doctor",
            "password": "pw123456",
            "role": "doctor",
            "display_name": "人事员工",
            "employee_id": employee["id"],
        },
        headers=auth["hr"],
    )
    assert account.status_code == 201, account.text
    assert account.json()["employee_id"] == employee["id"]

    users = client.get("/users/", headers=auth["hr"])
    assert users.status_code == 200
    assert any(row["username"] == "hr_created_doctor" for row in users.json())

    denied = client.post(
        "/users/",
        json={"username": "bad", "password": "pw123456", "role": "doctor"},
        headers=auth["cashier"],
    )
    assert denied.status_code == 403

    forbidden = client.post(
        "/users/",
        json={"username": "hr_admin", "password": "pw123456", "role": "admin"},
        headers=auth["hr"],
    )
    assert forbidden.status_code == 403
