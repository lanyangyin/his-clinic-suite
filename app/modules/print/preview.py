"""打印模板预览：使用演示数据渲染所有主模板，不需要真实就诊记录。"""
from datetime import datetime
from types import SimpleNamespace

from app.modules.print.documents import (
    render_full_set,
    render_record,
    render_tcm,
    render_western,
)


def sample_data() -> dict:
    encounter = SimpleNamespace(
        id=900001,
        diagnosis="上呼吸道感染",
        diagnosis_code="J06.9",
        created_at=datetime.now(),
        registration_id=1,
    )
    record = SimpleNamespace(
        chief_complaint="发热、咳嗽 3 天",
        present_illness="受凉后发热，最高 38.5℃，伴咽痛、咳嗽。",
        past_history="否认高血压、糖尿病。",
        personal_history="无吸烟饮酒史。",
        marital_history="已婚。",
        family_history="否认家族遗传病史。",
        physical_exam="咽充血，双肺呼吸音清，未闻及干湿啰音。",
        auxiliary_exam="血常规：WBC 11.2×10^9/L。",
        treatment_advice="多饮水，按医嘱服药，3 天后复诊。",
        signed_by="演示医生",
        signed_at=datetime.now(),
    )
    return {
        "encounter": encounter,
        "record": record,
        "patient_name": "演示患者",
        "patient_gender": "男",
        "patient_age": 36,
        "patient_address": "演示地址 1 号",
        "patient_phone": "13800000000",
        "allergy": "无",
        "special_history": "无",
        "department_name": "全科",
        "doctor_name": "演示医生",
        "record_no": "BL202611250001",
        "visit_date": datetime.now().strftime("%Y-%m-%d"),
        "record": record,
        "diagnoses": [
            {"diagnosis_code": "J06.9", "diagnosis": "上呼吸道感染",
             "diagnosis_type": "primary", "note": "", "sort_no": 0},
        ],
        "lines": [
            {"name": "阿莫西林胶囊", "spec": "0.25g", "unit": "粒", "qty": 12,
             "price": 1.25, "amount": 15.0, "usage": "口服 每次2粒 每日3次"},
        ],
        "tcm": [
            {"formula_name": "演示方", "prescription_no": "TCM-DEMO-001", "packs": 3,
             "decoct_service": "decoct", "decoction_method": "常规煎煮",
             "status": "pending", "items": [
                 {"name": "金银花", "dose": 10, "special": "none"},
                 {"name": "连翘", "dose": 10, "special": "none"},
             ]},
        ],
        "aux_exams": [
            {"type": "检验", "name": "血常规", "result": "WBC 11.2×10^9/L",
             "critical": False, "date": datetime.now().strftime("%Y-%m-%d")},
        ],
        "total": 30.0,
        "prescription_no": "RX900001",
        "prescription_status": "pending_review",
        "signature": {"signed": True, "signed_by": "演示医生",
                      "signed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                      "verify_code": "DEMO123456"},
    }


def render(kind: str, profile: dict | None = None) -> str:
    data = sample_data()
    if kind == "record":
        return render_record(data, profile)
    if kind == "western":
        return render_western(data, profile)
    if kind == "tcm":
        return render_tcm(data, profile)
    if kind == "full":
        return render_full_set(data, profile)
    raise ValueError("未知打印模板")
