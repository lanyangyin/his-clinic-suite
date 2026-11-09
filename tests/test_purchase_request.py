"""出库缺货 → 采购申请 → 机构审核 → 到货入库 → 原出库单出库。"""
from datetime import date, timedelta


def _setup(client, auth):
    supplier = client.post(
        "/suppliers/",
        json={"code": "PR-SUP", "name": "采购供应商"},
        headers=auth["admin"],
    ).json()
    drug = client.post(
        "/drugs/",
        json={"name": "缺货药品", "base_price": 10.0, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    outbound = client.post(
        "/warehouse/outbound-orders",
        json={
            "target_type": "pharmacy",
            "target_name": "药房",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "PR-BATCH",
                    "quantity": 3,
                }
            ],
        },
        headers=auth["pharmacist"],
    ).json()
    return supplier, drug, outbound


def test_outbound_shortage_purchase_approval_receive(client, auth):
    supplier, drug, outbound = _setup(client, auth)
    request = client.post(
        f"/warehouse/outbound-orders/{outbound['id']}/purchase-request",
        headers=auth["warehouse"],
    )
    assert request.status_code == 201, request.text
    data = request.json()
    assert data["request_no"].startswith("PR")
    assert data["source_type"] == "outbound"
    assert data["source_id"] == outbound["id"]
    assert data["status"] == "submitted"
    assert data["items"][0]["quantity"] == 3

    # 库房自己不能审批
    denied = client.post(
        f"/warehouse/purchase-requests/{data['id']}/approve",
        headers=auth["warehouse"],
    )
    assert denied.status_code == 403

    approved = client.post(
        f"/warehouse/purchase-requests/{data['id']}/approve",
        headers=auth["admin"],
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approver"] == "admin"

    ordered = client.post(
        f"/warehouse/purchase-requests/{data['id']}/order",
        json={"supplier_id": supplier["id"]},
        headers=auth["warehouse"],
    )
    assert ordered.status_code == 200
    assert ordered.json()["status"] == "ordered"

    item_id = approved.json()["items"][0]["id"]
    expiry = (date.today() + timedelta(days=365)).isoformat()
    received = client.post(
        f"/warehouse/purchase-requests/{data['id']}/receive",
        json={
            "supplier_id": supplier["id"],
            "items": [
                {
                    "item_id": item_id,
                    "quantity": 3,
                    "batch_no": "PR-BATCH",
                    "expiry": expiry,
                }
            ],
        },
        headers=auth["warehouse"],
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "received"
    stock = client.get(
        f"/warehouse/stocks?drug_id={drug['id']}", headers=auth["warehouse"]
    ).json()
    assert sum(row["quantity"] for row in stock) == 3

    # 原出库单仍保留，采购到货后正常出库
    approved_outbound = client.post(
        f"/warehouse/outbound-orders/{outbound['id']}/approve",
        headers=auth["warehouse"],
    )
    assert approved_outbound.status_code == 200
    issued = client.post(
        f"/warehouse/outbound-orders/{outbound['id']}/issue",
        headers=auth["warehouse"],
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "issued"


def test_manual_purchase_request_and_reject(client, auth):
    supplier, drug, _ = _setup(client, auth)
    created = client.post(
        "/warehouse/purchase-requests",
        json={
            "department": "库房",
            "supplier_id": supplier["id"],
            "note": "月度补货",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "quantity": 10,
                    "estimated_unit_price": 9.5,
                }
            ],
        },
        headers=auth["warehouse"],
    )
    assert created.status_code == 201
    data = created.json()
    assert data["requester"] == "warehouse"
    assert data["total_amount"] == 95.0

    rejected = client.post(
        f"/warehouse/purchase-requests/{data['id']}/reject",
        json={"reason": "预算不足"},
        headers=auth["admin"],
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejected_reason"] == "预算不足"

    # 已驳回不能再下单
    ordered = client.post(
        f"/warehouse/purchase-requests/{data['id']}/order",
        json={},
        headers=auth["warehouse"],
    )
    assert ordered.status_code == 400


def test_purchase_request_admin_page(client, auth):
    supplier, drug, outbound = _setup(client, auth)
    request = client.post(
        f"/warehouse/outbound-orders/{outbound['id']}/purchase-request",
        headers=auth["warehouse"],
    ).json()
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/purchase-requests")
    assert page.status_code == 200
    assert request["request_no"] in page.text
    detail = client.get(f"/admin/purchase-requests/{request['id']}")
    assert detail.status_code == 200
    assert "机构审核通过" in detail.text
    approved = client.post(
        f"/admin/purchase-requests/{request['id']}/approve",
        follow_redirects=False,
    )
    assert approved.status_code in (302, 303)
    detail = client.get(f"/admin/purchase-requests/{request['id']}")
    assert "已批准" in detail.text


def test_purchase_request_admin_page_lists_supplier(client, auth):
    supplier, drug, outbound = _setup(client, auth)
    request = client.post(
        f"/warehouse/outbound-orders/{outbound['id']}/purchase-request",
        headers=auth["warehouse"],
    ).json()
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    # 未批准时详情页不显示下单，批准后显示供应商选项
    client.post(f"/admin/purchase-requests/{request['id']}/approve", follow_redirects=False)
    detail = client.get(f"/admin/purchase-requests/{request['id']}")
    assert supplier["name"] in detail.text

