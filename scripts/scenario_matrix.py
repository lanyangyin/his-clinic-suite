"""多患者分流 + 非患者后台路径模拟（可重复运行）。

每个患者只走自己的路径，合起来覆盖不同科室；后台流程单独作为完整路径。
运行：.venv\\Scripts\\python.exe scripts\\scenario_matrix.py
产出：docs/多患者分流模拟报告.md
"""
import base64
import json
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001"
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "多患者分流模拟报告.md"
PATHS: list[dict] = []


class Role:
    def __init__(self, name: str, username: str, password: str):
        self.name = name
        self.username = username
        self.session = requests.Session()
        self.session.trust_env = False
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers["Authorization"] = f"Basic {token}"

    def call(self, method, path, expected=(200, 201), **kwargs):
        response = self.session.request(method, BASE + path, timeout=30, **kwargs)
        if response.status_code not in expected:
            raise RuntimeError(
                f"{self.name} {method} {path} -> {response.status_code}: {response.text[:300]}"
            )
        return response.json() if response.text else {}


def mark(path: str, patient: str, step: str, detail: str = "") -> None:
    PATHS.append(
        {"path": path, "patient": patient, "step": step, "detail": detail, "at": time.time()}
    )
    print(f"[{path}] {patient} · {step}" + (f" · {detail}" if detail else ""), flush=True)


def patient(admin, cashier, doctor, suffix: str, name: str, tag: str = "1"):
    dept = admin.call("POST", "/departments/", json={"name": f"{name}科{suffix}"})
    doc = admin.call(
        "POST", "/doctors/", json={"name": f"{name}医生{suffix}", "department_id": dept["id"]}
    )
    p = cashier.call(
        "POST",
        "/patients/",
        json={
            "name": f"{name}患者{suffix}",
            "id_number": f"1101011996{suffix[-8:-1]}{tag}",
        },
    )
    reg = cashier.call(
        "POST", "/registrations/", json={"patient_id": p["id"], "doctor_id": doc["id"]}
    )
    enc = doctor.call(
        "POST",
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": f"{name}诊断"},
    )
    doctor.call(
        "POST",
        f"/encounters/{enc['id']}/medical-record",
        json={"chief_complaint": "模拟症状", "present_illness": "模拟病程"},
    )
    doctor.call("POST", f"/encounters/{enc['id']}/medical-record/sign")
    return p, doc, reg, enc


def path_a(admin, cashier, doctor, lab, pharmacist, suffix):
    """患者 A：内科开方 + 检验 + 药房发药/退药 + 发票/退费。"""
    name = "A内科"
    p, doc, reg, enc = patient(admin, cashier, doctor, suffix, name, tag="1")
    mark("A 内科-检验-药房-退费", p["name"], "挂号/接诊/病历签名")
    drug = admin.call(
        "POST", "/drugs/", json={"name": f"A药{suffix}", "base_price": 12.0}
    )
    lab_item = admin.call(
        "POST", "/lab/items/", json={"code": f"LA{suffix[-6:]}", "name": f"血常规{suffix}", "price": 20}
    )
    pharmacist.call(
        "POST", "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": f"PA-{suffix}", "expiry": "2027-12-31", "quantity": 20},
    )
    rx = doctor.call(
        "POST", f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
    )
    lab_req = doctor.call(
        "POST", f"/lab/encounters/{enc['id']}/lab-requests", json={"item_id": lab_item["id"]}
    )
    mark("A 内科-检验-药房-退费", p["name"], "处方+检验申请", f"处方{rx['id']} 检验{lab_req['id']}")
    payment = cashier.call(
        "POST", "/payments/", json={"encounter_id": enc["id"], "channel": "cash"}
    )
    assert payment["status"] == "paid"
    mark("A 内科-检验-药房-退费", p["name"], "收费完成", f"{payment['amount']:.2f}")
    lab.call("POST", f"/lab/requests/{lab_req['id']}/collect")
    lab.call("POST", f"/lab/requests/{lab_req['id']}/receive")
    lab.call("POST", f"/lab/requests/{lab_req['id']}/start")
    lab.call(
        "POST", f"/lab/requests/{lab_req['id']}/report",
        json={"result": "WBC 6.1×10^9/L"},
    )
    reviewed = lab.call("POST", f"/lab/requests/{lab_req['id']}/review")
    assert reviewed["status"] in ("reported", "reviewed")
    mark("A 内科-检验-药房-退费", p["name"], "检验采样/签收/报告/审核")
    dispense = pharmacist.call(
        "POST", "/pharmacy/dispense",
        json={"encounter_id": enc["id"], "receiver_name": p["name"], "receiver_relation": "本人"},
    )
    mark("A 内科-检验-药房-退费", p["name"], "药房签字发药", f"发药{dispense['id']}")
    pharmacist.call("POST", f"/pharmacy/dispense/{dispense['id']}/return")
    mark("A 内科-检验-药房-退费", p["name"], "退药（库存回补）")
    invoice = cashier.call("POST", f"/invoices/payments/{payment['id']}/print")
    assert invoice["print_count"] >= 1
    voided = cashier.call(
        "POST", f"/invoices/payments/{payment['id']}/void", json={"reason": "模拟作废"}
    )
    assert voided["invoice_status"] == "void"
    refunded = cashier.call("POST", f"/payments/{payment['id']}/refund")
    assert refunded["status"] == "refunded"
    mark("A 内科-检验-药房-退费", p["name"], "发票作废/整单退费")
    return {"patient_id": p["id"], "encounter_id": enc["id"], "payment_id": payment["id"]}


