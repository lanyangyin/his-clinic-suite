def setup_admitted(client, auth):
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
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": bed["id"]},
        headers=auth["cashier"],
    ).json()
    return admission, doctor


def make_pathway(client, auth, name="社区获得性肺炎路径", diagnosis="社区获得性肺炎"):
    return client.post(
        "/pathways/",
        json={"name": name, "diagnosis": diagnosis},
        headers=auth["admin"],
    )


def test_create_pathway(client, auth):
    r = make_pathway(client, auth)
    assert r.status_code == 201
    assert r.json()["name"] == "社区获得性肺炎路径"


def test_duplicate_pathway_rejected(client, auth):
    make_pathway(client, auth)
    r = make_pathway(client, auth)
    assert r.status_code == 400
    assert r.json()["detail"] == "临床路径名称已存在"


def test_enroll_patient(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    r = client.post(
        f"/pathways/{pathway['id']}/enroll",
        json={"admission_id": admission["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "active"
    assert body["admission_id"] == admission["id"]


def test_enroll_twice_rejected(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    payload = {"admission_id": admission["id"]}
    client.post(f"/pathways/{pathway['id']}/enroll", json=payload, headers=auth["doctor"])
    r = client.post(f"/pathways/{pathway['id']}/enroll", json=payload, headers=auth["doctor"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该患者已在该路径中"


def test_enroll_after_discharge_rejected(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    client.post(f"/admissions/{admission['id']}/discharge", headers=auth["doctor"])
    r = client.post(
        f"/pathways/{pathway['id']}/enroll",
        json={"admission_id": admission["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该患者已出院，不能入径"


def test_enroll_missing_pathway_or_admission(client, auth):
    admission, doctor = setup_admitted(client, auth)
    r = client.post(
        "/pathways/999/enroll", json={"admission_id": admission["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 404
    pathway = make_pathway(client, auth).json()
    r = client.post(
        f"/pathways/{pathway['id']}/enroll", json={"admission_id": 999},
        headers=auth["doctor"],
    )
    assert r.status_code == 404


def test_variance_recorded(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    enrollment = client.post(
        f"/pathways/{pathway['id']}/enroll",
        json={"admission_id": admission["id"]},
        headers=auth["doctor"],
    ).json()

    r = client.post(
        f"/pathways/enrollments/{enrollment['id']}/variance",
        json={"reason": "患者发热持续，抗生素方案调整"},
        headers=auth["nurse"],
    )
    assert r.status_code == 200
    assert r.json()["noted_by"] == "nurse"

    variances = client.get(
        f"/pathways/enrollments/{enrollment['id']}/variances"
    ).json()
    assert len(variances) == 1
    assert "抗生素方案调整" in variances[0]["reason"]


def test_variance_only_when_active(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    enrollment = client.post(
        f"/pathways/{pathway['id']}/enroll",
        json={"admission_id": admission["id"]},
        headers=auth["doctor"],
    ).json()
    client.post(f"/pathways/enrollments/{enrollment['id']}/complete", headers=auth["doctor"])
    r = client.post(
        f"/pathways/enrollments/{enrollment['id']}/variance",
        json={"reason": "x"},
        headers=auth["nurse"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "仅进行中的路径可记录变异"


def test_complete_enrollment(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    enrollment = client.post(
        f"/pathways/{pathway['id']}/enroll",
        json={"admission_id": admission["id"]},
        headers=auth["doctor"],
    ).json()
    r = client.post(f"/pathways/enrollments/{enrollment['id']}/complete", headers=auth["doctor"])
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert r.json()["completed_at"] is not None
    # 重复完成被拒
    again = client.post(f"/pathways/enrollments/{enrollment['id']}/complete", headers=auth["doctor"])
    assert again.status_code == 400


def test_withdraw_enrollment(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    enrollment = client.post(
        f"/pathways/{pathway['id']}/enroll",
        json={"admission_id": admission["id"]},
        headers=auth["doctor"],
    ).json()
    r = client.post(f"/pathways/enrollments/{enrollment['id']}/withdraw", headers=auth["doctor"])
    assert r.status_code == 200
    assert r.json()["status"] == "withdrawn"
    # 退出后不能完成
    r = client.post(f"/pathways/enrollments/{enrollment['id']}/complete", headers=auth["doctor"])
    assert r.status_code == 400


def test_list_endpoints(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    enrollment = client.post(
        f"/pathways/{pathway['id']}/enroll",
        json={"admission_id": admission["id"]},
        headers=auth["doctor"],
    ).json()
    # 路径列表
    all_paths = client.get("/pathways/").json()
    assert len(all_paths) == 1
    filtered = client.get("/pathways/?diagnosis=社区获得性肺炎").json()
    assert len(filtered) == 1
    # 住院记录入径列表
    enrollments = client.get(f"/pathways/enrollments/admission/{admission['id']}").json()
    assert len(enrollments) == 1
    assert enrollments[0]["id"] == enrollment["id"]


def test_get_missing(client):
    assert client.get("/pathways/999").status_code == 404
    assert client.get("/pathways/enrollments/999").status_code == 404


def test_role_protection(client, auth):
    admission, doctor = setup_admitted(client, auth)
    pathway = make_pathway(client, auth).json()
    # 医生不能建路径
    r = client.post(
        "/pathways/", json={"name": "X", "diagnosis": "X"}, headers=auth["doctor"]
    )
    assert r.status_code == 403
    # 收费员不能入径
    r = client.post(
        f"/pathways/{pathway['id']}/enroll",
        json={"admission_id": admission["id"]},
        headers=auth["cashier"],
    )
    assert r.status_code == 403
    # 未登录不能入径
    r = client.post(
        f"/pathways/{pathway['id']}/enroll", json={"admission_id": admission["id"]}
    )
    assert r.status_code == 401
