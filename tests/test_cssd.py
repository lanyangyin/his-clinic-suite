"""器械灭菌（CSSD）：监测放行、包码发放/使用/召回。"""


def _set(client, auth):
    return client.post(
        "/cssd/sets",
        json={"code": "SET-001", "name": "换药包", "department": "门诊"},
        headers=auth["nurse"],
    ).json()


def _batch(client, auth, **overrides):
    payload = {
        "sterilizer": "高压灭菌器 1",
        "method": "steam",
        "cycle": "134℃ 4min",
        "temperature": 134,
        "pressure": 210,
        "duration_min": 4,
        "chemical_indicator": "pass",
        "biological_indicator": "pass",
    }
    payload.update(overrides)
    return client.post("/cssd/batches", json=payload, headers=auth["nurse"])


def _package(client, auth, set_id, batch_id, code="PKG-001", expiry=None):
    from datetime import date, timedelta

    return client.post(
        "/cssd/packages",
        json={
            "package_code": code,
            "set_id": set_id,
            "batch_id": batch_id,
            "expiry": expiry or (date.today() + timedelta(days=180)).isoformat(),
            "location": "无菌间",
        },
        headers=auth["nurse"],
    )


def test_cssd_release_issue_use(client, auth):
    instrument_set = _set(client, auth)
    batch = _batch(client, auth)
    assert batch.status_code == 201
    batch = batch.json()
    assert batch["release_status"] == "pending"

    released = client.post(
        f"/cssd/batches/{batch['id']}/release",
        json={"released_by": "护士长"},
        headers=auth["nurse"],
    )
    assert released.status_code == 200
    assert released.json()["release_status"] == "released"

    package = _package(client, auth, instrument_set["id"], batch["id"])
    assert package.status_code == 201
    package = package.json()
    assert package["set_name"] == "换药包"
    assert package["batch_no"] == batch["batch_no"]

    issued = client.post(
        f"/cssd/packages/{package['id']}/issue",
        json={"department": "门诊"},
        headers=auth["nurse"],
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "issued"

    used = client.post(
        f"/cssd/packages/{package['id']}/use",
        json={"department": "门诊", "patient_id": None},
        headers=auth["nurse"],
    )
    assert used.status_code == 201
    assert used.json()["package_id"] == package["id"]

    detail = client.get(
        "/cssd/packages", params={"status": "used"}, headers=auth["nurse"]
    ).json()
    assert detail[0]["package_code"] == "PKG-001"


def test_cssd_cannot_release_without_indicators(client, auth):
    _set(client, auth)
    batch = _batch(client, auth, biological_indicator="pending").json()
    response = client.post(
        f"/cssd/batches/{batch['id']}/release", json={}, headers=auth["nurse"]
    )
    assert response.status_code == 400
    assert "监测" in response.json()["detail"]


def test_cssd_cannot_issue_before_release(client, auth):
    instrument_set = _set(client, auth)
    batch = _batch(client, auth).json()
    package = _package(client, auth, instrument_set["id"], batch["id"]).json()
    response = client.post(
        f"/cssd/packages/{package['id']}/issue",
        json={"department": "门诊"},
        headers=auth["nurse"],
    )
    assert response.status_code == 400
    assert "未放行" in response.json()["detail"]


def test_cssd_reject_recalls_packages_and_expiry(client, auth):
    from datetime import date, timedelta

    instrument_set = _set(client, auth)
    batch = _batch(client, auth).json()
    _package(client, auth, instrument_set["id"], batch["id"], "PKG-EXPIRE", (date.today() + timedelta(days=10)).isoformat())
    rejected = client.post(
        f"/cssd/batches/{batch['id']}/reject",
        json={"reason": "生物监测不合格"},
        headers=auth["nurse"],
    )
    assert rejected.status_code == 200
    assert rejected.json()["release_status"] == "rejected"
    packages = client.get("/cssd/packages", headers=auth["nurse"]).json()
    assert all(row["status"] == "recalled" for row in packages)

    alerts = client.get(
        "/cssd/expiry-alerts", params={"days": 30}, headers=auth["nurse"]
    ).json()
    assert alerts == []
