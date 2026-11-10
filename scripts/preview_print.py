"""生成门诊病历/处方笺打印预览（真实接口数据）。

产出：
- docs/打印预览_门诊病历处方.html
- docs/打印预览_门诊病历处方.pdf
- docs/screenshots/print_preview.png
"""
import base64
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8001"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def auth(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def main() -> int:
    admin = auth("admin", "admin123")
    cashier = auth("cashier", "cashier123")
    doctor = auth("doctor", "doctor123")
    suffix = datetime.now().strftime("%H%M%S")

    patient = requests.post(
        f"{BASE}/patients/",
        headers=cashier,
        json={
            "name": "何燕琼",
            "gender": "female",
            "birth_date": "1974-05-20",
            "id_number": f"11010119740520{suffix[-4:]}",
            "phone": "13678970575",
            "address": "演示地址",
            "allergy_status": "unknown",
            "privacy_consent": True,
        },
        timeout=30,
    ).json()
    dept = requests.post(
        f"{BASE}/departments/", headers=admin, json={"name": "中西医结合科"}, timeout=30
    ).json()
    doctor_row = requests.post(
        f"{BASE}/doctors/",
        headers=admin,
        json={"name": "李德珍", "department_id": dept["id"]},
        timeout=30,
    ).json()
    reg = requests.post(
        f"{BASE}/registrations/",
        headers=cashier,
        json={"patient_id": patient["id"], "doctor_id": doctor_row["id"]},
        timeout=30,
    ).json()
    encounter = requests.post(
        f"{BASE}/encounters/",
        headers=doctor,
        json={"registration_id": reg["id"], "diagnosis": "高脂血症"},
        timeout=30,
    ).json()
    record = requests.post(
        f"{BASE}/encounters/{encounter['id']}/medical-record",
        headers=doctor,
        json={
            "chief_complaint": "血脂异常",
            "present_illness": "2026/7/21 血脂四项甘油三酯 8.25，胆固醇 6.31。",
            "past_history": "无特殊慢性病史。",
            "physical_exam": "",
            "treatment_advice": "病情无缓解或加重时，请速到市人民医院就诊。",
        },
        timeout=30,
    )
    assert record.status_code in (200, 201), record.text

    drug = requests.post(
        f"{BASE}/drugs/",
        headers=admin,
        json={
            "name": "辛伐他汀分散片",
            "spec": "10mg",
            "unit": "片",
            "base_price": 0.5,
            "insurance_ratio": 0.7,
        },
        timeout=30,
    ).json()
    rx = requests.post(
        f"{BASE}/encounters/{encounter['id']}/prescriptions",
        headers=doctor,
        json={
            "drug_id": drug["id"],
            "quantity": 7,
            "dosage": "每次10mg",
            "frequency": "每日一次",
            "route": "口服",
            "days": 7,
        },
        timeout=30,
    )
    assert rx.status_code in (200, 201), rx.text

    herb_names = [
        ("桃仁", 10), ("焦山楂", 10), ("丹参", 10), ("杏仁", 10),
        ("甘草", 6), ("麻黄梢", 6), ("地龙", 10), ("黄芪", 10),
        ("瓜蒌皮", 10), ("杏仁", 10), ("枇杷叶", 10), ("地龙", 10),
        ("前胡", 10), ("紫苏叶", 10), ("炒苏子", 10), ("炒牛蒡子", 10),
    ]
    items = []
    for index, (name, dose) in enumerate(herb_names):
        herb = requests.post(
            f"{BASE}/tcm/herbs",
            headers=admin,
            json={
                "code": f"PRINT-{suffix}-{index}",
                "name": name,
                "price_per_g": 0.1,
                "insurance_code": f"TCM{index:03d}",
            },
            timeout=30,
        ).json()
        items.append({"herb_id": herb["id"], "dose_g": dose})
    tcm = requests.post(
        f"{BASE}/tcm/encounters/{encounter['id']}/prescriptions",
        headers=doctor,
        json={
            "formula_name": "降脂化瘀方",
            "packs": 3,
            "decoct_service": "decoct",
            "decoction_method": "水煎服 每日两次",
            "items": items,
        },
        timeout=30,
    )
    assert tcm.status_code == 201, tcm.text

    lab = auth("lab", "lab123")
    lab_item = requests.post(
        f"{BASE}/lab/items/",
        headers=admin,
        json={"code": f"LIP{suffix[-4:]}", "name": "甘油三酯", "price": 10, "unit": "mmol/L"},
        timeout=30,
    ).json()
    lab_req = requests.post(
        f"{BASE}/lab/encounters/{encounter['id']}/lab-requests",
        headers=doctor,
        json={"item_id": lab_item["id"]},
        timeout=30,
    ).json()
    for action in ("collect", "receive", "start"):
        assert requests.post(
            f"{BASE}/lab/requests/{lab_req['id']}/{action}", headers=lab, timeout=30
        ).status_code == 200
    report = requests.post(
        f"{BASE}/lab/requests/{lab_req['id']}/report",
        headers=lab,
        json={
            "result": "8.25",
            "result_value": 8.25,
            "result_unit": "mmol/L",
            "critical_flag": False,
        },
        timeout=30,
    )
    assert report.status_code == 200, report.text

    page = requests.get(f"{BASE}/print/prescription/{encounter['id']}", timeout=30)
    assert page.status_code == 200
    html_path = ROOT / "docs" / "打印预览_门诊病历处方.html"
    html_path.write_text(page.text, encoding="utf-8")
    print("HTML:", html_path)

    pdf = ROOT / "docs" / "打印预览_门诊病历处方.pdf"
    pdf.unlink(missing_ok=True)
    subprocess.run(
        [
            EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
            f"--user-data-dir={ROOT / 'build' / 'edge-print'}",
            f"--print-to-pdf={pdf}",
            html_path.as_uri(),
        ],
        check=False,
        timeout=60,
    )
    print("PDF:", pdf, pdf.is_file())
    return 0


if __name__ == "__main__":
    sys.exit(main())
