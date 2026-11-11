def test_doctor_can_update_allergy_and_conditions_with_audit(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "接诊修改患者", "id_number": "110101199001016666"},
        headers=auth["cashier"],
    ).json()
    response = client.put(
        f"/patients/{patient['id']}/clinical-profile",
        json={
            "allergy_status": "present",
            "allergy_detail": "青霉素",
            "special_history": "2型糖尿病 8 年；高血压 5 年",
            "reason": "接诊核对患者史",
        },
        headers=auth["doctor"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["allergy_label"] == "青霉素"
    assert body["special_history"] == "2型糖尿病 8 年；高血压 5 年"

    changes = client.get(
        f"/patients/{patient['id']}/clinical-changes", headers=auth["doctor"]
    )
    assert changes.status_code == 200
    fields = {row["field"] for row in changes.json()}
    assert fields == {"allergy", "special_history"}
    assert all(row["reason"] == "接诊核对患者史" for row in changes.json())

    denied = client.put(
        f"/patients/{patient['id']}/clinical-profile",
        json={"special_history": "x", "reason": "x"},
        headers=auth["cashier"],
    )
    assert denied.status_code == 403
