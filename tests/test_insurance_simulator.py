"""国家医保第三方模拟器：服务端协议/参数联调。"""
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.insurance_simulator import Handler


@pytest.fixture(scope="module")
def simulator():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    yield base
    server.shutdown()
    thread.join(timeout=3)


def _login(client):
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )


def _configure(client, url, *, timeout=5, retry=0):
    _login(client)
    form = {
        "clinic_name": "模拟机构",
        "insurance_enabled": "1",
        "national_url": url,
        "national_token": "sim-token",
        "national_org_code": "H999999",
        "national_org_name": "模拟医院",
        "national_region_code": "110000",
        "national_mdtrtarea_code": "110100",
        "national_insuplc_code": "110000",
        "national_operator": "SIM01",
        "national_infver": "V1.0",
        "national_recer_sys_code": "HIS",
        "national_med_type": "11",
        "national_sign_type": "SM2",
        "national_security_mode": "plain",
        "national_timeout": str(timeout),
        "national_retry": str(retry),
        "national_mock": "0",
    }
    response = client.post(
        "/admin/institution-settings", data=form, follow_redirects=False
    )
    assert response.status_code == 302, response.text


def _encounter(client, auth):
    patient = client.post(
        "/patients/", json={"name": "模拟医保患者", "id_number": "110101199404049999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post("/departments/", json={"name": "模拟医保科"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": "模拟医保医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/", json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "模拟诊断"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "模拟医保药", "base_price": 10, "insurance_code": "SIM01"},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    return encounter


def test_simulator_success_and_envelope(client, auth, simulator):
    Handler.requests.clear()
    _configure(client, simulator + "/success")
    status = client.get("/insurance/national/status", headers=auth["admin"]).json()
    assert status["security_mode"] == "plain"
    assert status["fixmedins_code"] == "H999999"
    assert status["mdtrtarea_admvs"] == "110100"
    assert status["missing"] == []

    encounter = _encounter(client, auth)
    response = client.post(
        f"/insurance/national/pre-settle/{encounter['id']}", headers=auth["cashier"]
    )
    assert response.status_code == 200, response.text
    assert response.json()["infcode"] == 0
    request = Handler.requests[-1]
    assert request["fixmedins_code"] == "H999999"
    assert request["fixmedins_name"] == "模拟医院"
    assert request["infver"] == "V1.0"
    assert request["recer_sys_code"] == "HIS"
    assert request["mdtrtarea_admvs"] == "110100"
    assert request["insuplc_admdvs"] == "110000"
    assert request["input"]["data"]["med_type"] == "11"

    setl_id = response.json()["output"]["setlinfo"]["setl_id"]
    settled = client.post(
        f"/insurance/national/settle/{encounter['id']}",
        json={"setl_id": setl_id}, headers=auth["cashier"],
    )
    assert settled.status_code == 200, settled.text
    cancelled = client.post(
        f"/insurance/national/cancel-settle/{encounter['id']}",
        json={"setl_id": setl_id}, headers=auth["cashier"],
    )
    assert cancelled.status_code == 200, cancelled.text


def test_simulator_business_error_does_not_fake_success(client, auth, simulator):
    _configure(client, simulator + "/business-error")
    encounter = _encounter(client, auth)
    response = client.post(
        f"/insurance/national/pre-settle/{encounter['id']}", headers=auth["cashier"]
    )
    assert response.status_code == 503
    assert "模拟医保业务失败" in response.text


def test_simulator_malformed_response_is_rejected(client, auth, simulator):
    _configure(client, simulator + "/malformed")
    encounter = _encounter(client, auth)
    response = client.post(
        f"/insurance/national/pre-settle/{encounter['id']}", headers=auth["cashier"]
    )
    assert response.status_code == 503


def test_simulator_timeout_is_bounded(client, auth, simulator):
    _configure(client, simulator + "/timeout", timeout=1)
    encounter = _encounter(client, auth)
    response = client.post(
        f"/insurance/national/pre-settle/{encounter['id']}", headers=auth["cashier"]
    )
    assert response.status_code == 503


def test_standard_security_mode_refuses_fake_success(client, auth, simulator):
    _configure(client, simulator + "/success")
    _login(client)
    client.post(
        "/admin/institution-settings",
        data={
            "clinic_name": "模拟机构",
            "insurance_enabled": "1",
            "national_url": simulator + "/success",
            "national_org_code": "H999999",
            "national_region_code": "110000",
            "national_operator": "SIM01",
            "national_security_mode": "sm2_sm4",
            "national_sm2_private_key": "test-key",
            "national_sm4_key": "test-key",
            "national_mock": "0",
        },
        follow_redirects=False,
    )
    encounter = _encounter(client, auth)
    response = client.post(
        f"/insurance/national/pre-settle/{encounter['id']}", headers=auth["cashier"]
    )
    assert response.status_code == 503
    assert "SM2" in response.text or "sm2" in response.text