def path_b(admin, cashier, doctor, treatment, suffix):
    """患者 B：治疗室清创 + 套餐耗材 + 换药随访。"""
    name = "B外科"
    p, doc, reg, enc = patient(admin, cashier, doctor, suffix, name, tag="2")
    charge = admin.call(
        "POST", "/charges/items/",
        json={"code": f"TB{suffix[-6:]}", "name": f"清创{suffix}", "category": "treatment", "price": 80},
    )
    material = admin.call(
        "POST", "/materials/items/",
        json={"code": f"MB{suffix[-6:]}", "name": f"清创包{suffix}", "unit": "个", "price": 10, "category": "consumable"},
    )
    admin.call(
        "POST", "/materials/stock-in",
        json={"item_id": material["id"], "warehouse": "总库", "quantity": 10},
    )
    admin.call(
        "PUT", "/treatment-room/templates/debridement",
        json={
            "charge_item_id": charge["id"], "price": 80,
            "materials": [{"material_id": material["id"], "quantity": 1, "warehouse": "总库"}],
            "active": True,
        },
    )
    case = treatment.call(
        "POST", "/treatment-room/cases",
        json={
            "patient_id": p["id"], "encounter_id": enc["id"],
            "procedure_name": "清创缝合", "template_code": "debridement",
            "template_data": {"site": "右手掌", "size": "3cm"},
        },
    )
    payment = cashier.call(
        "POST", "/payments/", json={"encounter_id": enc["id"], "channel": "cash"}
    )
    assert payment["status"] == "paid"
    started = treatment.call(
        "POST", f"/treatment-room/cases/{case['id']}/start",
        json={"consent": True, "anesthesia": "局麻", "findings": "3cm 裂伤"},
    )
    assert started["kit_applied"] is True
    completed = treatment.call(
        "POST", f"/treatment-room/cases/{case['id']}/complete",
        json={"procedure_detail": "清创缝合 3 针", "sutures": "3-0 丝线 3 针", "dressing": "无菌敷料"},
    )
    assert completed["status"] == "completed"
    followups = treatment.call("GET", "/treatment-room/follow-ups?status=pending")
    followup = next(row for row in followups if row["case_id"] == case["id"])
    followup_done = treatment.call(
        "POST", f"/treatment-room/follow-ups/{followup['id']}/complete",
        json={"result_note": "创面干燥", "healing_score": 8, "next_due_date": (date.today() + timedelta(days=2)).isoformat()},
    )
    assert followup_done["status"] == "completed"
    stock = admin.call("GET", f"/materials/stocks?item_id={material['id']}")
    assert sum(row["quantity"] for row in stock if row["warehouse"] == "总库") == 9
    mark("B 外科-治疗室-耗材-随访", p["name"], "清创/套餐扣耗材/完成/随访", f"病例{case['id']}")
    return {"patient_id": p["id"], "case_id": case["id"], "payment_id": payment["id"]}


