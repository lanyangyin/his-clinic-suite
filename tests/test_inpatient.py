def make_patient(client, auth, id_number="110101199001011234"):
    return client.post(
        "/patients/", json={"name": "张三", "id_number": id_number},
        headers=auth["cashier"],
    ).json()


def make_doctor(client, auth):
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    return client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()


def make_ward_and_beds(client, auth, codes=("101", "102")):
    ward = client.post(
        "/wards/", json={"name": "内科病区"}, headers=auth["admin"]
    ).json()
    beds = [
        client.post(
            "/beds/", json={"ward_id": ward["id"], "code": code},
            headers=auth["admin"],
        ).json()
        for code in codes
    ]
    return ward, beds


def test_create_ward_and_bed(client, auth):
    ward, beds = make_ward_and_beds(client, auth)
    assert ward["name"] == "内科病区"
    assert all(b["status"] == "empty" for b in beds)
    assert beds[0]["code"] == "101"


def test_duplicate_ward_returns_existing(client, auth):
    first = client.post("/wards/", json={"name": "内科病区"}, headers=auth["admin"])
    second = client.post("/wards/", json={"name": "内科病区"}, headers=auth["admin"])
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_duplicate_bed_rejected(client, auth):
    ward, _ = make_ward_and_beds(client, auth)
    r = client.post(
        "/beds/", json={"ward_id": ward["id"], "code": "101"},
        headers=auth["admin"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该病区床位号已存在"


def test_bed_missing_ward(client, auth):
    r = client.post(
        "/beds/", json={"ward_id": 999, "code": "101"}, headers=auth["admin"]
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "病区不存在"


def test_admit_patient_occupies_bed(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    _, beds = make_ward_and_beds(client, auth)
    r = client.post(
        "/admissions/",
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "bed_id": beds[0]["id"],
        },
        headers=auth["cashier"],
    )
    assert r.status_code == 201
    assert r.json()["status"] == "in"
    # 床位变为占用
    assert client.get(f"/beds/{beds[0]['id']}").json()["status"] == "occupied"


def test_admit_occupied_bed_rejected(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    _, beds = make_ward_and_beds(client, auth)
    payload = {
        "patient_id": patient["id"],
        "doctor_id": doctor["id"],
        "bed_id": beds[0]["id"],
    }
    client.post("/admissions/", json=payload, headers=auth["cashier"])
    r = client.post("/admissions/", json=payload, headers=auth["cashier"])
    assert r.status_code == 400
    assert r.json()["detail"] == "床位已被占用"


def test_admit_missing_patient_and_doctor(client, auth):
    _, beds = make_ward_and_beds(client, auth)
    doctor = make_doctor(client, auth)
    r = client.post(
        "/admissions/",
        json={"patient_id": 999, "doctor_id": doctor["id"], "bed_id": beds[0]["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "患者不存在"

    patient = make_patient(client, auth)
    r = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": 999, "bed_id": beds[0]["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "医生不存在"


def test_admit_missing_bed(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    r = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": 999},
        headers=auth["cashier"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "床位不存在"


def test_transfer_bed(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    _, beds = make_ward_and_beds(client, auth)
    admission = client.post(
        "/admissions/",
        json={
            "patient_id": patient["id"],
            "doctor_id": doctor["id"],
            "bed_id": beds[0]["id"],
        },
        headers=auth["cashier"],
    ).json()

    r = client.post(
        f"/admissions/{admission['id']}/transfer-bed",
        json={"bed_id": beds[1]["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 200
    assert r.json()["bed_id"] == beds[1]["id"]
    # 旧床释放、新床占用
    assert client.get(f"/beds/{beds[0]['id']}").json()["status"] == "empty"
    assert client.get(f"/beds/{beds[1]['id']}").json()["status"] == "occupied"


def test_transfer_to_occupied_bed_rejected(client, auth):
    patient = make_patient(client, auth)
    patient2 = make_patient(client, auth, id_number="110101199501011234")
    doctor = make_doctor(client, auth)
    _, beds = make_ward_and_beds(client, auth)
    client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": beds[0]["id"]},
        headers=auth["cashier"],
    )
    admission2 = client.post(
        "/admissions/",
        json={"patient_id": patient2["id"], "doctor_id": doctor["id"], "bed_id": beds[1]["id"]},
        headers=auth["cashier"],
    ).json()

    r = client.post(
        f"/admissions/{admission2['id']}/transfer-bed",
        json={"bed_id": beds[0]["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "目标床位已被占用"


def test_transfer_same_bed_rejected(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    _, beds = make_ward_and_beds(client, auth)
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": beds[0]["id"]},
        headers=auth["cashier"],
    ).json()
    r = client.post(
        f"/admissions/{admission['id']}/transfer-bed",
        json={"bed_id": beds[0]["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "目标床位与当前床位相同"


def test_discharge_releases_bed(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    _, beds = make_ward_and_beds(client, auth)
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": beds[0]["id"]},
        headers=auth["cashier"],
    ).json()

    r = client.post(
        f"/admissions/{admission['id']}/discharge", headers=auth["doctor"]
    )
    assert r.status_code == 200
    assert r.json()["status"] == "discharged"
    assert r.json()["discharged_at"] is not None
    assert client.get(f"/beds/{beds[0]['id']}").json()["status"] == "empty"


def test_discharge_twice_rejected(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    _, beds = make_ward_and_beds(client, auth)
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": beds[0]["id"]},
        headers=auth["cashier"],
    ).json()
    client.post(f"/admissions/{admission['id']}/discharge", headers=auth["doctor"])
    r = client.post(f"/admissions/{admission['id']}/discharge", headers=auth["doctor"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该患者已出院"


def test_transfer_after_discharge_rejected(client, auth):
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    _, beds = make_ward_and_beds(client, auth)
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": beds[0]["id"]},
        headers=auth["cashier"],
    ).json()
    client.post(f"/admissions/{admission['id']}/discharge", headers=auth["doctor"])
    r = client.post(
        f"/admissions/{admission['id']}/transfer-bed",
        json={"bed_id": beds[1]["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该患者已出院，不能转床"


def test_role_protection(client, auth):
    # 医生不能建床位（复用已建好的病区与床位）
    ward, beds = make_ward_and_beds(client, auth)
    r = client.post(
        "/beds/", json={"ward_id": ward["id"], "code": "103"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403

    # 药师不能办理入院（cashier 权限）
    patient = make_patient(client, auth)
    doctor = make_doctor(client, auth)
    r = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": beds[0]["id"]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 403

    # 未登录不能出院
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": beds[0]["id"]},
        headers=auth["cashier"],
    ).json()
    r = client.post(f"/admissions/{admission['id']}/discharge")
    assert r.status_code == 401


def test_get_missing_resources(client, auth):
    assert client.get("/wards/999").status_code == 404
    assert client.get("/beds/999").status_code == 404
    assert client.get("/admissions/999").status_code == 404
