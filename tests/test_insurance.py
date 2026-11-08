from app.modules.insurance import demo_keys
from app.modules.insurance.adapter import (
    InsuranceUnavailable,
    check_prescription,
    settle_payment,
)
from app.modules.insurance.crypto import (
    sm2_sign,
    sm2_verify,
    sm4_decrypt,
    sm4_encrypt,
)
from app.modules.insurance.mock_platform import handle_check, handle_settle


def make_registration(client, auth):
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
    return client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()


def make_drug(client, auth, name, base_price=10.0, ratio=0.7):
    return client.post(
        "/drugs/",
        json={"name": name, "base_price": base_price, "insurance_ratio": ratio},
        headers=auth["admin"],
    ).json()


def make_encounter(client, auth):
    reg = make_registration(client, auth)
    return client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()


# ---------- 国密算法往返 ----------


def test_sm4_roundtrip():
    plaintext = "医保报文：诊断=感冒 数量=2".encode()
    cipher = sm4_encrypt(plaintext)
    assert sm4_decrypt(cipher) == plaintext


def test_sm2_sign_verify():
    data = "待签名数据".encode()
    sig = sm2_sign(data, demo_keys.HIS_PRIVATE, demo_keys.HIS_PUBLIC)
    assert sm2_verify(sig, data, demo_keys.HIS_PUBLIC) is True
    assert sm2_verify(sig, "篡改后的数据".encode(), demo_keys.HIS_PUBLIC) is False


# ---------- 模拟平台规则（直连平台侧） ----------


def test_adapter_check_pass():
    result = check_prescription(
        diagnosis="感冒", drug_name="阿莫西林", quantity=2, ratio=0.7
    )
    assert result["result"] == "pass"


def test_adapter_check_warn():
    result = check_prescription(
        diagnosis="感冒", drug_name="阿莫西林", quantity=6, ratio=0.7
    )
    assert result["result"] == "warn"
    assert "超量" in result["message"]


def test_adapter_check_forbid():
    result = check_prescription(
        diagnosis="感冒", drug_name="进口钙片", quantity=1, ratio=0
    )
    assert result["result"] == "forbid"
    assert "不在医保目录" in result["message"]


def test_adapter_settle():
    result = settle_payment(
        lines=[
            {"drug_name": "A", "total": 30.0, "ratio": 0.7},
            {"drug_name": "B", "total": 50.0, "ratio": 0.8},
        ]
    )
    assert result["total"] == 80.0
    assert result["insurance_amount"] == 61.0  # 21 + 40
    assert result["self_pay_amount"] == 19.0


def test_platform_rejects_tampered_signature():
    from app.modules.insurance.adapter import _build_request
    from app.modules.insurance.mock_platform import handle_check

    payload = _build_request(
        "check", {"diagnosis": "x", "drug_name": "A", "quantity": 1, "ratio": 0.7}
    )
    payload["sign"] = "0" * 128  # 篡改签名
    try:
        handle_check(payload)
        assert False, "篡改签名应被平台拒绝"
    except ValueError as e:
        assert "签名" in str(e)


# ---------- API 集成：事前提醒 ----------


def test_prescribe_pass_no_warning(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, "A药", ratio=0.7)
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    assert r.json()["insurance_warning"] is None


def test_prescribe_warn_records_warning(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, "A药", ratio=0.7)
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 6},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    assert "超量" in r.json()["insurance_warning"]


def test_prescribe_forbid_rejected(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, "目录外药", ratio=0)
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert "不在医保目录" in r.json()["detail"]


def test_prescribe_degrades_when_insurance_down(client, auth, monkeypatch):
    import app.modules.encounter.service as encounter_service

    def _down(**kwargs):
        raise InsuranceUnavailable("医保服务不可用")

    monkeypatch.setattr(encounter_service, "check_prescription", _down)
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, "A药", ratio=0.7)
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    assert "自费放行" in r.json()["insurance_warning"]


# ---------- API 集成：结算 ----------


def test_payment_with_insurance(client, auth):
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, "A药", base_price=10.0, ratio=0.8)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 3},
        headers=auth["doctor"],
    )
    r = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == 30.0
    assert body["insurance_amount"] == 24.0  # 30 * 0.8
    assert body["self_pay_amount"] == 6.0


def test_payment_degrades_to_self_pay(client, auth, monkeypatch):
    import app.modules.billing.service as billing_service

    def _down(**kwargs):
        raise InsuranceUnavailable("医保服务不可用")

    monkeypatch.setattr(billing_service, "settle_payment", _down)
    encounter = make_encounter(client, auth)
    drug = make_drug(client, auth, "A药", base_price=10.0, ratio=0.8)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 3},
        headers=auth["doctor"],
    )
    r = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert r.status_code == 201
    body = r.json()
    assert body["insurance_amount"] == 0.0
    assert body["self_pay_amount"] == 30.0
