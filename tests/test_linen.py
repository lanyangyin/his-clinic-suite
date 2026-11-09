"""被服洗涤消毒：批次/发放/召回/窗帘。与器械灭菌分开。"""


def test_linen_batch_distribute_recall_and_summary(client, auth):
    created = client.post(
        "/linen/batches",
        json={
            "category": "bedding",
            "item_name": "床单被套",
            "quantity": 10,
            "source_department": "病房",
            "soil_level": "normal",
            "wash_method": "thermal",
            "temperature": 75,
            "duration_min": 30,
            "operator": "洗衣房",
        },
        headers=auth["nurse"],
    )
    assert created.status_code == 201, created.text
    batch = created.json()
    assert batch["batch_no"].startswith("LIN")
    assert batch["remaining_quantity"] == 10

    distributed = client.post(
        f"/linen/batches/{batch['id']}/distribute",
        json={"department": "门诊", "quantity": 4},
        headers=auth["nurse"],
    )
    assert distributed.status_code == 201
    detail = client.get(f"/linen/batches/{batch['id']}", headers=auth["nurse"]).json()
    assert detail["distributed_quantity"] == 4
    assert detail["remaining_quantity"] == 6

    too_many = client.post(
        f"/linen/batches/{batch['id']}/distribute",
        json={"department": "门诊", "quantity": 99},
        headers=auth["nurse"],
    )
    assert too_many.status_code == 400
    assert "剩余数量" in too_many.json()["detail"]

    recalled = client.post(
        f"/linen/batches/{batch['id']}/recall",
        json={"reason": "洗涤温度记录异常"},
        headers=auth["nurse"],
    )
    assert recalled.status_code == 200
    assert recalled.json()["status"] == "recalled"

    blocked = client.post(
        f"/linen/batches/{batch['id']}/distribute",
        json={"department": "门诊", "quantity": 1},
        headers=auth["nurse"],
    )
    assert blocked.status_code == 400
    assert "召回" in blocked.json()["detail"]

    summary = client.get(
        "/linen/summary",
        params={"start_date": "2000-01-01", "end_date": "2100-01-01"},
        headers=auth["nurse"],
    ).json()
    assert summary["batch_count"] == 1
    assert summary["total_quantity"] == 10
    assert summary["recalled_count"] == 1
    assert summary["by_category"]["bedding"] == 10


def test_linen_curtain_records_and_reminders(client, auth):
    from datetime import date, timedelta

    due = (date.today() + timedelta(days=10)).isoformat()
    created = client.post(
        "/linen/curtains",
        json={
            "department": "门诊",
            "room": "诊室 3",
            "curtain_no": "CUR-001",
            "event": "reinstall",
            "method": "清洗消毒后安装",
            "operator": "保洁",
            "next_due": due,
        },
        headers=auth["nurse"],
    )
    assert created.status_code == 201
    reminders = client.get(
        "/linen/curtains/reminders", params={"days": 30}, headers=auth["nurse"]
    ).json()
    assert any(row["curtain_no"] == "CUR-001" for row in reminders)


def test_linen_requires_staff_role(client, auth):
    response = client.post(
        "/linen/batches",
        json={"item_name": "工作服", "quantity": 1},
        headers=auth["cashier"],
    )
    assert response.status_code == 403
