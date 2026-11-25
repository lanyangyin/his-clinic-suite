"""国家医保平台门诊接口模板（mock/缺配置）。"""
import pytest


def make_encounter(client, auth):
    patient = client.post(
        "/patients/", json={"name": "医保患者", "id_number": "110101199001019999"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "医保内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "医保医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/", json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": registration["id"], "diagnosis": "高血压"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "医保药", "base_price": 10, "insurance_ratio": 0.7,
                         "insurance_code": "XA01"},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    return encounter


def test_national_status_reports_missing_config(client, auth, monkeypatch):
    from app import settings

    monkeypatch.setattr(settings, "INSURANCE_NATIONAL_URL", "")
    monkeypatch.setattr(settings, "INSURANCE_NATIONAL_ORG_CODE", "")
    monkeypatch.setattr(settings, "INSURANCE_NATIONAL_REGION_CODE", "")
    monkeypatch.setattr(settings, "INSURANCE_NATIONAL_MOCK", False)
    status = client.get("/insurance/national/status", headers=auth["admin"]).json()
    assert status["configured"] is False
    assert "url" in status["missing"]

    encounter = make_encounter(client, auth)
    blocked = client.post(
        f"/insurance/national/pre-settle/{encounter['id']}", headers=auth["cashier"]
    )
    assert blocked.status_code == 503


def test_national_pre_settle_and_settle_mock(client, auth, monkeypatch):
    from app import settings

    monkeypatch.setattr(settings, "INSURANCE_NATIONAL_URL", "")
    monkeypatch.setattr(settings, "INSURANCE_NATIONAL_MOCK", True)
    encounter = make_encounter(client, auth)
    pre = client.post(
        f"/insurance/national/pre-settle/{encounter['id']}", headers=auth["cashier"]
    )
    assert pre.status_code == 200, pre.text
    assert pre.json()["mock"] is True
    setl_id = pre.json()["output"]["setlinfo"]["setl_id"]

    settled = client.post(
        f"/insurance/national/settle/{encounter['id']}",
        json={"setl_id": setl_id}, headers=auth["cashier"],
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["infcode"] == 0

    rows = client.get(
        "/insurance/national/transactions", headers=auth["admin"]
    ).json()
    assert any(row["infno"] == "2206" for row in rows)
    assert any(row["infno"] == "2207" for row in rows)
