def _encounter(client, auth, suffix):
    patient = client.post(
        "/patients/",
        json={"name": f"安全患者{suffix}", "id_number": f"11010119900101{suffix}"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": f"安全科{suffix}"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": f"安全医生{suffix}", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    return client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()


def test_duplicate_ingredient_blocked(client, auth):
    enc = _encounter(client, auth, "101")
    first = client.post(
        "/drugs/",
        json={"name": "复方甲", "base_price": 1, "ingredient": "对乙酰氨基酚"},
        headers=auth["admin"],
    ).json()
    second = client.post(
        "/drugs/",
        json={"name": "复方乙", "base_price": 1, "ingredient": "对乙酰氨基酚"},
        headers=auth["admin"],
    ).json()
    assert client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": first["id"], "quantity": 1},
        headers=auth["doctor"],
    ).status_code == 201
    blocked = client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": second["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert blocked.status_code == 400
    assert "成分重复" in blocked.json()["detail"]


def test_configured_interaction_blocked(client, auth):
    enc = _encounter(client, auth, "102")
    first = client.post(
        "/drugs/",
        json={"name": "华法林", "base_price": 1, "ingredient": "华法林"},
        headers=auth["admin"],
    ).json()
    second = client.post(
        "/drugs/",
        json={"name": "阿司匹林", "base_price": 1, "ingredient": "阿司匹林"},
        headers=auth["admin"],
    ).json()
    rule = client.post(
        "/drugs/interactions",
        json={
            "drug_a_id": first["id"],
            "drug_b_id": second["id"],
            "severity": "block",
            "note": "出血风险增加",
        },
        headers=auth["admin"],
    )
    assert rule.status_code == 201, rule.text
    assert client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": first["id"], "quantity": 1},
        headers=auth["doctor"],
    ).status_code == 201
    blocked = client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": second["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert blocked.status_code == 400
    assert "相互作用" in blocked.json()["detail"]


def test_interaction_admin_page(client, auth):
    first = client.post(
        "/drugs/", json={"name": "规则药A", "base_price": 1}, headers=auth["admin"]
    ).json()
    second = client.post(
        "/drugs/", json={"name": "规则药B", "base_price": 1}, headers=auth["admin"]
    ).json()
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    response = client.post(
        "/admin/drug-interactions",
        data={
            "drug_a_id": first["id"],
            "drug_b_id": second["id"],
            "severity": "block",
            "note": "测试规则",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    page = client.get("/admin/drug-interactions")
    assert page.status_code == 200
    assert "规则药A" in page.text
    assert "测试规则" in page.text


def test_drug_barcode_lookup(client, auth):
    drug = client.post(
        "/drugs/",
        json={"name": "条码药", "base_price": 2, "barcode": "690000000001"},
        headers=auth["admin"],
    ).json()
    found = client.get("/drugs/by-barcode/690000000001")
    assert found.status_code == 200
    assert found.json()["id"] == drug["id"]
    assert client.get("/drugs/by-barcode/NO-SUCH").status_code == 404
