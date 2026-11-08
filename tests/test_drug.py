def test_create_drug(client, auth):
    r = client.post(
        "/drugs/",
        json={"name": "阿莫西林胶囊", "spec": "0.25g*24粒", "unit": "盒", "base_price": 12.5},
        headers=auth["admin"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["spec"] == "0.25g*24粒"


def test_duplicate_drug_returns_existing(client, auth):
    first = client.post(
        "/drugs/", json={"name": "阿莫西林胶囊", "base_price": 12.5}, headers=auth["admin"]
    )
    second = client.post(
        "/drugs/", json={"name": "阿莫西林胶囊", "base_price": 99}, headers=auth["admin"]
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_drug_negative_price_rejected(client, auth):
    r = client.post("/drugs/", json={"name": "x", "base_price": -1}, headers=auth["admin"])
    assert r.status_code == 422


def test_get_drug(client, auth):
    drug = client.post(
        "/drugs/", json={"name": "阿莫西林胶囊", "base_price": 12.5}, headers=auth["admin"]
    ).json()
    r = client.get(f"/drugs/{drug['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "阿莫西林胶囊"


def test_get_drug_missing(client):
    assert client.get("/drugs/999").status_code == 404
