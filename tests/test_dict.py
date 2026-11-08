def make_entry(client, auth, dict_type="blood_type", code="A", name="A型", sort_order=1):
    return client.post(
        f"/dict/{dict_type}/entries",
        json={"code": code, "name": name, "sort_order": sort_order},
        headers=auth["admin"],
    )


def test_create_entry(client, auth):
    r = make_entry(client, auth)
    assert r.status_code == 201
    body = r.json()
    assert body["dict_type"] == "blood_type"
    assert body["code"] == "A"
    assert body["active"] is True


def test_duplicate_code_in_same_type(client, auth):
    make_entry(client, auth)
    r = make_entry(client, auth, name="重复")
    assert r.status_code == 400
    assert r.json()["detail"] == "该字典类型下编码已存在"


def test_same_code_different_type_allowed(client, auth):
    make_entry(client, auth, dict_type="blood_type", code="A")
    r = make_entry(client, auth, dict_type="pay_type", code="A", name="现金")
    assert r.status_code == 201


def test_list_entries_sorted(client, auth):
    make_entry(client, auth, code="B", name="B型", sort_order=2)
    make_entry(client, auth, code="A", name="A型", sort_order=1)
    rows = client.get("/dict/blood_type/entries").json()
    assert [row["code"] for row in rows] == ["A", "B"]


def test_get_entry_and_missing(client, auth):
    make_entry(client, auth)
    r = client.get("/dict/blood_type/entries/A")
    assert r.status_code == 200
    assert r.json()["name"] == "A型"
    assert client.get("/dict/blood_type/entries/Z").status_code == 404


def test_update_entry_disable(client, auth):
    make_entry(client, auth)
    r = client.put(
        "/dict/blood_type/entries/A",
        json={"name": "A型（停用）", "active": False},
        headers=auth["admin"],
    )
    assert r.status_code == 200
    assert r.json()["active"] is False
    assert r.json()["name"] == "A型（停用）"
    # active_only 过滤
    assert client.get("/dict/blood_type/entries?active_only=true").json() == []
    # 更新不存在的条目
    r = client.put(
        "/dict/blood_type/entries/Z", json={"active": True}, headers=auth["admin"]
    )
    assert r.status_code == 404


def test_list_types(client, auth):
    make_entry(client, auth, dict_type="blood_type", code="A")
    make_entry(client, auth, dict_type="blood_type", code="B", name="B型")
    make_entry(client, auth, dict_type="pay_type", code="CASH", name="现金")
    rows = client.get("/dict/types").json()
    types = {row["dict_type"]: row["entry_count"] for row in rows}
    assert types["blood_type"] == 2
    assert types["pay_type"] == 1


def test_role_protection(client, auth):
    r = client.post(
        "/dict/blood_type/entries",
        json={"code": "X", "name": "X"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    r = client.post("/dict/blood_type/entries", json={"code": "Y", "name": "Y"})
    assert r.status_code == 401