def path_c(admin, cashier, doctor, pharmacist, decoction, suffix):
    """患者 C：中医饮片处方 + 中药房 + 煎药全流程。"""
    name = "C中医"
    p, doc, reg, enc = patient(admin, cashier, doctor, suffix, name, tag="3")
    herb = admin.call(
        "POST", "/tcm/herbs",
        json={"code": f"HC{suffix[-6:]}", "name": f"黄芪{suffix}", "price_per_g": 0.2},
    )
    rx = doctor.call(
        "POST", f"/tcm/encounters/{enc['id']}/prescriptions",
        json={
            "formula_name": f"补气方{suffix}", "packs": 3, "decoct_service": "decoct",
            "items": [{"herb_id": herb["id"], "dose_g": 10}],
        },
    )
    payment = cashier.call(
        "POST", "/payments/", json={"encounter_id": enc["id"], "channel": "cash"}
    )
    assert payment["status"] == "paid"
    pharmacist.call("POST", f"/tcm/prescriptions/{rx['id']}/review")
    pharmacist.call("POST", f"/tcm/prescriptions/{rx['id']}/dispense")
    orders = pharmacist.call("GET", "/tcm/decoction-orders")
    order = next(row for row in orders if row["prescription_id"] == rx["id"])
    decoction.call("POST", f"/tcm/decoction-orders/{order['id']}/soak", json={"soak_minutes": 30})
    decoction.call(
        "POST", f"/tcm/decoction-orders/{order['id']}/decoct",
        json={"machine_no": "DEC-1", "decoct_minutes": 40},
    )
    decoction.call(
        "POST", f"/tcm/decoction-orders/{order['id']}/package",
        json={"bags": 6, "bag_volume_ml": 200},
    )
    issued = decoction.call(
        "POST", f"/tcm/decoction-orders/{order['id']}/issue",
        json={"pickup_method": "self", "receiver": p["name"]},
    )
    assert issued["status"] in ("completed", "issued")
    mark("C 中医-中药房-煎药", p["name"], "饮片处方/审核/发药/煎煮/包装/发药", f"煎药单{order['id']}")
    return {"patient_id": p["id"], "prescription_id": rx["id"], "payment_id": payment["id"]}


def path_d(admin, cashier, doctor, nurse, suffix):
    """患者 D：门诊治疗单 → 护士配药/输液执行/观察/完成。"""
    name = "D护理"
    p, doc, reg, enc = patient(admin, cashier, doctor, suffix, name, tag="4")
    item = admin.call(
        "POST", "/charges/items/",
        json={"code": f"ND{suffix[-6:]}", "name": f"静脉输液{suffix}", "category": "treatment", "price": 35},
    )
    doctor.call(
        "POST", f"/treatments/encounters/{enc['id']}",
        json={"item_id": item["id"], "quantity": 1},
    )
    payment = cashier.call(
        "POST", "/payments/", json={"encounter_id": enc["id"], "channel": "cash"}
    )
    orders = nurse.call("POST", f"/nursing/encounters/{enc['id']}/sync")
    order = next(row for row in orders if row["encounter_id"] == enc["id"])
    nurse.call(
        "POST", f"/nursing/orders/{order['id']}/prepare",
        json={"solvent": "0.9%氯化钠", "dose": "1 支", "checked_by": "nurse"},
    )
    nurse.call(
        "POST", f"/nursing/orders/{order['id']}/start",
        json={"seat_no": "A1", "rate_ml_h": 60},
    )
    nurse.call(
        "POST", f"/nursing/orders/{order['id']}/observe",
        json={"rate_ml_h": 60, "note": "无不适", "adverse_reaction": ""},
    )
    done = nurse.call(
        "POST", f"/nursing/orders/{order['id']}/complete",
        json={"note": "输液完成", "adverse_reaction": ""},
    )
    assert done["status"] == "completed", done
    mark("D 护理-输液执行", p["name"], "治疗单/配药/穿刺/观察/完成", f"护理单{order['id']}")
    return {"patient_id": p["id"], "nursing_order_id": order["id"], "payment_id": payment["id"]}


