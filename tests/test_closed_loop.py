def test_full_closed_loop(client, auth):
    """建档 -> 挂号 -> 接诊 -> 开方 -> 收费 -> 入库 -> 发药 全链路（多角色）。"""
    # 建档（收费员）
    patient = client.post(
        "/patients/",
        json={"name": "赵六", "id_number": "110101199701011234"},
        headers=auth["cashier"],
    ).json()
    # 科室与医生（管理员）
    department = client.post(
        "/departments/", json={"name": "耳鼻喉科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "陈医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    # 挂号（收费员）
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    assert reg["status"] == "registered"
    # 接诊（医生）：挂号状态流转为 visited
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "急性扁桃体炎"},
        headers=auth["doctor"],
    ).json()
    assert client.get(f"/registrations/{reg['id']}").json()["status"] == "visited"
    # 药品主数据（管理员）
    drug_a = client.post(
        "/drugs/", json={"name": "头孢克肟胶囊", "base_price": 22.0}, headers=auth["admin"]
    ).json()
    drug_b = client.post(
        "/drugs/", json={"name": "蒲地蓝口服液", "base_price": 15.5}, headers=auth["admin"]
    ).json()
    # 开方（医生）
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug_a["id"], "quantity": 3},
        headers=auth["doctor"],
    )
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug_b["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    items = client.get(f"/encounters/{encounter['id']}/prescriptions").json()
    assert len(items) == 2
    # 收费（收费员）：3*22 + 2*15.5 = 97.0，收费后就诊关闭
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    assert payment["amount"] == 97.0
    assert payment["status"] == "paid"
    assert client.get(f"/encounters/{encounter['id']}").json()["status"] == "closed"
    # 入库（药师，两个批次）
    stock_a1 = client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug_a["id"], "batch_no": "A001", "expiry": "2027-06-30", "quantity": 10},
        headers=auth["pharmacist"],
    ).json()
    stock_a2 = client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug_a["id"], "batch_no": "A002", "expiry": "2028-06-30", "quantity": 100},
        headers=auth["pharmacist"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug_b["id"], "batch_no": "B001", "expiry": "2027-06-30", "quantity": 2},
        headers=auth["pharmacist"],
    )
    # 发药（药师）：头孢 3 先扣近效期批次 A001（10→7）
    dispense = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    ).json()
    assert dispense["encounter_id"] == encounter["id"]
    assert client.get(f"/pharmacy/stocks/{stock_a1['id']}").json()["quantity"] == 7
    assert client.get(f"/pharmacy/stocks/{stock_a2['id']}").json()["quantity"] == 100


def test_full_loop_audit_logged(client, auth):
    """闭环过程中每个写操作都应留下审计日志。"""
    patient = client.post(
        "/patients/",
        json={"name": "赵六", "id_number": "110101199701011234"},
        headers=auth["cashier"],
    )
    assert patient.status_code == 201
    logs = client.get("/audit/logs").json()
    entries = [(l["username"], l["role"], l["path"], l["status_code"]) for l in logs]
    assert ("cashier", "cashier", "/patients/", 201) in entries
