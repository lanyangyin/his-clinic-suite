def test_drug_proposal_two_stage_approval(client, auth):
    proposal = client.post(
        "/catalog-proposals/",
        json={
            "kind": "drug",
            "name": "新药审批药",
            "spec": "0.5g",
            "unit": "盒",
            "price": 18.5,
            "reason": "门诊需要",
        },
        headers=auth["doctor"],
    )
    assert proposal.status_code == 201, proposal.text
    proposal = proposal.json()
    assert proposal["status"] == "pending_pharmacy"

    mine = client.get("/catalog-proposals/mine", headers=auth["doctor"])
    assert any(row["id"] == proposal["id"] for row in mine.json())

    pharmacy = client.get("/catalog-proposals/", headers=auth["pharmacist"])
    assert any(row["id"] == proposal["id"] for row in pharmacy.json())
    approved = client.post(
        f"/catalog-proposals/{proposal['id']}/review",
        json={"approve": True, "note": "药事同意"},
        headers=auth["pharmacist"],
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "pending_warehouse"

    warehouse = client.get("/catalog-proposals/", headers=auth["warehouse"])
    assert any(row["id"] == proposal["id"] for row in warehouse.json())
    final = client.post(
        f"/catalog-proposals/{proposal['id']}/review",
        json={"approve": True, "note": "库房同意"},
        headers=auth["warehouse"],
    )
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "approved"
    assert final.json()["created_object_id"]

    drugs = client.get("/drugs/", params={"name": "新药审批药"}).json()
    assert any(row["name"] == "新药审批药" for row in drugs)


def test_treatment_proposal_director_approval(client, auth):
    proposal = client.post(
        "/catalog-proposals/",
        json={
            "kind": "treatment",
            "name": "新治疗项目",
            "unit": "次",
            "price": 66,
            "reason": "新技术",
        },
        headers=auth["doctor"],
    )
    assert proposal.status_code == 201, proposal.text
    proposal = proposal.json()
    assert proposal["status"] == "pending_director"

    approved = client.post(
        f"/catalog-proposals/{proposal['id']}/review",
        json={"approve": True, "note": "院长同意"},
        headers=auth["director"],
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    items = client.get("/charges/items/", params={"category": "treatment"}).json()
    assert any(row["name"] == "新治疗项目" for row in items)


def test_proposal_reject_and_permission(client, auth):
    proposal = client.post(
        "/catalog-proposals/",
        json={"kind": "drug", "name": "驳回新药", "price": 1},
        headers=auth["doctor"],
    ).json()
    denied = client.post(
        f"/catalog-proposals/{proposal['id']}/review",
        json={"approve": True},
        headers=auth["doctor"],
    )
    assert denied.status_code == 403
    rejected = client.post(
        f"/catalog-proposals/{proposal['id']}/review",
        json={"approve": False, "note": "已有同类药"},
        headers=auth["pharmacist"],
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