def path_e(admin, cashier, doctor, archive, suffix):
    """患者 E：病案建档 → 归档 → 借阅/归还 → 复印 → 封存/启封。"""
    name = "E病案"
    p, doc, reg, enc = patient(admin, cashier, doctor, suffix, name, tag="5")
    record = archive.call(
        "POST", "/archive/records",
        json={"patient_id": p["id"], "encounter_id": enc["id"]},
    )
    archived = archive.call(
        "POST", f"/archive/records/{record['id']}/archive",
        json={"storage_location": f"E-{suffix[-4:]}", "page_count": 18, "completeness": "complete"},
    )
    assert archived["status"] == "archived"
    borrowing = archive.call(
        "POST", f"/archive/records/{record['id']}/borrow",
        json={"borrower": "质控科", "department": "质控", "due_days": 7},
    )
    archive.call("POST", f"/archive/borrowings/{borrowing['id']}/return")
    copy = archive.call(
        "POST", f"/archive/records/{record['id']}/copy",
        json={"applicant": p["name"], "relationship": "本人", "copies": 1},
    )
    archive.call("POST", f"/archive/copies/{copy['id']}/complete", json={"fee": 2})
    seal = archive.call(
        "POST", f"/archive/records/{record['id']}/seal", json={"reason": "模拟封存"}
    )
    unsealed = archive.call(
        "POST", f"/archive/records/{record['id']}/unseal", json={"reason": "模拟启封"}
    )
    assert unsealed["action"] == "unseal"
    record_after = archive.call("GET", f"/archive/records/{record['id']}")
    assert record_after["status"] == "archived"
    mark("E 病案-归档借阅", p["name"], "建档/归档/借阅/归还/复印/封存/启封", f"病案{record['archive_no']}")
    return {"patient_id": p["id"], "archive_id": record["id"]}


def path_n2(admin, cashier, suffix):
    """非患者：医保目录导入/对码、进销存上传、工作台。"""
    code = f"SIM{suffix}"
    csv = (
        "national_code,name,category,spec,unit\n"
        f"{code},医保模拟药{suffix},甲,10mg,盒\n"
    ).encode("utf-8-sig")
    imported = admin.session.post(
        BASE + "/insurance/catalog/import",
        files={"file": (f"catalog_{suffix}.csv", csv, "text/csv")},
        timeout=30,
    )
    assert imported.status_code == 200, imported.text
    drug = admin.call(
        "POST", "/drugs/",
        json={"name": f"医保匹配药{suffix}", "base_price": 15, "insurance_code": code},
    )
    matched = admin.call("POST", "/insurance/catalog/match?only_unmatched=true")
    assert matched["matched"] >= 1
    resolved = admin.call("GET", f"/insurance/catalog/resolve/{drug['id']}")
    assert resolved["insurance_code"] == code
    today = date.today().isoformat()
    upload = admin.call(
        "POST", "/insurance/inventory/upload",
        json={"start_date": today, "end_date": today},
    )
    assert upload["upload_no"]
    workbench = admin.call("GET", "/insurance/workbench")
    assert "matching" in workbench and "drugs" in workbench["matching"]
    mark("N2 医保目录-进销存", "无患者", "目录导入/对码/进销存上传/工作台", f"上传{upload['upload_no']}")
    return {"catalog": code, "drug_id": drug["id"], "upload": upload["upload_no"]}


def path_n3(admin, cashier, suffix):
    """非患者：发票号段 → 收费开班/日结/交班。"""
    batch = admin.call(
        "POST", "/invoices/batches",
        json={"prefix": f"NB{suffix[-4:]}", "start_no": 1, "end_no": 20, "assigned_to": "cashier"},
    )
    shift = next(
        (
            row
            for row in cashier.call("GET", "/cashier/shifts")
            if row["status"] == "open"
        ),
        None,
    )
    if shift is None:
        shift = cashier.call(
            "POST", "/cashier/shifts/open", json={"opening_float": 100}
        )
    daily = cashier.call("GET", "/cashier/daily")
    assert daily["scope"] == "cashier"
    closed = cashier.call(
        "POST", f"/cashier/shifts/{shift['id']}/close",
        json={"counted_cash": 100, "note": "模拟交班"},
    )
    assert closed["status"] == "closed"
    mark("N3 收费-发票-交班", "无患者", "号段/开班/日结/交班", f"号段{batch['prefix']}")
    return {"batch_id": batch["id"], "shift_id": shift["id"]}


