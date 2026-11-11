def _setup(client, auth, suffix):
    dept = client.post(
        "/departments/", json={"name": f"锁科{suffix}"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": f"锁医生{suffix}", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    regs = []
    for index in (1, 2):
        patient = client.post(
            "/patients/",
            json={"name": f"锁患者{suffix}-{index}", "id_number": f"11010119900101{suffix}{index}"},
            headers=auth["cashier"],
        ).json()
        reg = client.post(
            "/registrations/",
            json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
            headers=auth["cashier"],
        ).json()
        regs.append(reg)
    return doctor, regs


def test_only_one_active_encounter_until_pause(client, auth):
    doctor, regs = _setup(client, auth, "31")
    first = client.post(
        "/encounters/start", json={"registration_id": regs[0]["id"]}, headers=auth["doctor"]
    )
    assert first.status_code == 201, first.text
    blocked = client.post(
        "/encounters/start", json={"registration_id": regs[1]["id"]}, headers=auth["doctor"]
    )
    assert blocked.status_code == 400
    assert "尚未完成" in blocked.json()["detail"]

    paused = client.post(
        f"/encounters/{first.json()['id']}/pause", headers=auth["doctor"]
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    second = client.post(
        "/encounters/start", json={"registration_id": regs[1]["id"]}, headers=auth["doctor"]
    )
    assert second.status_code == 201, second.text

    resume_blocked = client.post(
        f"/encounters/{first.json()['id']}/resume", headers=auth["doctor"]
    )
    assert resume_blocked.status_code == 400
    assert "当前患者" in resume_blocked.json()["detail"]


def test_adverse_reaction_pauses_encounter_and_is_listed(client, auth):
    doctor, regs = _setup(client, auth, "32")
    encounter = client.post(
        "/encounters/start", json={"registration_id": regs[0]["id"]}, headers=auth["doctor"]
    ).json()
    response = client.post(
        f"/encounters/{encounter['id']}/adverse-reactions",
        json={
            "drug_name": "测试药",
            "reaction": "皮疹、瘙痒",
            "severity": "moderate",
            "action_taken": "立即停药",
            "pause_encounter": True,
        },
        headers=auth["doctor"],
    )
    assert response.status_code == 201, response.text
    assert response.json()["reported_by"] == "doctor"
    detail = client.get(f"/encounters/{encounter['id']}")
    assert detail.json()["status"] == "paused"
    rows = client.get(
        f"/encounters/{encounter['id']}/adverse-reactions", headers=auth["doctor"]
    )
    assert rows.status_code == 200
    assert rows.json()[0]["drug_name"] == "测试药"
