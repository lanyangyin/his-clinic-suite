def setup_admission(client, auth):
    """建患者/医生/病区/床位并入院，返回 admission。"""
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    ward = client.post("/wards/", json={"name": "内科病区"}, headers=auth["admin"]).json()
    bed = client.post(
        "/beds/", json={"ward_id": ward["id"], "code": "101"}, headers=auth["admin"]
    ).json()
    return client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": bed["id"]},
        headers=auth["cashier"],
    ).json()


def test_record_vital_signs(client, auth):
    admission = setup_admission(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/vital-signs",
        json={"temperature": 37.5, "pulse": 88, "respiration": 20, "systolic": 120, "diastolic": 80, "spo2": 98},
        headers=auth["nurse"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["temperature"] == 37.5
    assert body["spo2"] == 98
    assert body["recorded_by"] == "nurse"


def test_vital_signs_partial_record(client, auth):
    admission = setup_admission(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/vital-signs",
        json={"temperature": 36.8},
        headers=auth["nurse"],
    )
    assert r.status_code == 201
    assert r.json()["pulse"] is None


def test_vital_signs_all_empty_rejected(client, auth):
    admission = setup_admission(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/vital-signs",
        json={},
        headers=auth["nurse"],
    )
    assert r.status_code == 422


def test_vital_signs_out_of_range_rejected(client, auth):
    admission = setup_admission(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/vital-signs",
        json={"temperature": 50},
        headers=auth["nurse"],
    )
    assert r.status_code == 422


def test_list_vital_signs(client, auth):
    admission = setup_admission(client, auth)
    for temp in (36.5, 37.2, 38.0):
        client.post(
            f"/admissions/{admission['id']}/vital-signs",
            json={"temperature": temp},
            headers=auth["nurse"],
        )
    r = client.get(f"/admissions/{admission['id']}/vital-signs")
    assert r.status_code == 200
    assert [v["temperature"] for v in r.json()] == [36.5, 37.2, 38.0]


def test_vital_signs_missing_admission(client, auth):
    r = client.post(
        "/admissions/999/vital-signs", json={"temperature": 36.5}, headers=auth["nurse"]
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "住院记录不存在"
    assert client.get("/admissions/999/vital-signs").status_code == 404


def test_create_nursing_note(client, auth):
    admission = setup_admission(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/nursing-notes",
        json={"content": "患者诉头晕，已通知医生，嘱卧床休息。"},
        headers=auth["nurse"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["recorded_by"] == "nurse"
    assert "头晕" in body["content"]


def test_nursing_note_empty_content_rejected(client, auth):
    admission = setup_admission(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/nursing-notes",
        json={"content": ""},
        headers=auth["nurse"],
    )
    assert r.status_code == 422


def test_list_nursing_notes(client, auth):
    admission = setup_admission(client, auth)
    for text in ("记录一", "记录二"):
        client.post(
            f"/admissions/{admission['id']}/nursing-notes",
            json={"content": text},
            headers=auth["nurse"],
        )
    r = client.get(f"/admissions/{admission['id']}/nursing-notes")
    assert r.status_code == 200
    assert [n["content"] for n in r.json()] == ["记录一", "记录二"]


def test_nursing_notes_missing_admission(client, auth):
    r = client.post(
        "/admissions/999/nursing-notes", json={"content": "x"}, headers=auth["nurse"]
    )
    assert r.status_code == 400
    assert client.get("/admissions/999/nursing-notes").status_code == 404


def test_role_protection(client, auth):
    admission = setup_admission(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/vital-signs",
        json={"temperature": 36.5},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    r = client.post(
        f"/admissions/{admission['id']}/nursing-notes",
        json={"content": "x"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    r = client.post(f"/admissions/{admission['id']}/vital-signs", json={"temperature": 36.5})
    assert r.status_code == 401
