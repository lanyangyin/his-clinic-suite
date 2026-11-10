"""收费员数据隔离与发票号段。"""
import base64
from datetime import date


def _basic(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _sale(client, auth, suffix):
    dept = client.post(
        "/departments/", json={"name": f"隔离科{suffix}"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": f"隔离医生{suffix}", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/",
        json={"name": f"隔离患者{suffix}", "id_number": f"11010119990101{suffix}"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": f"诊断{suffix}"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": f"隔离药{suffix}", "base_price": 15},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    return encounter


def test_invoice_batch_allocation(client, auth):
    batch = client.post(
        "/invoices/batches",
        json={
            "prefix": "FP",
            "start_no": 1,
            "end_no": 5,
            "assigned_to": "cashier",
            "note": "测试号段",
        },
        headers=auth["admin"],
    )
    assert batch.status_code == 201, batch.text
    assert batch.json()["next_no"] == 1

    encounter = _sale(client, auth, "01")
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    assert payment.status_code in (200, 201)
    body = payment.json()
    assert body["invoice_no"] == "FP00000001"
    assert body["invoice_batch_id"] == batch.json()["id"]

    batch_after = client.get("/invoices/batches", headers=auth["admin"]).json()[0]
    assert batch_after["next_no"] == 2

    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/invoice-batches")
    assert page.status_code == 200
    assert "FP" in page.text


def test_cashier_daily_isolation(client, auth):
    created = client.post(
        "/users/",
        json={
            "username": "cashier2",
            "password": "cashier2pass",
            "role": "cashier",
            "display_name": "收费员二",
        },
        headers=auth["admin"],
    )
    assert created.status_code == 201, created.text
    cashier2 = _basic("cashier2", "cashier2pass")

    encounter1 = _sale(client, auth, "02")
    client.post(
        "/payments/", json={"encounter_id": encounter1["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    encounter2 = _sale(client, auth, "03")
    client.post(
        "/payments/", json={"encounter_id": encounter2["id"], "channel": "cash"},
        headers=cashier2,
    )

    own = client.get("/cashier/daily", headers=auth["cashier"]).json()
    assert own["scope"] == "cashier"
    assert own["payment_count"] >= 1
    assert all(row["channel"] == "cash" for row in own["channels"])

    all_data = client.get("/cashier/daily", headers=auth["admin"]).json()
    assert all_data["scope"] == "all"
    assert all_data["payment_count"] >= own["payment_count"] + 1
    assert len(all_data["channels"]) >= len(own["channels"])
