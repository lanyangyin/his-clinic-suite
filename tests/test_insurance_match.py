def import_catalog(client, auth, rows):
    content = (
        "国家医保药品代码,药品名称,剂型,规格,生产厂家,单位,医保类别\n"
        + "\n".join(rows)
    ).encode("utf-8")
    r = client.post(
        "/insurance/catalog/import",
        files={"file": ("match.csv", content, "text/csv")},
        headers=auth["admin"],
    )
    assert r.status_code == 200, r.text
    return r.json()


def make_drug(client, auth, **kwargs):
    payload = {"name": "对码测试药", "base_price": 10.0, "insurance_ratio": 0.7}
    payload.update(kwargs)
    return client.post("/drugs/", json=payload, headers=auth["admin"]).json()


def make_encounter(client, auth):
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    return client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()


def prescribe_and_pay(client, auth, drug_id, quantity=2):
    encounter = make_encounter(client, auth)
    item = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug_id, "quantity": quantity},
        headers=auth["doctor"],
    ).json()
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    return item, payment


def test_match_by_code_and_jia_class(client, auth):
    import_catalog(
        client,
        auth,
        ["MAT001,对码药,片剂,0.1g*10片,演示药业,盒,甲"],
    )
    drug = make_drug(
        client,
        auth,
        name="对码药",
        spec="0.1g*10片",
        dosage_form="片剂",
        insurance_code="MAT001",
    )
    stats = client.post("/insurance/catalog/match", headers=auth["admin"]).json()
    assert stats["matched"] >= 1

    matches = client.get("/insurance/catalog/matches", headers=auth["admin"]).json()
    row = next(m for m in matches if m["drug_id"] == drug["id"])
    assert row["insurance_match_status"] == "matched"
    assert row["insurance_category"] == "甲"
    assert row["catalog_name"] == "对码药"

    resolved = client.get(
        f"/insurance/catalog/resolve/{drug['id']}", headers=auth["admin"]
    ).json()
    assert resolved["category"] == "甲"
    assert resolved["ratio"] == 1.0

    item, payment = prescribe_and_pay(client, auth, drug["id"], quantity=2)
    assert item["insurance_category"] == "甲"
    assert "甲类" in (item["insurance_warning"] or "")
    assert payment["insurance_amount"] == 20.0
    assert payment["self_pay_amount"] == 0.0


def test_match_by_name_form_spec_yi_class(client, auth):
    import_catalog(
        client,
        auth,
        ["MAT002,名称匹配药,胶囊剂,0.25g*12粒,演示药业,盒,乙"],
    )
    drug = make_drug(
        client,
        auth,
        name="名称匹配药",
        spec="0.25g*12粒",
        dosage_form="胶囊剂",
        insurance_ratio=0.6,
    )
    client.post("/insurance/catalog/match", headers=auth["admin"])

    matches = client.get("/insurance/catalog/matches", headers=auth["admin"]).json()
    row = next(m for m in matches if m["drug_id"] == drug["id"])
    assert row["insurance_match_status"] == "matched"
    assert row["insurance_category"] == "乙"
    assert row["insurance_code"] == "MAT002"

    resolved = client.get(
        f"/insurance/catalog/resolve/{drug['id']}", headers=auth["admin"]
    ).json()
    assert resolved["category"] == "乙"
    assert resolved["ratio"] == 0.6

    item, payment = prescribe_and_pay(client, auth, drug["id"], quantity=2)
    assert item["insurance_category"] == "乙"
    assert "乙类" in (item["insurance_warning"] or "")
    assert payment["insurance_amount"] == 12.0  # 20 * 0.6


def test_bing_class_is_self_pay(client, auth):
    import_catalog(
        client,
        auth,
        ["MAT003,丙类药,片剂,5mg*20片,演示药业,盒,丙"],
    )
    drug = make_drug(
        client, auth, name="丙类药", spec="5mg*20片", dosage_form="片剂"
    )
    client.post("/insurance/catalog/match", headers=auth["admin"])

    resolved = client.get(
        f"/insurance/catalog/resolve/{drug['id']}", headers=auth["admin"]
    ).json()
    assert resolved["category"] == "丙"
    assert resolved["ratio"] == 0.0

    item, payment = prescribe_and_pay(client, auth, drug["id"], quantity=2)
    assert item["insurance_category"] == "丙"
    assert "丙类" in (item["insurance_warning"] or "")
    assert payment["insurance_amount"] == 0.0
    assert payment["self_pay_amount"] == 20.0


def test_coded_but_unmatched_is_self_pay(client, auth):
    drug = make_drug(
        client, auth, name="未匹配药", insurance_code="NOT-IN-CATALOG"
    )
    resolved = client.get(
        f"/insurance/catalog/resolve/{drug['id']}", headers=auth["admin"]
    ).json()
    assert resolved["ratio"] == 0.0
    assert "自费" in (resolved["warning"] or "")

    item, payment = prescribe_and_pay(client, auth, drug["id"], quantity=2)
    assert "自费" in (item["insurance_warning"] or "")
    assert payment["insurance_amount"] == 0.0


def test_ambiguous_match(client, auth):
    import_catalog(
        client,
        auth,
        [
            "AMB001,歧义药,片剂,1g*10片,厂家甲,盒,甲",
            "AMB002,歧义药,片剂,1g*10片,厂家乙,盒,乙",
        ],
    )
    drug = make_drug(
        client, auth, name="歧义药", spec="1g*10片", dosage_form="片剂"
    )
    client.post("/insurance/catalog/match", headers=auth["admin"])
    matches = client.get("/insurance/catalog/matches", headers=auth["admin"]).json()
    row = next(m for m in matches if m["drug_id"] == drug["id"])
    assert row["insurance_match_status"] == "ambiguous"
    assert row["insurance_category"] == ""


def test_insurance_match_admin_page(client, auth):
    import_catalog(client, auth, ["PAGE001,页面匹配药,片剂,2mg*10片,演示药业,盒,甲"])
    make_drug(
        client,
        auth,
        name="页面匹配药",
        spec="2mg*10片",
        dosage_form="片剂",
    )
    client.cookies.clear()
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/insurance-catalog")
    assert page.status_code == 200
    assert "药品对码" in page.text
    assert "自动对码" in page.text
    matched = client.post("/admin/insurance-catalog/match", follow_redirects=False)
    assert matched.status_code == 302
    page = client.get("/admin/insurance-catalog")
    assert "已匹配" in page.text
