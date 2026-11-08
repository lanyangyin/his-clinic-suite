def setup_drug_stock(client, auth, quantity=5):
    drug = client.post(
        "/drugs/", json={"name": "追溯码测试药", "base_price": 10.0},
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
                    "batch_no": "TR-B1",
                    "expiry": "2028-12-31",
                    "quantity": quantity,
                }
            ],
        },
        headers=auth["warehouse"],
    ).json()
    client.post(f"/inbound/orders/{inbound['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{inbound['id']}/stock", headers=auth["warehouse"])
    return drug


def scan(client, auth, path, codes, **extra):
    payload = {"codes": codes}
    payload.update(extra)
    return client.post(f"/trace/scan/{path}", json=payload, headers=auth)


def test_trace_inbound_and_validations(client, auth):
    drug = setup_drug_stock(client, auth, 5)
    r = scan(
        client, auth["warehouse"], "inbound",
        ["TR001", "TR002"], drug_id=drug["id"], batch_no="TR-B1",
    )
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] == 2
    assert r.json()["status"] == "in_stock"

    rows = client.get(
        f"/trace/codes?drug_id={drug['id']}&batch_no=TR-B1", headers=auth["warehouse"]
    ).json()
    assert {row["trace_code"] for row in rows} == {"TR001", "TR002"}
    assert all(row["warehouse"] == "总库" and row["status"] == "in_stock" for row in rows)

    duplicate = scan(
        client, auth["warehouse"], "inbound",
        ["TR001"], drug_id=drug["id"], batch_no="TR-B1",
    )
    assert duplicate.status_code == 400
    assert "已存在" in duplicate.json()["detail"]

    over = scan(
        client, auth["warehouse"], "inbound",
        ["TR003", "TR004", "TR005", "TR006"], drug_id=drug["id"], batch_no="TR-B1",
    )
    assert over.status_code == 400
    assert "超过" in over.json()["detail"]

    missing_batch = scan(
        client, auth["warehouse"], "inbound",
        ["TRX"], drug_id=drug["id"], batch_no="NO-BATCH",
    )
    assert missing_batch.status_code == 400

    denied = scan(
        client, auth["pharmacist"], "inbound",
        ["TR010"], drug_id=drug["id"], batch_no="TR-B1",
    )
    assert denied.status_code == 403


def test_trace_outbound_dispense_return(client, auth):
    drug = setup_drug_stock(client, auth, 5)
    scan(client, auth["warehouse"], "inbound", ["TR101", "TR102"], drug_id=drug["id"], batch_no="TR-B1")

    out = scan(client, auth["warehouse"], "outbound", ["TR101", "TR102"])
    assert out.status_code == 200
    codes = client.get("/trace/codes?trace_code=TR101", headers=auth["pharmacist"]).json()
    assert codes[0]["warehouse"] == "药房"

    denied_dispense = scan(client, auth["warehouse"], "dispense", ["TR101"])
    assert denied_dispense.status_code == 403

    # 就诊上下文
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post("/departments/", json={"name": "内科"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/", json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()

    used = scan(
        client, auth["pharmacist"], "dispense", ["TR101", "TR102"],
        encounter_id=encounter["id"],
    )
    assert used.status_code == 200
    assert used.json()["status"] == "used"
    row = client.get("/trace/codes?trace_code=TR101", headers=auth["pharmacist"]).json()[0]
    assert row["status"] == "used"
    assert row["patient_id"] == patient["id"]
    assert row["encounter_id"] == encounter["id"]

    again = scan(client, auth["pharmacist"], "dispense", ["TR101"])
    assert again.status_code == 400

    returned = scan(client, auth["pharmacist"], "return", ["TR101", "TR102"])
    assert returned.status_code == 200
    row = client.get("/trace/codes?trace_code=TR101", headers=auth["pharmacist"]).json()[0]
    assert row["status"] == "in_stock"
    assert row["warehouse"] == "药房"


def test_trace_query_and_summary(client, auth):
    drug = setup_drug_stock(client, auth, 5)
    scan(client, auth["warehouse"], "inbound", ["TR201", "TR202", "TR203"], drug_id=drug["id"], batch_no="TR-B1")
    scan(client, auth["warehouse"], "outbound", ["TR201"])

    summary = client.get(
        f"/trace/codes/summary?drug_id={drug['id']}", headers=auth["warehouse"]
    ).json()
    counts = {(item["status"], item["warehouse"]): item["count"] for item in summary["items"]}
    assert counts[("in_stock", "总库")] == 2
    assert counts[("in_stock", "药房")] == 1
    assert summary["total"] == 3

    page = client.get("/trace/codes?status=in_stock&warehouse=药房", headers=auth["warehouse"]).json()
    assert [row["trace_code"] for row in page] == ["TR201"]

    assert client.get("/trace/codes/NOPE", headers=auth["warehouse"]).status_code == 404
    assert client.get("/trace/codes", headers=auth["cashier"]).status_code == 403

def test_trace_admin_page(client, auth):
    drug = setup_drug_stock(client, auth, 3)
    scan(client, auth["warehouse"], "inbound", ["TRADM1"], drug_id=drug["id"], batch_no="TR-B1")

    client.cookies.clear()
    resp = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    page = client.get("/admin/trace-codes?trace_code=TRADM1")
    assert page.status_code == 200
    assert "药品追溯码" in page.text
    assert "TRADM1" in page.text
