def setup_patient(client, auth, id_number="110101199001012222"):
    return client.post(
        "/patients/",
        json={"name": "NFC患者", "id_number": id_number},
        headers=auth["cashier"],
    ).json()


def test_issue_and_find_card(client, auth):
    patient = setup_patient(client, auth)
    card = client.post(
        f"/patients/{patient['id']}/cards",
        json={"card_uid": "NFC-1001", "note": "首次发卡"},
        headers=auth["cashier"],
    )
    assert card.status_code == 201, card.text
    assert card.json()["card_uid"] == "NFC-1001"
    assert card.json()["patient_name"] == patient["name"]

    found = client.get("/patients/by-card/NFC-1001")
    assert found.status_code == 200
    assert found.json()["patient"]["id"] == patient["id"]

    duplicate = client.post(
        f"/patients/{patient['id']}/cards",
        json={"card_uid": "NFC-1001"},
        headers=auth["cashier"],
    )
    assert duplicate.status_code == 400


def test_lost_and_reissue_card(client, auth):
    patient = setup_patient(client, auth)
    card = client.post(
        f"/patients/{patient['id']}/cards",
        json={"card_uid": "NFC-2001"},
        headers=auth["cashier"],
    ).json()
    lost = client.post(
        f"/patients/{patient['id']}/cards/{card['id']}/lost",
        headers=auth["cashier"],
    )
    assert lost.status_code == 200
    assert lost.json()["status"] == "lost"
    assert client.get("/patients/by-card/NFC-2001").status_code == 404

    new_card = client.post(
        f"/patients/{patient['id']}/cards/reissue",
        json={"card_uid": "NFC-2002", "note": "挂失补卡"},
        headers=auth["cashier"],
    )
    assert new_card.status_code == 201, new_card.text
    assert new_card.json()["card_uid"] == "NFC-2002"
    assert client.get("/patients/by-card/NFC-2002").status_code == 200


def test_card_requires_cashier(client, auth):
    patient = setup_patient(client, auth)
    response = client.post(
        f"/patients/{patient['id']}/cards",
        json={"card_uid": "NFC-3001"},
        headers=auth["doctor"],
    )
    assert response.status_code == 403
