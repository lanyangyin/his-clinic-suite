"""医生查看患者历史诊疗聚合接口。"""


def _setup_visit(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "历史患者", "id_number": "110101198001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "历史内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "历史医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": registration["id"], "diagnosis": "高血压复诊"},
        headers=auth["doctor"],
    ).json()
    record = client.post(
        f"/encounters/{encounter['id']}/medical-record",
        json={
            "chief_complaint": "头晕 1 周",
            "present_illness": "晨起头晕，血压偏高",
            "past_history": "高血压 5 年",
            "physical_exam": "血压 150/95mmHg",
            "treatment_advice": "低盐饮食，规律服药",
        },
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/medical-record/sign", headers=auth["doctor"]
    )
    drug = client.post(
        "/drugs/",
        json={"name": "历史降压药", "base_price": 10.0, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={
            "drug_id": drug["id"],
            "quantity": 2,
            "dosage": "1片",
            "frequency": "qd",
            "route": "口服",
            "days": 7,
        },
        headers=auth["doctor"],
    )
    lab_item = client.post(
        "/lab/items/",
        json={"code": "HIST-LAB", "name": "历史血常规", "price": 20.0},
        headers=auth["admin"],
    ).json()
    lab = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": lab_item["id"]},
        headers=auth["doctor"],
    ).json()
    charge_item = client.post(
        "/charges/items/",
        json={
            "code": "HIST-TRT",
            "name": "历史雾化",
            "category": "treatment",
            "price": 30.0,
            "insurance_ratio": 0.0,
        },
        headers=auth["admin"],
    ).json()
    treatment = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": charge_item["id"], "quantity": 1},
        headers=auth["doctor"],
    ).json()
    payment = client.post(
        "/payments/",
        json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    ).json()
    client.post(
        f"/lab/requests/{lab['id']}/report",
        json={"result": "血压相关指标正常"},
        headers=auth["lab"],
    )
    client.post(f"/treatments/{treatment['id']}/execute", headers=auth["nurse"])
    return patient, doctor, encounter, record, drug, lab, treatment, payment


def test_patient_history_contains_all_visit_data(client, auth):
    patient, doctor, encounter, record, drug, lab, treatment, payment = _setup_visit(
        client, auth
    )

    response = client.get(
        f"/patients/{patient['id']}/history", headers=auth["doctor"]
    )
    assert response.status_code == 200
    data = response.json()
    assert data["patient"]["name"] == "历史患者"
    assert len(data["encounters"]) == 1

    visit = data["encounters"][0]
    assert visit["id"] == encounter["id"]
    assert visit["diagnosis"] == "高血压复诊"
    assert visit["doctor_id"] == doctor["id"]
    assert visit["doctor_name"] == "历史医生"
    assert visit["medical_record"]["chief_complaint"] == "头晕 1 周"
    assert visit["medical_record"]["signed_by"] == "doctor"
    assert visit["prescriptions"][0]["drug_name"] == "历史降压药"
    assert visit["prescriptions"][0]["quantity"] == 2
    assert visit["lab_requests"][0]["item_name"] == "历史血常规"
    assert visit["lab_requests"][0]["status"] == "reported"
    assert visit["lab_requests"][0]["result"] == "血压相关指标正常"
    assert visit["treatments"][0]["item_name"] == "历史雾化"
    assert visit["treatments"][0]["status"] == "done"
    assert visit["charges"]
    assert visit["payments"][0]["id"] == payment["id"]
    assert visit["payments"][0]["status"] == "paid"


def test_patient_history_missing_patient(client, auth):
    response = client.get("/patients/99999/history", headers=auth["doctor"])
    assert response.status_code == 404
    assert response.json()["detail"] == "患者不存在"


def test_patient_history_requires_doctor(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "权限患者", "id_number": "110101198001019999"},
        headers=auth["cashier"],
    ).json()
    response = client.get(
        f"/patients/{patient['id']}/history", headers=auth["cashier"]
    )
    assert response.status_code == 403
