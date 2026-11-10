def _archive_record(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "销毁审批患者", "id_number": "110101199001011111"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "销毁审批科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "销毁审批医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    record = client.post(
        "/archive/records",
        json={"patient_id": patient["id"], "encounter_id": enc["id"]},
        headers=auth["archive"],
    ).json()
    archived = client.post(
        f"/archive/records/{record['id']}/archive",
        json={"storage_location": "D-01", "page_count": 10, "completeness": "complete"},
        headers=auth["archive"],
    )
    assert archived.status_code == 200
    return record


def test_archive_destruction_requires_director_and_execution(client, auth):
    record = _archive_record(client, auth)
    requested = client.post(
        f"/archive/records/{record['id']}/destruction-requests",
        json={"reason": "保存期满", "note": "销毁清册 2026-001"},
        headers=auth["archive"],
    )
    assert requested.status_code == 201, requested.text
    request_id = requested.json()["id"]
    assert requested.json()["status"] == "pending"

    attachment = client.post(
        f"/archive/destruction-requests/{request_id}/attachment",
        files={"file": ("清册.pdf", b"%PDF-1.4 demo", "application/pdf")},
        headers=auth["archive"],
    )
    assert attachment.status_code == 200, attachment.text
    assert attachment.json()["attachment_name"] == "清册.pdf"
    download = client.get(
        f"/archive/destruction-requests/{request_id}/attachment",
        headers=auth["director"],
    )
    assert download.status_code == 200

    denied = client.post(
        f"/archive/destruction-requests/{request_id}/approve",
        json={"note": "同意"},
        headers=auth["archive"],
    )
    assert denied.status_code == 403

    approved = client.post(
        f"/archive/destruction-requests/{request_id}/approve",
        json={"note": "同意销毁"},
        headers=auth["director"],
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approver"] == "director"

    self_witness = client.post(
        f"/archive/destruction-requests/{request_id}/execute",
        json={"witness": "archive"},
        headers=auth["archive"],
    )
    assert self_witness.status_code == 400

    executed = client.post(
        f"/archive/destruction-requests/{request_id}/execute",
        json={"witness": "医务科"},
        headers=auth["archive"],
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "executed"
    printed = client.get(
        f"/archive/destruction-requests/{request_id}/print",
        headers=auth["director"],
    )
    assert printed.status_code == 200
    assert "病案销毁清册" in printed.text
    assert "清册.pdf" in printed.text
    assert (
        client.get(
            f"/archive/records/{record['id']}", headers=auth["archive"]
        ).json()["status"]
        == "destroyed"
    )


def test_director_can_reject_archive_destruction(client, auth):
    record = _archive_record(client, auth)
    requested = client.post(
        f"/archive/records/{record['id']}/destruction-requests",
        json={"reason": "重复病案"},
        headers=auth["archive"],
    ).json()
    rejected = client.post(
        f"/archive/destruction-requests/{requested['id']}/reject",
        json={"note": "材料不齐"},
        headers=auth["director"],
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_director_can_approve_purchase_request(client, auth):
    supplier = client.post(
        "/suppliers/",
        json={"code": "DIR-SUP", "name": "院长审批供应商"},
        headers=auth["admin"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "院长审批药", "base_price": 10},
        headers=auth["admin"],
    ).json()
    request = client.post(
        "/warehouse/purchase-requests",
        json={
            "department": "库房",
            "supplier_id": supplier["id"],
            "note": "院长审批测试",
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
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]

    listed = client.get(
        "/warehouse/purchase-requests", headers=auth["director"]
    )
    assert listed.status_code == 200
    assert any(row["id"] == request_id for row in listed.json())

    denied = client.post(
        f"/warehouse/purchase-requests/{request_id}/approve",
        headers=auth["warehouse"],
    )
    assert denied.status_code == 403

    approved = client.post(
        f"/warehouse/purchase-requests/{request_id}/approve",
        headers=auth["director"],
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approver"] == "director"


def test_rejected_destruction_can_be_reapplied(client, auth):
    record = _archive_record(client, auth)
    first = client.post(
        f"/archive/records/{record['id']}/destruction-requests",
        json={"reason": "保存期满"},
        headers=auth["archive"],
    ).json()
    client.post(
        f"/archive/destruction-requests/{first['id']}/reject",
        json={"note": "材料不齐"},
        headers=auth["director"],
    )
    again = client.post(
        f"/archive/records/{record['id']}/destruction-requests",
        json={"reason": "补齐材料后重新申请"},
        headers=auth["archive"],
    )
    assert again.status_code == 201, again.text
    assert again.json()["status"] == "pending"