def path_n1(admin, warehouse, pharmacist, suffix):
    """非患者：供应商→GSP 验收/温湿度/召回→盘点。"""
    supplier = admin.call(
        "POST", "/suppliers/", json={"code": f"NS{suffix[-6:]}", "name": f"模拟供应商{suffix}"}
    )
    acceptance = pharmacist.call(
        "POST", "/gsp/acceptances",
        json={
            "supplier_id": supplier["id"], "delivery_no": f"NSD-{suffix}", "transport_temp": 22,
            "items": [{"name": f"GSP模拟药{suffix}", "batch_no": f"NG-{suffix}", "quantity": 10}],
        },
    )
    storage = pharmacist.call(
        "POST", "/gsp/storage-logs",
        json={"area": "药房", "temperature": 32, "humidity": 80, "note": "模拟异常"},
    )
    assert storage["result"] == "abnormal"
    recall = pharmacist.call(
        "POST", "/gsp/recalls",
        json={"drug_name": f"GSP模拟药{suffix}", "batch_no": f"NG-{suffix}", "reason": "模拟召回", "level": "2"},
    )
    pharmacist.call("POST", f"/gsp/recalls/{recall['id']}/complete")
    drug = admin.call(
        "POST", "/drugs/", json={"name": f"盘点模拟药{suffix}", "base_price": 5}
    )
    admin.call(
        "POST", "/warehouse/purchase",
        json={"drug_id": drug["id"], "batch_no": f"NS-{suffix}", "expiry": "2027-12-31", "quantity": 10},
    )
    take = warehouse.call(
        "POST", "/stocktakes", json={"kind": "drug", "title": f"模拟盘点{suffix}"}
    )
    line = next(row for row in take["items"] if row["drug_id"] == drug["id"])
    warehouse.call(
        "PUT", f"/stocktakes/{take['id']}/counts",
        json={"items": [{"item_id": row["id"], "actual_quantity": (row["book_quantity"] - 1 if row["drug_id"] == drug["id"] else row["book_quantity"])} for row in take["items"]]},
    )
    done = warehouse.call("POST", f"/stocktakes/{take['id']}/complete")
    assert done["status"] == "completed"
    mark("N1 供应链-GSP-盘点", "无患者", "验收/温湿度异常/召回/盘点", f"盘点{take['take_no']}")
    return {"acceptance_id": acceptance["id"], "stocktake_id": take["id"]}


def main() -> int:
    suffix = datetime.now().strftime("%m%d%H%M%S")
    admin = Role("管理员", "admin", "admin123")
    cashier = Role("收费员", "cashier", "cashier123")
    doctor = Role("医生", "doctor", "doctor123")
    lab = Role("检验", "lab", "lab123")
    pharmacist = Role("药师", "pharmacist", "pharm123")
    warehouse = Role("库房", "warehouse", "warehouse123")
    treatment = Role("治疗室", "treatment", "treatment123")
    decoction = Role("煎药", "decoction", "decoction123")
    nurse = Role("护士", "nurse", "nurse123")
    archive = Role("病案", "archive", "archive123")

    results = {}
    try:
        results["A"] = path_a(admin, cashier, doctor, lab, pharmacist, suffix)
        results["B"] = path_b(admin, cashier, doctor, treatment, suffix)
        results["C"] = path_c(admin, cashier, doctor, pharmacist, decoction, suffix)
        results["D"] = path_d(admin, cashier, doctor, nurse, suffix)
        results["E"] = path_e(admin, cashier, doctor, archive, suffix)
        results["N1"] = path_n1(admin, warehouse, pharmacist, suffix)
        results["N2"] = path_n2(admin, cashier, suffix)
        results["N3"] = path_n3(admin, cashier, suffix)
        print("\n多患者分流模拟通过")
        print(json.dumps(results, ensure_ascii=False, indent=2))
        REPORT.write_text(
            "# 多患者分流模拟报告\n\n"
            f"- 执行时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"- 服务端：{BASE}\n"
            f"- 结果：通过\n"
            f"- 路径：A 内科/检验/药房/退费；B 外科/治疗室/耗材/随访；C 中医/中药房/煎药；D 护理/输液；E 病案/归档借阅；N1 供应链/GSP/盘点；N2 医保目录/进销存；N3 收费/发票/交班\n\n"
            "## 路径明细\n\n"
            + "\n".join(
                f"- **{row['path']}** · {row['patient']} · {row['step']}"
                + (f" · {row['detail']}" if row['detail'] else "")
                for row in PATHS
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"报告：{REPORT}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"模拟失败：{exc}")
        traceback.print_exc()
        REPORT.write_text(
            "# 多患者分流模拟报告\n\n"
            f"- 执行时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"- 结果：失败\n- 错误：{exc}\n\n"
            "## 已完成步骤\n\n"
            + "\n".join(
                f"- **{row['path']}** · {row['patient']} · {row['step']}"
                for row in PATHS
            )
            + "\n",
            encoding="utf-8",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
