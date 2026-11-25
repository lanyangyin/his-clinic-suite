"""国家医保平台门诊接口模板（2203/2204/2206/2207/2208）。

说明：
- 报文按公开的《医疗保障信息平台 定点医药机构接口规范》基线版组织；
- 真实平台还需要各地前置机地址、机构编码、密钥/证书、SM2/SM4 封装；
- 未配置时抛 NationalInsuranceNotConfigured，路由返回 503，不伪造结算成功；
- 显式配置 mock 时返回带 mock 标记的演示结果，供本地联调和测试。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app import settings
from app.modules.charges.models import EncounterCharge
from app.modules.drug.models import Drug
from app.modules.encounter.models import Encounter, PrescriptionItem
from app.modules.patient.models import Patient
from app.modules.registration.models import Registration

INFNO_VISIT = "2203"
INFNO_DETAIL = "2204"
INFNO_PRE_SETTLE = "2206"
INFNO_SETTLE = "2207"
INFNO_CANCEL_SETTLE = "2208"
SUPPORTED = {INFNO_VISIT, INFNO_DETAIL, INFNO_PRE_SETTLE, INFNO_SETTLE, INFNO_CANCEL_SETTLE}


class NationalInsuranceNotConfigured(RuntimeError):
    """真实医保网关未配置。"""


@dataclass(frozen=True)
class NationalConfig:
    url: str
    token: str
    org_code: str
    region_code: str
    operator: str
    mock: bool

    @property
    def configured(self) -> bool:
        return bool(self.url and self.org_code and self.region_code)


def config(db=None) -> NationalConfig:
    def _get(name: str, fallback: str = "") -> str:
        return str(getattr(settings, name, "") or fallback).strip()

    values = None
    if db is not None:
        from app.modules.admin.institution import load as load_institution

        values = load_institution(db)
    return NationalConfig(
        url=(values or {}).get("national_url") or _get("INSURANCE_NATIONAL_URL", _get("INSURANCE_GATEWAY_URL")),
        token=(values or {}).get("national_token") or _get("INSURANCE_NATIONAL_TOKEN", _get("INSURANCE_GATEWAY_TOKEN")),
        org_code=(values or {}).get("national_org_code") or _get("INSURANCE_NATIONAL_ORG_CODE"),
        region_code=(values or {}).get("national_region_code") or _get("INSURANCE_NATIONAL_REGION_CODE"),
        operator=(values or {}).get("national_operator") or _get("INSURANCE_NATIONAL_OPERATOR", "HIS"),
        mock=bool((values or {}).get("national_mock") or getattr(settings, "INSURANCE_NATIONAL_MOCK", False)),
    )


def build_envelope(infno: str, input_data: dict, db=None) -> dict:
    """构造国家医保平台通用输入报文（加密/签名留出适配点）。"""
    cfg = config(db)
    if infno not in SUPPORTED:
        raise ValueError(f"不支持的医保交易 {infno}")
    return {
        "infno": infno,
        "msgid": uuid.uuid4().hex,
        "mdtrtarea_admvs": cfg.region_code,
        "insuplc_admdvs": cfg.region_code,
        "recer_sys_code": "HIS",
        "infver": "V1.0",
        "opter_no": cfg.operator,
        "signtype": "SM2",
        "dev_no": "",
        "dev_safe_info": "",
        "cert": "",
        # 真实平台需按当地规范对 input 做 SM4 加密并 SM2 签名；此处保留明文模板。
        "input": input_data,
    }


def _mock_response(infno: str, data: dict) -> dict:
    total = float(data.get("medfee_sumamt") or 0)
    fund = round(total * 0.7, 2)
    psn = round(total - fund, 2)
    setl_id = f"MOCK{datetime.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:6].upper()}"
    return {
        "infcode": 0,
        "infmsg": "mock",
        "output": {
            "setlinfo": {
                "setl_id": setl_id,
                "medfee_sumamt": round(total, 2),
                "fund_pay_sumamt": fund,
                "psn_pay": psn,
                "acct_pay": 0,
                "cash_payamt": psn,
                "med_type": data.get("med_type", "11"),
            },
            "setldetail": [
                {"fund_pay_type": "310", "fund_pay_sumamt": fund, "psn_pay": psn}
            ],
        },
        "mock": True,
    }


def _post(envelope: dict, db=None) -> dict:
    cfg = config(db)
    if not cfg.configured:
        raise NationalInsuranceNotConfigured(
            "未配置医保国家平台网关（URL/机构编码/区域编码）"
        )
    import urllib.request

    request = urllib.request.Request(
        cfg.url,
        data=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {cfg.token}" if cfg.token else "",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise NationalInsuranceNotConfigured(f"医保平台调用失败：{exc}") from exc
    if not isinstance(body, dict):
        raise NationalInsuranceNotConfigured("医保平台响应不是 JSON 对象")
    return body


def call(infno: str, input_data: dict, db=None) -> dict:
    cfg = config(db)
    envelope = build_envelope(infno, input_data, db)
    if cfg.configured:
        return _post(envelope, db)
    if cfg.mock:
        return _mock_response(infno, input_data)
    raise NationalInsuranceNotConfigured(
        "未配置医保国家平台网关；可设置 insurance_national_mock 做本地联调"
    )


def _patient_payload(patient: Patient) -> dict:
    return {
        "psn_no": patient.id_number or f"P{patient.id}",
        "psn_name": patient.name,
        "gend": {"male": "1", "female": "2"}.get(patient.gender, "0"),
        "brdy": patient.birth_date.isoformat() if patient.birth_date else "",
        "tel": patient.phone or "",
        "certno": patient.id_number or "",
    }


def _visit_payload(encounter: Encounter, patient: Patient, registration: Registration) -> dict:
    diagnoses = []
    if encounter.diagnosis:
        diagnoses.append({
            "diag_type": "1",
            "diag_code": encounter.diagnosis_code or "",
            "diag_name": encounter.diagnosis,
        })
    return {
        "mdtrt_id": f"E{encounter.id}",
        "psn_no": patient.id_number or f"P{patient.id}",
        "med_type": "11",
        "begntime": encounter.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "endtime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "diaginfo": diagnoses,
        "reg_no": str(registration.id),
    }


def _detail_payload(db: Session, encounter: Encounter, patient: Patient) -> list[dict]:
    rows = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.encounter_id == encounter.id)
        .all()
    )
    details = []
    for item in rows:
        drug: Drug | None = item.drug
        details.append({
            "mdtrt_id": f"E{encounter.id}",
            "psn_no": patient.id_number or f"P{patient.id}",
            "chrg_bchno": f"C{encounter.id}",
            "fee_ocur_time": item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "med_list_code": (drug.insurance_code if drug and drug.insurance_code else ""),
            "medins_list_code": (drug.insurance_code if drug and drug.insurance_code else str(item.drug_id)),
            "medins_list_name": item.drug_name,
            "det_item_fee_sumamt": round(item.unit_price * item.quantity, 2),
            "cnt": item.quantity,
            "pric": item.unit_price,
            "bilg_dept_codg": "",
            "bilg_dr_codg": "",
        })
    return details


def outpatient_payload(db: Session, encounter_id: int) -> tuple[dict, dict]:
    encounter = db.get(Encounter, encounter_id)
    if not encounter:
        raise ValueError("就诊记录不存在")
    registration = db.get(Registration, encounter.registration_id)
    patient = db.get(Patient, registration.patient_id) if registration else None
    if not registration or not patient:
        raise ValueError("就诊缺少挂号/患者信息")
    details = _detail_payload(db, encounter, patient)
    total = round(sum(row["det_item_fee_sumamt"] for row in details), 2)
    return _patient_payload(patient), {
        **_visit_payload(encounter, patient, registration),
        "chrg_bchno": f"C{encounter.id}",
        "medfee_sumamt": total,
        "feedetail": details,
        "setl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def pre_settle(db: Session, encounter_id: int, operator: str = "") -> dict:
    patient, data = outpatient_payload(db, encounter_id)
    response = call(INFNO_PRE_SETTLE, {"data": {**patient, **data}}, db)
    _record(db, encounter_id, INFNO_PRE_SETTLE, data, response, operator)
    return response


def settle(db: Session, encounter_id: int, operator: str = "", setl_id: str = "") -> dict:
    patient, data = outpatient_payload(db, encounter_id)
    if setl_id:
        data["setl_id"] = setl_id
    response = call(INFNO_SETTLE, {"data": {**patient, **data}}, db)
    _record(db, encounter_id, INFNO_SETTLE, data, response, operator)
    return response


def cancel_settle(db: Session, encounter_id: int, setl_id: str, operator: str = "") -> dict:
    response = call(INFNO_CANCEL_SETTLE, {"data": {"setl_id": setl_id}}, db)
    _record(db, encounter_id, INFNO_CANCEL_SETTLE, {"setl_id": setl_id}, response, operator)
    return response


def _record(db: Session, encounter_id: int, infno: str, request: dict, response: dict, operator: str) -> None:
    from .models import InsuranceTransaction

    output = response.get("output") or {}
    setl = output.get("setlinfo") or {}
    row = InsuranceTransaction(
        encounter_id=encounter_id,
        kind=f"national_{infno}",
        result="success" if response.get("infcode") == 0 else "failed",
        message=str(response.get("infmsg") or "")[:300],
        settlement_no=str(setl.get("setl_id") or ""),
        operator=operator,
        infno=infno,
        trade_no=str(response.get("msgid") or ""),
        request_json=json.dumps(request, ensure_ascii=False),
        response_json=json.dumps(response, ensure_ascii=False),
        status="success" if response.get("infcode") == 0 else "failed",
        mode="mock" if response.get("mock") else "gateway",
    )
    db.add(row)
    db.commit()
