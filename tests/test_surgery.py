"""手术室：排班、安全核查、术中记录、器械清点、复苏、CSSD 包。"""
from datetime import date, timedelta


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "手术患者", "id_number": "110101198601019999"},
        headers=auth["cashier"],
    ).json()
    room = client.post(
        "/surgery/rooms",
        json={"code": "OR-1", "name": "一号手术间", "location": "3楼"},
        headers=auth["surgery"],
    ).json()
    case = client.post(
        "/surgery/cases",
        json={
            "patient_id": patient["id"],
            "room_id": room["id"],
            "procedure_name": "腹腔镜胆囊切除术",
            "diagnosis": "胆囊结石",
            "surgeon": "张医生",
            "anesthesia_type": "全麻",
            "scheduled_at": (date.today() + timedelta(days=1)).isoformat() + "T09:00:00",
        },
        headers=auth["surgery"],
    ).json()
    return patient, room, case


def test_surgery_case_full_flow(client, auth):
    patient, room, case = _setup(client, auth)
    assert case["surgery_no"].startswith("SR")
    assert case["patient_name"] == "手术患者"
    assert case["status"] == "scheduled"

    # 未做术前核查不能开始
    blocked = client.post(
        f"/surgery/cases/{case['id']}/start", headers=auth["surgery"]
    )
    assert blocked.status_code == 400
    assert "安全核查" in blocked.json()["detail"]

    sign_in = client.post(
        f"/surgery/cases/{case['id']}/safety",
        json={"phase": "sign_in", "checklist": "身份/部位/过敏史确认"},
        headers=auth["surgery"],
    )
    assert sign_in.status_code == 201
    duplicate = client.post(
        f"/surgery/cases/{case['id']}/safety",
        json={"phase": "sign_in", "checklist": "重复"},
        headers=auth["surgery"],
    )
    assert duplicate.status_code == 400

    started = client.post(
        f"/surgery/cases/{case['id']}/start", headers=auth["surgery"]
    )
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    record = client.post(
        f"/surgery/cases/{case['id']}/record",
        json={
            "findings": "胆囊壁增厚",
            "procedure_detail": "三孔法完成",
            "implants": "",
            "specimens": "胆囊送病理",
            "blood_loss_ml": 20,
        },
        headers=auth["surgery"],
    )
    assert record.status_code == 201
    assert record.json()["blood_loss_ml"] == 20

    count = client.post(
        f"/surgery/cases/{case['id']}/counts",
        json={"phase": "after", "item_name": "纱布", "expected": 10, "actual": 10},
        headers=auth["surgery"],
    )
    assert count.status_code == 201
    assert count.json()["matched"] is True

    no_sign_out = client.post(
        f"/surgery/cases/{case['id']}/complete", headers=auth["surgery"]
    )
    assert no_sign_out.status_code == 400
    assert "离室" in no_sign_out.json()["detail"]

    client.post(
        f"/surgery/cases/{case['id']}/safety",
        json={"phase": "sign_out", "checklist": "器械/标本/患者状态确认"},
        headers=auth["surgery"],
    )
    completed = client.post(
        f"/surgery/cases/{case['id']}/complete", headers=auth["surgery"]
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    recovery = client.post(
        f"/surgery/cases/{case['id']}/recovery",
        json={"vitals": "BP 120/80，HR 76", "score": 9, "note": "清醒"},
        headers=auth["surgery"],
    )
    assert recovery.status_code == 201
    assert recovery.json()["score"] == 9

    detail = client.get(
        f"/surgery/cases/{case['id']}", headers=auth["surgery"]
    ).json()
    assert len(detail["checks"]) == 2
    assert len(detail["records"]) == 1
    assert len(detail["counts"]) == 1
    assert len(detail["recovery"]) == 1


def test_surgery_count_mismatch_blocks_completion(client, auth):
    _, _, case = _setup(client, auth)
    client.post(
        f"/surgery/cases/{case['id']}/safety",
        json={"phase": "sign_in", "checklist": "ok"},
        headers=auth["surgery"],
    )
    client.post(f"/surgery/cases/{case['id']}/start", headers=auth["surgery"])
    client.post(
        f"/surgery/cases/{case['id']}/counts",
        json={"phase": "after", "item_name": "纱布", "expected": 10, "actual": 9},
        headers=auth["surgery"],
    )
    client.post(
        f"/surgery/cases/{case['id']}/safety",
        json={"phase": "sign_out", "checklist": "ok"},
        headers=auth["surgery"],
    )
    blocked = client.post(
        f"/surgery/cases/{case['id']}/complete", headers=auth["surgery"]
    )
    assert blocked.status_code == 400
    assert "清点不符" in blocked.json()["detail"]


def test_surgery_attach_cssd_package(client, auth):
    _, _, case = _setup(client, auth)
    instrument_set = client.post(
        "/cssd/sets",
        json={"code": "OR-SET", "name": "腹腔镜包"},
        headers=auth["nurse"],
    ).json()
    batch = client.post(
        "/cssd/batches",
        json={
            "sterilizer": "高压灭菌器",
            "chemical_indicator": "pass",
            "biological_indicator": "pass",
        },
        headers=auth["nurse"],
    ).json()
    client.post(f"/cssd/batches/{batch['id']}/release", json={}, headers=auth["nurse"])
    package = client.post(
        "/cssd/packages",
        json={
            "package_code": "OR-PKG-1",
            "set_id": instrument_set["id"],
            "batch_id": batch["id"],
            "expiry": (date.today() + timedelta(days=180)).isoformat(),
        },
        headers=auth["nurse"],
    ).json()
    attached = client.post(
        f"/surgery/cases/{case['id']}/packages/{package['id']}",
        headers=auth["surgery"],
    )
    assert attached.status_code == 200
    assert attached.json()["package_code"] == "OR-PKG-1"


def test_surgery_permissions(client, auth):
    assert client.get("/surgery/cases", headers=auth["doctor"]).status_code == 403
    assert client.get("/surgery/rooms", headers=auth["cashier"]).status_code == 403
