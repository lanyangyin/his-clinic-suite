"""打印模板预览：全部单据使用演示数据渲染，不依赖真实就诊记录。"""
from datetime import datetime
from html import escape
import re
from types import SimpleNamespace

from app.modules.print.documents import (
    _clinic_meta,
    _html,
    _logo_html,
    _profile,
    apply_print_profile,
    render_full_set,
    render_imaging_report,
    render_record,
    render_tcm,
    render_western,
)

DOCUMENTS = [
    ("full", "病历 + 处方全套", "门诊病历、西药处方、中药处方一次打印", 1200),
    ("record", "门诊病历", "结构化病历、诊断、医师签名", 900),
    ("western", "西药处方笺", "西药/中成药处方、用法用量、审核栏", 900),
    ("tcm", "中药处方笺", "中药饮片、煎法、付数", 900),
    ("prescription-header", "单张处方笺", "按处方头打印的单张处方", 900),
    ("receipt", "收费收据", "费用明细、医保/自费、支付方式", 760),
    ("retail", "零售小票", "药房非医保零售", 620),
    ("dispense-slip", "取药凭证 / 取药单", "取药号、窗口、药品核对清单、用药指导", 900),
    ("dispense-label", "发药袋标签", "患者、药品、用法、发药人", 620),
    ("nursing-label", "输液/注射瓶签", "座位、药品、溶媒、核对人", 620),
    ("lab-report", "检验报告单", "检验结果、参考范围、危急值、审核", 760),
    ("imaging-report", "检查报告单", "影像/检查所见、意见、审核", 760),
]


def _payment():
    return SimpleNamespace(
        id=900001, invoice_no="INV-DEMO-0001", amount=86.50,
        insurance_amount=30.00, self_pay_amount=56.50, discount_amount=0.0,
        discount_reason="", channel="mixed", status="paid",
        created_at=datetime.now(),
        allocations=[SimpleNamespace(channel="微信支付", amount=56.50)],
        refunded_amount=0.0, net_amount=86.50,
    )


def _patient():
    return SimpleNamespace(
        name="演示患者", gender="male", age=36, patient_no="P900001",
        id_number="110101199001019999", phone="13800000000",
        allergy_label="无过敏史", special_history="高血压 5 年",
    )


def sample_data() -> dict:
    patient = _patient()
    payment = _payment()
    encounter = SimpleNamespace(
        id=900001, diagnosis="上呼吸道感染", diagnosis_code="J06.9",
        created_at=datetime.now(), registration_id=1,
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
        signed_by="演示医生", signed_at=datetime.now(),
    )
    lines = [
        {"name": "阿莫西林胶囊", "spec": "0.25g", "unit": "粒", "qty": 12,
         "price": 1.25, "amount": 15.0, "usage": "口服 每次2粒 每日3次"},
        {"name": "复方甘草片", "spec": "100片", "unit": "片", "qty": 9,
         "price": 0.50, "amount": 4.5, "usage": "口服 每次3片 每日3次"},
    ]
    charges = [
        {"name": "诊查费", "qty": 1, "price": 20.0, "amount": 20.0},
        {"name": "阿莫西林胶囊", "qty": 12, "price": 1.25, "amount": 15.0},
        {"name": "血常规", "qty": 1, "price": 25.0, "amount": 25.0},
    ]
    return {
        "encounter": encounter,
        "record": record,
        "patient": patient,
        "patient_name": patient.name,
        "patient_gender": "男",
        "patient_age": 36,
        "patient_id_number": patient.id_number,
        "patient_address": "演示地址 1 号",
        "patient_phone": patient.phone,
        "allergy": "无",
        "special_history": "无",
        "department_name": "全科",
        "doctor_name": "演示医生",
        "record_no": "BL202611250001",
        "visit_date": datetime.now().strftime("%Y-%m-%d"),
        "diagnoses": [{"diagnosis_code": "J06.9", "diagnosis": "上呼吸道感染",
                       "diagnosis_type": "primary", "note": "", "sort_no": 0}],
        "lines": lines,
        "tcm": [{"formula_name": "演示方", "prescription_no": "TCM-DEMO-001", "packs": 3,
                 "decoct_service": "decoct", "decoction_method": "常规煎煮",
                 "status": "pending", "items": [
                     {"name": "金银花", "dose": 10, "special": "none"},
                     {"name": "连翘", "dose": 10, "special": "none"},
                 ]}],
        "aux_exams": [{"type": "检验", "name": "血常规", "result": "WBC 11.2×10^9/L",
                       "critical": False, "date": datetime.now().strftime("%Y-%m-%d")}],
        "total": 44.5,
        "prescription_no": "RX900001",
        "prescription_status": "pending_review",
        "signature": {"signed": True, "signed_by": "演示医生",
                      "signed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                      "verify_code": "DEMO123456"},
        "payment": payment,
        "charges": charges,
        "pickup_code": "Q900001",
        "sale": SimpleNamespace(
            id=900001, sale_no="LS-DEMO-0001", customer_name="散客",
            channel="cash", status="completed", total_amount=22.5,
            sold_by="演示药师", created_at=datetime.now(),
            items=[SimpleNamespace(name="维生素C片", quantity=1, unit_price=12.5, amount=12.5),
                   SimpleNamespace(name="口罩", quantity=2, unit_price=5.0, amount=10.0)],
        ),
        "dispense": {
            "encounter_id": encounter.id, "patient": patient, "department": "全科",
            "doctor_name": "演示医生", "settled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "valid_until": datetime.now().strftime("%Y-%m-%d"),
            "pharmacy_name": "门诊药房", "window_no": "2号窗", "queue_no": "A012",
            "waiting_count": 3, "prescription_count": 1, "diagnosis": encounter.diagnosis,
            "items": [{"drug_name": line["name"], "spec": line["spec"], "dosage_form": "胶囊",
                       "quantity": line["qty"], "unit": line["unit"], "amount": line["amount"],
                       "usage": line["usage"], "batch_no": "B20261101", "expiry": "2028-10-31"}
                      for line in lines],
            "tcm_prescriptions": [], "signatures": {"doctor": "演示医生", "dispenser": "演示药师",
                                                      "checker": "演示药师", "receiver": "本人"},
            "dispensed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tips": ["请按用法用量服药", "3 天后复诊"], "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "dispense_label": {
            "patient": patient, "encounter_id": encounter.id,
            "receiver_name": "本人", "verified_by": "演示药师",
            "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "items": [{"drug_name": line["name"], "quantity": line["qty"], "usage": line["usage"]}
                      for line in lines],
        },
        "nursing_label": {
            "patient": patient, "seat_no": "A-03", "order_id": encounter.id,
            "item_name": "0.9% 氯化钠注射液 100ml + 头孢曲松 2g",
            "dosage": "2g", "route": "静脉滴注", "frequency": "每日1次",
            "solvent": "0.9% 氯化钠注射液 100ml", "batch_no": "S20261101",
            "prepared_by": "演示护士", "checked_by": "演示护士",
        },
        "imaging_report": {
            "patient_name": patient.name, "encounter_id": encounter.id,
            "diagnosis": encounter.diagnosis, "doctor_name": "演示医生",
            "report_no": "IMG-DEMO-0001", "item_name": "胸部正位片",
            "body_part": "胸部", "status": "已报告",
            "findings": "双肺纹理清晰，未见明显实变。",
            "impression": "胸部正位片未见明显异常。",
            "image_url": "", "reported_by": "演示影像医师",
            "reviewed_by": "演示审核医师",
            "reported_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "lab_report": {
            "patient": patient, "encounter_id": encounter.id, "diagnosis": encounter.diagnosis,
            "doctor_name": "演示医生", "report_no": "LAB-DEMO-0001",
            "specimen_no": "S900001", "specimen_type": "静脉血",
            "item_name": "白细胞计数", "result": "11.2", "unit": "×10^9/L",
            "reference": "3.5 – 9.5", "flag": "↑ 偏高",
            "critical": False, "critical_note": "", "critical_notified_to": "",
            "testing_by": "演示检验师", "reviewed_by": "演示审核师",
            "status": "已审核", "reported_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    }


def _table(rows: list[list[str]], headers: list[str]) -> str:
    head = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<table class='info' style='width:100%;border-collapse:collapse' border='1'><tr>{head}</tr>{body}</table>"


def _receipt(data: dict, profile: dict) -> str:
    meta = _clinic_meta(profile)
    payment = data["payment"]
    rows = [[line["name"], f"{line['qty']}×{line['price']:.2f}", f"{line['amount']:.2f}"] for line in data["charges"]]
    body = f"""
<h2>{escape(meta['name'])}</h2>
<p style='text-align:center'>收费收据</p>
<hr>
<p>患者：{escape(data['patient'].name)}</p>
<p>单号：{payment.id}　票据号：{escape(payment.invoice_no)}</p>
<p>取药码：{escape(data['pickup_code'])}</p>
<p>日期：{payment.created_at:%Y-%m-%d %H:%M}</p>
<hr>
{_table(rows, ['项目', '数量×单价', '金额'])}
<hr>
<p style='text-align:right'>应收：{payment.amount:.2f} 元</p>
<p style='text-align:right'>医保支付：{payment.insurance_amount:.2f} 元</p>
<p style='text-align:right'>自费：{payment.self_pay_amount:.2f} 元</p>
<p style='text-align:right'>支付方式：混合支付</p>
<p style='text-align:center'>打印时间：{datetime.now():%Y-%m-%d %H:%M}</p>
"""
    return _html(body, "收费收据", profile)


def _retail(data: dict, profile: dict) -> str:
    meta = _clinic_meta(profile)
    sale = data["sale"]
    rows = [[i.name, f"{i.quantity}×{i.unit_price:.2f}", f"{i.amount:.2f}"] for i in sale.items]
    body = f"""
<h2>{escape(meta['name'])}</h2>
<p style='text-align:center'>零售小票</p><hr>
<p>单号：{escape(sale.sale_no)}　日期：{sale.created_at:%Y-%m-%d %H:%M}</p>
<p>顾客：{escape(sale.customer_name)}</p><hr>
{_table(rows, ['商品', '数量×单价', '金额'])}
<hr><p style='text-align:right'>合计：{sale.total_amount:.2f} 元</p>
<p style='text-align:right'>销售员：{escape(sale.sold_by)}</p>
<p style='text-align:center'>非医保零售，请保留小票</p>
"""
    return _html(body, "零售小票", profile)


def _dispense_slip(data: dict, profile: dict) -> str:
    d = data["dispense"]
    rows = [[i["drug_name"], f"{i['quantity']}{i['unit']}", f"{i['amount']:.2f}", i["usage"]] for i in d["items"]]
    body = f"""
<h2>{escape(_clinic_meta(profile)['name'])}</h2>
<p style='text-align:center'>取药凭证</p>
<hr>
<p>患者：{escape(d['patient'].name)}　{d['patient'].age}岁　就诊卡：{escape(str(d['patient'].patient_no))}</p>
<p>科室：{escape(d['department'])}　医生：{escape(d['doctor_name'])}</p>
<p>结算时间：{escape(d['settled_at'])}　有效期：{escape(d['valid_until'])}</p>
<hr><p><b>取药指引</b></p>
<p>药房：{escape(d['pharmacy_name'])}　窗口：{escape(d['window_no'])}　取药号：<b>{escape(d['queue_no'])}</b></p>
<p>当前等待 {d['waiting_count']} 人　共 {d['prescription_count']} 张处方</p>
<p>临床诊断：{escape(d['diagnosis'])}</p>
{_table(rows, ['药品', '数量', '金额', '用法用量'])}
<p style='text-align:right'>药品合计：{sum(i['amount'] for i in d['items']):.2f} 元</p>
<hr>
<p>医师：{escape(d['signatures']['doctor'])}　调配药师：{escape(d['signatures']['dispenser'])}　核对药师：{escape(d['signatures']['checker'])}</p>
<p>取药人：{escape(d['signatures']['receiver'])}　发药时间：{escape(d['dispensed_at'])}</p>
<p style='font-size:11px'>{'　'.join(escape(t) for t in d['tips'])}</p>
"""
    return _html(body, "取药凭证", profile)


def _dispense_label(data: dict, profile: dict) -> str:
    d = data["dispense_label"]
    rows = [[i["drug_name"], str(i["quantity"]), i["usage"]] for i in d["items"]]
    body = f"""
<h2>{escape(_clinic_meta(profile)['name'])}</h2>
<p style='text-align:center'>发药袋标签</p><hr>
<p>患者：{escape(d['patient'].name)}　男/36岁　就诊：{d['encounter_id']}</p>
<p>取药人：{escape(d['receiver_name'])}</p><hr>
{_table(rows, ['药品', '数量', '用法'])}
<hr><p>发药人：{escape(d['verified_by'])}　时间：{escape(d['verified_at'])}</p>
<p style='text-align:center'>请核对姓名、药名、用法</p>
"""
    return _html(body, "发药袋标签", profile)


def _nursing_label(data: dict, profile: dict) -> str:
    d = data["nursing_label"]
    body = f"""
<h2>{escape(_clinic_meta(profile)['name'])}</h2>
<p style='text-align:center'>输液 / 注射瓶签</p><hr>
<p>患者：{escape(d['patient'].name)}　男/36岁</p>
<p>座位：{escape(d['seat_no'])}　执行单：{d['order_id']}</p><hr>
<p><b>药品：{escape(d['item_name'])}</b></p>
<p>剂量：{escape(d['dosage'])}　途径：{escape(d['route'])}　频次：{escape(d['frequency'])}</p>
<p>溶媒：{escape(d['solvent'])}　批号：{escape(d['batch_no'])}</p>
<p>配药：{escape(d['prepared_by'])}　核对：{escape(d['checked_by'])}</p>
<hr><p style='text-align:center'>执行前请核对患者姓名、药名、剂量、途径、时间</p>
"""
    return _html(body, "输液/注射瓶签", profile)


def _lab_report(data: dict, profile: dict) -> str:
    d = data["lab_report"]
    critical = (
        f"<p style='color:#b91c1c'>危急值：{escape(d['critical_note'])}　已通知：{escape(d['critical_notified_to'])}</p>"
        if d.get("critical") else ""
    )
    body = f"""
<h2>{escape(_clinic_meta(profile)['name'])} · 检验报告单</h2>
<p>患者：{escape(d['patient'].name)}　报告号：{escape(d['report_no'])}</p>
<p>就诊：{d['encounter_id']}　诊断：{escape(d['diagnosis'])}　医生：{escape(d['doctor_name'])}</p>
<p>标本号：{escape(d['specimen_no'])}　标本：{escape(d['specimen_type'])}</p>
{_table([[d['item_name'], d['result'], d['unit'], d['reference'], d['flag']]],
        ['项目', '结果', '单位', '参考范围', '异常'])}
{critical}
<p>检验者：{escape(d['testing_by'])}　审核者：{escape(d['reviewed_by'])}　状态：{escape(d['status'])}</p>
<p style='text-align:right'>报告时间：{escape(d['reported_at'])}　审核时间：{escape(d['reviewed_at'])}</p>
<p style='text-align:center'>本报告仅对送检标本负责</p>
"""
    return _html(body, "检验报告单", profile)


def _prescription_header(data: dict, profile: dict) -> str:
    rows = [[line["name"], line["spec"], str(line["qty"]), line["usage"]] for line in data["lines"]]
    body = f"""
<h2>{escape(_clinic_meta(profile)['name'])}</h2>
<p style='text-align:center'>处方笺</p><hr>
<p>患者：{escape(data['patient_name'])}　{escape(data['patient_gender'])}/{data['patient_age']}岁</p>
<p>诊断：{escape(data['encounter'].diagnosis)}　处方号：{escape(data['prescription_no'])}</p>
{_table(rows, ['药品', '规格', '数量', '用法'])}
<hr><p style='text-align:right'>医师：演示医生　审核药师：演示药师</p>
"""
    return _html(body, "处方笺", profile)


def _add_profile_notes(html: str, profile: dict) -> str:
    header = str(profile.get("header_note") or "").strip()
    footer = str(profile.get("footer_note") or "").strip()
    logo = _logo_html(profile)
    if logo and "clinic-logo" not in html:
        html = re.sub(r"(<h2[^>]*>)", logo + r"\1", html, count=1)
    if header and escape(header) not in html:
        html = re.sub(r"(</h2>)", r"\1" + f'<div class="header-note">{escape(header)}</div>', html, count=1)
    if footer and escape(footer) not in html:
        html = html.replace("</body>", f'<div class="footer-note">{escape(footer)}</div>\n</body>', 1)
    return html


def render(kind: str, profile: dict | None = None) -> str:
    data = sample_data()
    p = _profile(profile)
    if kind == "record":
        return render_record(data, profile)
    if kind == "western":
        return render_western(data, profile)
    if kind == "tcm":
        return render_tcm(data, profile)
    if kind == "full":
        return render_full_set(data, profile)
    if kind == "prescription-header":
        return _add_profile_notes(_prescription_header(data, p), p)
    if kind == "receipt":
        return _add_profile_notes(_receipt(data, p), p)
    if kind == "retail":
        return _add_profile_notes(_retail(data, p), p)
    if kind == "dispense-slip":
        return _add_profile_notes(_dispense_slip(data, p), p)
    if kind == "dispense-label":
        return _add_profile_notes(_dispense_label(data, p), p)
    if kind == "nursing-label":
        return _add_profile_notes(_nursing_label(data, p), p)
    if kind == "lab-report":
        return _add_profile_notes(_lab_report(data, p), p)
    if kind == "imaging-report":
        return render_imaging_report(data["imaging_report"], p)
    raise ValueError("未知打印模板")
