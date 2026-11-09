"""全流程真实环境验收：多角色、多会话、仓库/药房双分支、并发操作。

运行前先启动服务（默认 http://127.0.0.1:8001）：
    .venv\\Scripts\\python.exe scripts\\e2e_full_flow.py

产出：
    docs/全流程测试报告.md
    docs/全流程测试结果.json
"""
import base64
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001"
ROOT = Path(__file__).resolve().parent.parent
STEPS: list[dict] = []
STEP_DELAY = float(os.getenv("E2E_STEP_DELAY", "0"))
VERBOSE = os.getenv("E2E_VERBOSE", "0") == "1"


class FlowError(RuntimeError):
    pass


class Role:
    def __init__(self, name: str, username: str, password: str):
        self.name = name
        self.username = username
        self.session = requests.Session()
        self.session.trust_env = False
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers["Authorization"] = f"Basic {token}"

    def call(self, method: str, path: str, expected=(200, 201), **kwargs):
        phase = kwargs.pop("phase", "")
        started = time.time()
        response = self.session.request(
            method, BASE + path, timeout=30, **kwargs
        )
        elapsed = int((time.time() - started) * 1000)
        detail = ""
        try:
            body = response.json()
        except ValueError:
            body = response.text[:200]
        if isinstance(body, (dict, list)):
            detail = json.dumps(body, ensure_ascii=False)[:260]
        else:
            detail = str(body)[:260]
        STEPS.append(
            {
                "phase": phase,
                "role": self.name,
                "action": f"{method} {path}",
                "status": response.status_code,
                "elapsed_ms": elapsed,
                "detail": detail,
            }
        )
        if response.status_code not in expected:
            raise FlowError(
                f"{self.name} {method} {path} -> {response.status_code}: {detail}"
            )
        if STEP_DELAY:
            time.sleep(STEP_DELAY)
        return response

    def json(self, method: str, path: str, expected=(200, 201), **kwargs):
        return self.call(method, path, expected, **kwargs).json()

    def expect_error(self, method: str, path: str, status: int, contains: str, **kwargs):
        phase = kwargs.pop("phase", "")
        response = self.session.request(method, BASE + path, timeout=30, **kwargs)
        try:
            body = response.json()
            detail = body.get("detail", "") if isinstance(body, dict) else str(body)
        except ValueError:
            detail = response.text
        STEPS.append(
            {
                "phase": phase,
                "role": self.name,
                "action": f"{method} {path}（预期失败）",
                "status": response.status_code,
                "detail": str(detail)[:200],
            }
        )
        if response.status_code != status or contains not in str(detail):
            raise FlowError(
                f"{self.name} 预期 {status}/{contains}，实际 {response.status_code}: {detail}"
            )
        return response


def step(phase: str, role: str, action: str, detail: str = "") -> None:
    STEPS.append(
        {"phase": phase, "role": role, "action": action, "status": "OK", "detail": detail}
    )
    if VERBOSE:
        print(f"[{phase}] {role} · {action} · {detail}", flush=True)
    if STEP_DELAY:
        time.sleep(STEP_DELAY)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise FlowError(message)


def sum_stock(rows: list[dict], key: str, value: int) -> int:
    return sum(row["quantity"] for row in rows if row.get(key) == value)


def main() -> int:
    suffix = datetime.now().strftime("%m%d%H%M%S")
    today = date.today().isoformat()
    expiry_far = (date.today() + timedelta(days=900)).isoformat()
    near = (date.today() + timedelta(days=30)).isoformat()

    admin = Role("管理员", "admin", "admin123")
    cashier = Role("收费员", "cashier", "cashier123")
    doctor = Role("医生", "doctor", "doctor123")
    nurse = Role("护士", "nurse", "nurse123")
    pharmacist = Role("药师", "pharmacist", "pharm123")
    warehouse = Role("库房", "warehouse", "warehouse123")
    lab = Role("检验", "lab", "lab123")
    roles = [admin, cashier, doctor, nurse, pharmacist, warehouse, lab]

    try:
        # ================= 0. 基础数据 =================
        supplier = admin.json(
            "POST", "/suppliers/",
            json={"code": f"SUP-FLOW-{suffix}", "name": f"全流程供应商{suffix}"},
            phase="0 基础数据",
        )
        department = admin.json(
            "POST", "/departments/",
            json={"name": f"全流程内科{suffix}"}, phase="0 基础数据",
        )
        doctor_row = admin.json(
            "POST", "/doctors/",
            json={"name": f"全流程医生{suffix}", "department_id": department["id"]},
            phase="0 基础数据",
        )
        treatment_item = admin.json(
            "POST", "/charges/items/",
            json={
                "code": f"TRT-{suffix}",
                "name": f"雾化治疗{suffix}",
                "category": "treatment",
                "price": 30.0,
                "insurance_ratio": 0.0,
            },
            phase="0 基础数据",
        )
        lab_item = admin.json(
            "POST", "/lab/items/",
            json={"code": f"LAB-{suffix}", "name": f"血常规{suffix}", "price": 20.0},
            phase="0 基础数据",
        )
        material = admin.json(
            "POST", "/materials/items/",
            json={
                "code": f"MAT-{suffix}",
                "name": f"一次性敷料{suffix}",
                "spec": "10cm",
                "unit": "片",
                "price": 5.0,
                "is_high_value": True,
                "category": "consumable",
                "manufacturer": "演示医疗",
                "registration_no": f"械注准{suffix}",
            },
            phase="0 基础数据",
        )
        drug_a = admin.json(
            "POST", "/drugs/",
            json={"name": f"全流程A药{suffix}", "base_price": 12.5, "insurance_ratio": 0.8},
            phase="0 基础数据",
        )
        drug_b = admin.json(
            "POST", "/drugs/",
            json={"name": f"全流程B药{suffix}", "base_price": 8.0, "insurance_ratio": 0.7},
            phase="0 基础数据",
        )
        drug_d = admin.json(
            "POST", "/drugs/",
            json={"name": f"近效期药{suffix}", "base_price": 3.0},
            phase="0 基础数据",
        )

        # 医保目录：丙类药（自费），用于验证目录对码与处方目录校验
        csv_text = (
            "国家医保药品代码,药品名称,剂型,规格,生产厂家,单位,医保类别\n"
            f"FLA{suffix},全流程A药{suffix},胶囊,0.25g*24粒,演示药业,盒,乙\n"
            f"FLB{suffix},全流程B药{suffix},片剂,0.2g*12片,演示药业,盒,乙\n"
            f"FLD{suffix},近效期药{suffix},口服液,10ml,演示药业,盒,乙\n"
            f"FLOWC{suffix},全流程C药{suffix},片剂,0.5g*10片,演示药业,盒,丙\n"
        )
        admin.call(
            "POST",
            "/insurance/catalog/import",
            files={"file": ("flow.csv", csv_text.encode("utf-8"), "text/csv")},
            phase="0 基础数据",
        )
        drug_c = admin.json(
            "POST", "/drugs/",
            json={
                "name": f"全流程C药{suffix}",
                "spec": "0.5g*10片",
                "dosage_form": "片剂",
                "insurance_code": f"FLOWC{suffix}",
                "base_price": 6.0,
            },
            phase="0 基础数据",
        )
        admin.call("POST", "/insurance/catalog/match", phase="0 基础数据")
        c_match = admin.json(
            "GET", f"/insurance/catalog/resolve/{drug_c['id']}", phase="0 基础数据"
        )
        check(c_match["category"] == "丙", f"C药对码失败：{c_match}")
        step("0 基础数据", "管理员", "医保目录对码", f"C药={c_match['category']}类，比例{c_match['ratio']}")

        # ================= 1. 库房采购/入库 =================
        inbound_a = warehouse.json(
            "POST", "/inbound/orders",
            json={
                "order_type": "drug",
                "supplier_id": supplier["id"],
                "delivery_no": f"随货-A-{suffix}",
                "invoice_no": f"发票-A-{suffix}",
                "items": [
                    {
                        "kind": "drug",
                        "drug_id": drug_a["id"],
                        "batch_no": f"FLOW-A-{suffix}",
                        "expiry": expiry_far,
                        "quantity": 30,
                        "unit_price": 12.5,
                        "storage_condition": "常温",
                        "location": "A-01",
                    }
                ],
            },
            phase="1 库房入库",
        )
        warehouse.call(
            "POST", f"/inbound/orders/{inbound_a['id']}/check",
            json={"items": [{"item_id": inbound_a["items"][0]["id"], "rejected_qty": 2, "reject_reason": "包装破损"}]},
            phase="1 库房入库",
        )
        warehouse.call("POST", f"/inbound/orders/{inbound_a['id']}/stock", phase="1 库房入库")
        stocks = warehouse.json("GET", f"/warehouse/stocks?drug_id={drug_a['id']}", phase="1 库房入库")
        check(sum_stock(stocks, "drug_id", drug_a["id"]) == 28, f"A药入库数量错误：{stocks}")
        step("1 库房入库", "库房", "A药入库（30 收货、2 不合格）", "总库 28")

        inbound_c = warehouse.json(
            "POST", "/inbound/orders",
            json={
                "order_type": "drug",
                "supplier_id": supplier["id"],
                "items": [
                    {
                        "kind": "drug", "drug_id": drug_c["id"],
                        "batch_no": f"FLOW-C-{suffix}", "expiry": expiry_far, "quantity": 10,
                    }
                ],
            },
            phase="1 库房入库",
        )
        warehouse.call("POST", f"/inbound/orders/{inbound_c['id']}/check", json={"items": []}, phase="1 库房入库")
        warehouse.call("POST", f"/inbound/orders/{inbound_c['id']}/stock", phase="1 库房入库")

        inbound_mat = warehouse.json(
            "POST", "/inbound/orders",
            json={
                "order_type": "consumable",
                "supplier_id": supplier["id"],
                "items": [
                    {"kind": "material", "material_id": material["id"], "quantity": 50, "unit_price": 5.0}
                ],
            },
            phase="1 库房入库",
        )
        warehouse.call("POST", f"/inbound/orders/{inbound_mat['id']}/check", json={"items": []}, phase="1 库房入库")
        warehouse.call("POST", f"/inbound/orders/{inbound_mat['id']}/stock", phase="1 库房入库")
        mat_stock = warehouse.json("GET", f"/materials/stocks?item_id={material['id']}", phase="1 库房入库")
        check(sum_stock(mat_stock, "warehouse", "总库") == 50, f"物资入库错误：{mat_stock}")

        inbound_d = warehouse.json(
            "POST", "/inbound/orders",
            json={
                "order_type": "drug",
                "items": [
                    {
                        "kind": "drug", "drug_id": drug_d["id"],
                        "batch_no": f"FLOW-D-{suffix}", "expiry": near, "quantity": 5,
                    }
                ],
            },
            phase="1 库房入库",
        )
        warehouse.call("POST", f"/inbound/orders/{inbound_d['id']}/check", json={"items": []}, phase="1 库房入库")
        warehouse.call("POST", f"/inbound/orders/{inbound_d['id']}/stock", phase="1 库房入库")
        alerts = warehouse.json("GET", "/warehouse/expiry-alerts?days=90", phase="1 库房入库")
        check(
            any(row["batch_no"] == f"FLOW-D-{suffix}" for row in alerts["near_expiry"]),
            "近效期预警未包含 D 药批次",
        )
        step("1 库房入库", "库房", "近效期预警", f"近效期批次 {len(alerts['near_expiry'])} 个，含 D 药")

        # 报损 + 盘点差异调整
        scrap = warehouse.json(
            "POST", "/warehouse/outbound-orders",
            json={
                "outbound_type": "scrap",
                "target_type": "pharmacy",
                "items": [{
                    "kind": "drug", "drug_id": drug_d["id"],
                    "batch_no": f"FLOW-D-{suffix}", "quantity": 1,
                }],
            },
            phase="1 库房入库",
        )
        warehouse.call("POST", f"/warehouse/outbound-orders/{scrap['id']}/approve", phase="1 库房入库")
        warehouse.call("POST", f"/warehouse/outbound-orders/{scrap['id']}/issue", phase="1 库房入库")
        warehouse.call(
            "POST", "/warehouse/check",
            json={
                "drug_id": drug_d["id"], "batch_no": f"FLOW-D-{suffix}",
                "actual_quantity": 3,
            },
            phase="1 库房入库",
        )
        adjustments = warehouse.json("GET", "/warehouse/adjustments", phase="1 库房入库")
        check(any(item["drug_id"] == drug_d["id"] for item in adjustments), "盘点调整单缺失")
        step("1 库房入库", "库房", "报损 1 + 盘点差异调整", f"D 药 5→4→实盘3，调整单 {adjustments[0]['adjust_no']}")

        # 追溯码：入库扫码 4 个
        trace_codes = [f"TRC-{suffix}-{i}" for i in range(1, 5)]
        warehouse.call(
            "POST", "/trace/scan/inbound",
            json={"codes": trace_codes, "drug_id": drug_a["id"], "batch_no": f"FLOW-A-{suffix}"},
            phase="1 库房入库",
        )
        step("1 库房入库", "库房", "A药入库扫码", f"{len(trace_codes)} 个码登记总库")

        # ================= 2. 患者/挂号/分诊 =================
        patient = cashier.json(
            "POST", "/patients/",
            json={"name": f"全流程患者{suffix}", "id_number": f"1101011992{suffix[-8:]}", "phone": "13800000000"},
            phase="2 门诊",
        )
        schedule = admin.json(
            "POST", "/schedules/",
            json={
                "doctor_id": doctor_row["id"],
                "schedule_date": today,
                "period": "morning",
                "capacity": 5,
            },
            phase="2 门诊",
        )
        appointment = cashier.json(
            "POST", "/appointments/",
            json={
                "patient_id": patient["id"],
                "doctor_id": doctor_row["id"],
                "schedule_id": schedule["id"],
            },
            phase="2 门诊",
        )
        checked = cashier.json(
            "POST", f"/appointments/{appointment['id']}/check-in", phase="2 门诊"
        )
        check(checked["status"] == "checked_in", f"预约取号失败：{checked}")
        registration = cashier.json(
            "GET", f"/registrations/{checked['registration_id']}", phase="2 门诊"
        )
        check(registration["status"] == "registered", f"预约挂号状态异常：{registration}")
        step("2 门诊", "管理员/收费员",
            "排班→预约→取号（生成挂号）",
            f"排班 {schedule['id']}，预约 {appointment['id']}，挂号 {registration['id']}")
        ticket = nurse.json(
            "POST", "/triage/tickets",
            json={"registration_id": registration["id"]},
            phase="2 门诊",
        )
        nurse.call("POST", f"/triage/tickets/{ticket['id']}/call", phase="2 门诊")
        step("2 门诊", "护士", "分诊叫号", f"叫号单 {ticket['id']}")
        encounter = doctor.json(
            "POST", "/encounters/",
            json={"registration_id": registration["id"], "diagnosis": "上呼吸道感染"},
            phase="2 门诊",
        )
        doctor.call(
            "POST", f"/encounters/{encounter['id']}/medical-record",
            json={
                "chief_complaint": "发热咳嗽 2 天",
                "present_illness": "2 天前受凉后发热，最高 38.5℃",
                "past_history": "无",
                "physical_exam": "咽充血，双肺呼吸音清",
                "treatment_advice": "抗感染、对症治疗",
            },
            phase="2 门诊",
        )
        doctor.call("POST", f"/encounters/{encounter['id']}/medical-record/sign", phase="2 门诊")
        step("2 门诊", "医生", "接诊/病历/签名", f"就诊 {encounter['id']}")

        prescriptions = []
        for drug, quantity in (
            (drug_a, 4),
            (drug_b, 3),
            (drug_c, 2),
        ):
            item = doctor.json(
                "POST", f"/encounters/{encounter['id']}/prescriptions",
                json={"drug_id": drug["id"], "quantity": quantity, "dosage": "1片", "frequency": "tid", "route": "口服", "days": 3},
                phase="2 门诊",
            )
            prescriptions.append(item)
        lab_request = doctor.json(
            "POST", f"/lab/encounters/{encounter['id']}/lab-requests",
            json={"item_id": lab_item["id"]}, phase="2 门诊",
        )
        treatment = doctor.json(
            "POST", f"/treatments/encounters/{encounter['id']}",
            json={"item_id": treatment_item["id"], "quantity": 2, "note": "每日一次"},
            phase="2 门诊",
        )
        step("2 门诊", "医生", "开方/检验/治疗", f"处方3张，检验 {lab_request['id']}，治疗 {treatment['id']}")
        doctor.expect_error(
            "POST", f"/encounters/{encounter['id']}/prescriptions",
            status=400, contains="已在处方",
            json={"drug_id": drug_a["id"], "quantity": 1}, phase="2 门诊",
        )
        step("2 门诊", "医生", "重复开方拦截", "按预期失败：该药品已在处方中")

        # ================= 3. 并发：收费 + 多账号读取 =================
        barrier = threading.Barrier(6)
        results = {}

        def pay_job():
            barrier.wait()
            results["payment"] = cashier.json(
                "POST", "/payments/",
                json={"encounter_id": encounter["id"], "channel": "wechat", "auth_code": "134567890"},
                phase="3 并发收费",
            )

        def read_job(role: Role, key: str, path: str):
            barrier.wait()
            results[key] = role.json("GET", path, phase="3 并发收费")

        jobs = [
            pay_job,
            lambda: read_job(doctor, "registrations", "/registrations/"),
            lambda: read_job(pharmacist, "pharmacy_stock", f"/pharmacy/stocks?drug_id={drug_a['id']}"),
            lambda: read_job(warehouse, "warehouse_stock", f"/warehouse/stocks?drug_id={drug_a['id']}"),
            lambda: read_job(nurse, "queue", "/triage/queue"),
            lambda: read_job(lab, "lab_requests", f"/lab/encounters/{encounter['id']}/lab-requests"),
        ]
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(job) for job in jobs]
            for task in futures:
                task.result()
        payment = results["payment"]
        check(payment["status"] == "paid", f"收费失败：{payment}")
        check(payment["channel"] == "wechat" and payment["channel_status"] == "mock", f"支付通道异常：{payment}")
        step(
            "3 并发收费", "收费员+医生+药师+库房+护士+检验",
            "6 个账号同时请求（收费写入+5 个读取）",
            f"收费 {payment['amount']:.2f}，医保 {payment['insurance_amount']:.2f}，自费 {payment['self_pay_amount']:.2f}",
        )

        lab.call(
            "POST", f"/lab/requests/{lab_request['id']}/report",
            json={"result": "WBC 6.5×10^9/L，中性粒细胞 62%"}, phase="4 检验/治疗",
        )
        lab_done = lab.json("GET", f"/lab/requests/{lab_request['id']}", phase="4 检验/治疗")
        check(lab_done["status"] == "reported", f"检验报告状态异常：{lab_done}")
        nurse.call("POST", f"/treatments/{treatment['id']}/execute", phase="4 检验/治疗")
        treatment_done = nurse.json("GET", f"/treatments/{treatment['id']}", phase="4 检验/治疗")
        check(treatment_done["status"] == "done", f"治疗执行异常：{treatment_done}")
        step("4 检验/治疗", "检验/护士", "检验报告+治疗执行", f"检验 {lab_done['status']}，治疗 {treatment_done['status']}")

        # 打印
        cashier.call("GET", f"/print/receipt/{payment['id']}", phase="4 检验/治疗")
        doctor.call("GET", f"/print/prescription/{encounter['id']}", phase="4 检验/治疗")
        step("4 检验/治疗", "收费员/医生", "打印收费收据/处方", "HTML 200")

        # ================= 5. 药房：缺药→申请→采购/出库 =================
        for drug, label in ((drug_a, "A"), (drug_b, "B"), (drug_c, "C")):
            rows = pharmacist.json("GET", f"/pharmacy/stocks?drug_id={drug['id']}", phase="5 药房")
            check(sum_stock(rows, "drug_id", drug["id"]) == 0, f"{label}药药房初始应有 0")
        step("5 药房", "药师", "药房库存检查", "A/B/C 均为 0")

        pharmacist.expect_error(
            "POST", "/pharmacy/dispense",
            status=400, contains="库存不足",
            json={"encounter_id": encounter["id"]}, phase="5 药房",
        )
        step("5 药房", "药师", "无药直接发药", "按预期失败：库存不足")

        req_ac = pharmacist.json(
            "POST", "/warehouse/outbound-orders",
            json={
                "target_type": "pharmacy",
                "target_name": "药房",
                "items": [
                    {"kind": "drug", "drug_id": drug_a["id"], "batch_no": f"FLOW-A-{suffix}", "quantity": 4},
                    {"kind": "drug", "drug_id": drug_c["id"], "batch_no": f"FLOW-C-{suffix}", "quantity": 2},
                ],
            },
            phase="5 药房",
        )
        warehouse.call("POST", f"/warehouse/outbound-orders/{req_ac['id']}/approve", phase="5 药房")
        item_a = req_ac["items"][0]["id"]
        part = warehouse.json(
            "POST", f"/warehouse/outbound-orders/{req_ac['id']}/issue",
            json={"items": [{"item_id": item_a, "quantity": 2}]}, phase="5 药房",
        )
        check(part["status"] == "partially_issued", f"部分出库状态异常：{part}")
        warehouse.call("POST", f"/warehouse/outbound-orders/{req_ac['id']}/issue", phase="5 药房")
        step("5 药房", "药师→库房", "A/C 药领用出库（先部分 2，再出剩余）", f"申请单 {req_ac['id']} 已全部出库")

        req_b = pharmacist.json(
            "POST", "/warehouse/outbound-orders",
            json={"target_type": "pharmacy", "target_name": "药房",
                  "items": [{"kind": "drug", "drug_id": drug_b["id"], "batch_no": f"FLOW-B-{suffix}", "quantity": 3}]},
            phase="5 药房",
        )
        warehouse.call("POST", f"/warehouse/outbound-orders/{req_b['id']}/approve", phase="5 药房")
        warehouse.expect_error(
            "POST", f"/warehouse/outbound-orders/{req_b['id']}/issue",
            status=400, contains="库存不足", phase="5 药房",
        )
        step("5 药房", "库房", "B 药出库校验", "按预期失败：总库无库存")

        # 并发：采购写入 + 多账号读取
        barrier2 = threading.Barrier(5)
        purchase_result = {}

        def purchase_job():
            barrier2.wait()
            purchase_result["purchase"] = admin.json(
                "POST", "/warehouse/purchase",
                json={"drug_id": drug_b["id"], "batch_no": f"FLOW-B-{suffix}", "expiry": expiry_far, "quantity": 20, "supplier_id": supplier["id"]},
                phase="5 药房",
            )

        def read2(role: Role, key: str, path: str):
            barrier2.wait()
            purchase_result[key] = role.json("GET", path, phase="5 药房")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(purchase_job),
                executor.submit(read2, pharmacist, "pharmacy", "/pharmacy/stocks"),
                executor.submit(read2, warehouse, "warehouse", "/warehouse/stocks"),
                executor.submit(read2, nurse, "queue", "/triage/queue"),
                executor.submit(read2, doctor, "prescriptions", f"/encounters/{encounter['id']}/prescriptions"),
            ]
            for task in futures:
                task.result()
        step("5 药房", "管理员+药师+库房+护士+医生", "采购 B 药同时多账号读取", "采购成功，5 个会话并发返回")

        warehouse.call("POST", f"/warehouse/outbound-orders/{req_b['id']}/issue", phase="5 药房")
        step("5 药房", "库房", "B 药补货后出库", "总库→药房")

        # 库房向护士站、诊室出库物资
        for target, qty in (("护士站", 10), ("全流程内科" + suffix, 5)):
            req = pharmacist.json(
                "POST", "/warehouse/outbound-orders",
                json={
                    "outbound_type": "requisition",
                    "target_type": "department",
                    "target_name": target,
                    "items": [{"kind": "material", "material_id": material["id"], "quantity": qty}],
                },
                phase="5 药房",
            )
            warehouse.call("POST", f"/warehouse/outbound-orders/{req['id']}/approve", phase="5 药房")
            warehouse.call("POST", f"/warehouse/outbound-orders/{req['id']}/issue", phase="5 药房")
            step("5 药房", "库房", f"物资出库→{target}", f"{qty} 片")

        nurse.call(
            "POST", "/materials/usages",
            json={"item_id": material["id"], "serial_no": f"SN-{suffix}", "encounter_id": encounter["id"], "warehouse": "护士站"},
            phase="5 药房",
        )
        step("5 药房", "护士", "高值耗材使用追溯", f"序列号 SN-{suffix}")

        # 追溯码：出库、发药
        warehouse.call(
            "POST", "/trace/scan/outbound", json={"codes": trace_codes}, phase="5 药房"
        )

        dispense = pharmacist.json(
            "POST", "/pharmacy/dispense", json={"encounter_id": encounter["id"]}, phase="5 药房"
        )
        step("5 药房", "药师", "发药（A/B/C）", f"发药单 {dispense['id']}")
        pharmacist.call(
            "POST", "/trace/scan/dispense",
            json={"codes": trace_codes, "encounter_id": encounter["id"], "ref_id": dispense["id"]},
            phase="5 药房",
        )
        for drug, label in ((drug_a, "A"), (drug_b, "B"), (drug_c, "C")):
            rows = pharmacist.json("GET", f"/pharmacy/stocks?drug_id={drug['id']}", phase="5 药房")
            check(sum_stock(rows, "drug_id", drug["id"]) == 0, f"发药后{label}药库存应为 0")
        step("5 药房", "药师", "发药后库存核对", "A/B/C 均为 0；追溯码已核销")

        # 退药（全退）并回补库存
        returned = pharmacist.json(
            "POST", f"/pharmacy/dispense/{dispense['id']}/return", phase="5 药房"
        )
        check(returned["status"] == "returned", f"退药失败：{returned}")
        pharmacist.call("POST", "/trace/scan/return", json={"codes": trace_codes}, phase="5 药房")
        for drug, expected, label in ((drug_a, 4, "A"), (drug_b, 3, "B"), (drug_c, 2, "C")):
            rows = pharmacist.json("GET", f"/pharmacy/stocks?drug_id={drug['id']}", phase="5 药房")
            check(sum_stock(rows, "drug_id", drug["id"]) == expected, f"退药后{label}药库存应为 {expected}")
        step("5 药房", "药师", "退药+追溯码回库", "A4/B3/C2 回药房")

        # 药房退库回总库（退库单）
        ret = pharmacist.json(
            "POST", "/warehouse/outbound-orders",
            json={
                "outbound_type": "return",
                "target_type": "pharmacy",
                "target_name": "药房",
                "items": [{
                    "kind": "drug", "drug_id": drug_a["id"],
                    "batch_no": f"FLOW-A-{suffix}", "quantity": 1,
                }],
            },
            phase="5 药房",
        )
        warehouse.call("POST", f"/warehouse/outbound-orders/{ret['id']}/approve", phase="5 药房")
        warehouse.call("POST", f"/warehouse/outbound-orders/{ret['id']}/issue", phase="5 药房")
        rows = pharmacist.json("GET", f"/pharmacy/stocks?drug_id={drug_a['id']}", phase="5 药房")
        check(sum_stock(rows, "drug_id", drug_a["id"]) == 3, "退库后药房 A 药应为 3")
        step("5 药房", "药师→库房", "药房退库 A 药 1 盒", f"退库单 {ret['id']}，药房 A 药 4→3")

        # 药房有药直接发药分支（POS 刷卡支付）
        patient3 = cashier.json(
            "POST", "/patients/",
            json={"name": f"直接发药患者{suffix}", "id_number": f"1101011994{suffix[-8:]}"},
            phase="5 药房",
        )
        reg3 = cashier.json(
            "POST", "/registrations/",
            json={"patient_id": patient3["id"], "doctor_id": doctor_row["id"]},
            phase="5 药房",
        )
        enc3 = doctor.json(
            "POST", "/encounters/", json={"registration_id": reg3["id"], "diagnosis": "复诊"},
            phase="5 药房",
        )
        doctor.json(
            "POST", f"/encounters/{enc3['id']}/prescriptions",
            json={"drug_id": drug_a["id"], "quantity": 1}, phase="5 药房",
        )
        pay3 = cashier.json(
            "POST", "/payments/",
            json={"encounter_id": enc3["id"], "channel": "pos", "card_no": f"POS-{suffix}"},
            phase="5 药房",
        )
        dispense3 = pharmacist.json(
            "POST", "/pharmacy/dispense", json={"encounter_id": enc3["id"]}, phase="5 药房"
        )
        check(dispense3["status"] == "dispensed", f"直接发药失败：{dispense3}")
        rows = pharmacist.json("GET", f"/pharmacy/stocks?drug_id={drug_a['id']}", phase="5 药房")
        check(sum_stock(rows, "drug_id", drug_a["id"]) == 2, "直接发药后 A 药应为 2")
        pharmacist.json("POST", f"/pharmacy/dispense/{dispense3['id']}/return", phase="5 药房")
        rows = pharmacist.json("GET", f"/pharmacy/stocks?drug_id={drug_a['id']}", phase="5 药房")
        check(sum_stock(rows, "drug_id", drug_a["id"]) == 3, "直接发药退回后 A 药应为 3")
        step(
            "5 药房", "收费员/医生/药师",
            "药房有药直接发药（POS）",
            f"收费单 {pay3['id']}，发药单 {dispense3['id']}，A药 3→2→退回 3",
        )

        # ================= 6. 自费/医保退费 =================
        patient2 = cashier.json(
            "POST", "/patients/",
            json={"name": f"退费患者{suffix}", "id_number": f"1101011993{suffix[-8:]}"},
            phase="6 退费",
        )
        reg2 = cashier.json(
            "POST", "/registrations/",
            json={"patient_id": patient2["id"], "doctor_id": doctor_row["id"]},
            phase="6 退费",
        )
        enc2 = doctor.json(
            "POST", "/encounters/", json={"registration_id": reg2["id"], "diagnosis": "咽炎"},
            phase="6 退费",
        )
        treat2 = doctor.json(
            "POST", f"/treatments/encounters/{enc2['id']}",
            json={"item_id": treatment_item["id"], "quantity": 2}, phase="6 退费",
        )
        pay2 = cashier.json(
            "POST", "/payments/", json={"encounter_id": enc2["id"], "channel": "cash"},
            phase="6 退费",
        )
        nurse.call("POST", f"/treatments/{treat2['id']}/execute", phase="6 退费")
        full = cashier.json("POST", f"/payments/{pay2['id']}/refund", phase="6 退费")
        check(full["status"] == "refunded", f"医保/整单退费失败：{full}")
        step("6 退费", "收费员", "整单全额退费", f"已退 {full['refunded_amount']:.2f} 元")

        # ================= 7. 对账/进销存 =================
        expected_warehouse = {drug_a["id"]: 25, drug_b["id"]: 17, drug_c["id"]: 8, drug_d["id"]: 3}
        for drug_id, expected in expected_warehouse.items():
            rows = warehouse.json("GET", f"/warehouse/stocks?drug_id={drug_id}", phase="7 对账")
            actual = sum_stock(rows, "drug_id", drug_id)
            check(actual == expected, f"总库药品 {drug_id} 结存 {actual} != {expected}")
        expected_pharmacy = {drug_a["id"]: 3, drug_b["id"]: 3, drug_c["id"]: 2}
        for drug_id, expected in expected_pharmacy.items():
            rows = pharmacist.json("GET", f"/pharmacy/stocks?drug_id={drug_id}", phase="7 对账")
            actual = sum_stock(rows, "drug_id", drug_id)
            check(actual == expected, f"药房药品 {drug_id} 结存 {actual} != {expected}")
        material_rows = warehouse.json("GET", f"/materials/stocks?item_id={material['id']}", phase="7 对账")
        by_wh = {row["warehouse"]: row["quantity"] for row in material_rows}
        check(by_wh.get("总库") == 35, f"物资总库应为 35：{by_wh}")
        check(by_wh.get("护士站") == 9, f"护士站物资应为 9：{by_wh}")
        check(by_wh.get(f"全流程内科{suffix}") == 5, f"内科物资应为 5：{by_wh}")
        step("7 对账", "库房/药师", "库存结存核对", f"总库 {expected_warehouse}；药房 {expected_pharmacy}；物资 {by_wh}")

        ledger = admin.json("GET", "/stock/ledger?limit=500", phase="7 对账")
        ref_types = {row["ref_type"] for row in ledger}
        check({"inbound", "outbound", "dispense", "dispense_return", "usage"} <= ref_types,
              f"库存流水类型缺失：{ref_types}")
        step("7 对账", "管理员", "库存流水核查", f"流水 {len(ledger)} 条，类型 {sorted(ref_types)}")

        preview = admin.json(
            "POST", "/insurance/inventory/preview",
            json={"start_date": today, "end_date": today}, phase="7 对账",
        )
        upload = admin.json(
            "POST", "/insurance/inventory/upload",
            json={"start_date": today, "end_date": today}, phase="7 对账",
        )
        check(upload["status"] == "success", f"医保进销存上传失败：{upload}")
        detail = admin.json("GET", f"/insurance/inventory/uploads/{upload['id']}", phase="7 对账")
        payload = json.loads(detail["payload"])
        check(f"全流程A药{suffix}" in detail["payload"], "进销存报文缺少 A 药")
        check(
            all(row["insurance_code"] for row in payload["records"]),
            "进销存报文不应包含未对码药品",
        )
        step(
            "7 对账", "管理员", "医保进销存上传",
            f"预览 {preview['record_count']} 条（未对码 {preview['unmatched_count']}），"
            f"上传 {upload['record_count']} 条，跳过 {upload.get('skipped_count', 0)} 条，"
            f"{upload['upload_no']} 成功",
        )

        admin.json(
            "GET", f"/reports/departments/revenue?start_date={today}&end_date={today}",
            phase="7 对账",
        )
        admin.json("GET", "/bi/overview", phase="7 对账")
        step("7 对账", "管理员", "科室收入报表 / BI 概览", "均返回 200")

        # ================= 8. 汇总 =================
        summary = {
            "suffix": suffix,
            "server": BASE,
            "version": requests.get(BASE + "/version", timeout=10).json()["version"],
            "roles": {role.name: role.username for role in roles},
            "patient_id": patient["id"],
            "registration_id": registration["id"],
            "encounter_id": encounter["id"],
            "payment_id": payment["id"],
            "payment_amount": payment["amount"],
            "insurance_amount": payment["insurance_amount"],
            "self_pay_amount": payment["self_pay_amount"],
            "dispense_id": dispense["id"],
            "outbound_orders": [req_ac["id"], req_b["id"]],
            "lab_request_id": lab_request["id"],
            "treatment_id": treatment["id"],
            "warehouse_stocks": expected_warehouse,
            "pharmacy_stocks": expected_pharmacy,
            "material_stocks": by_wh,
            "ledger_rows": len(ledger),
            "inventory_upload": upload["upload_no"],
            "inventory_skipped": upload.get("skipped_count", 0),
        }
        write_report(summary)
        print("=" * 70)
        print("全流程验收通过")
        for key, value in summary.items():
            print(f"{key}: {value}")
        print(f"步骤数：{len(STEPS)}；报告：docs/全流程测试报告.md")
        return 0
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        write_report({"error": str(exc)}, failed=True)
        print("=" * 70)
        print(f"全流程验收失败：{exc}")
        print(f"步骤数：{len(STEPS)}；报告：docs/全流程测试报告.md")
        return 1


def write_report(summary: dict, failed: bool = False) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# HIS 全流程测试报告",
        "",
        f"- 执行时间：{now}",
        f"- 服务端：{BASE}",
        f"- 结果：{'失败' if failed else '通过'}",
        f"- 步骤数：{len(STEPS)}",
        "",
    ]
    if summary:
        lines += ["## 汇总", "", "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", ""]
    lines += [
        "## 步骤明细",
        "",
        "| # | 阶段 | 角色 | 操作 | 状态 | 耗时(ms) | 详情 |",
        "|---|---|---|---|---|---|---|",
    ]
    for index, item in enumerate(STEPS, 1):
        detail = str(item.get("detail", "")).replace("|", "\\|")[:160]
        lines.append(
            f"| {index} | {item.get('phase', '')} | {item.get('role', '')} | "
            f"{item.get('action', '')} | {item.get('status', '')} | {item.get('elapsed_ms', '')} | {detail} |"
        )
    lines += ["", "## 说明", "", "- 每个角色使用独立 HTTP 会话/Basic 登录，同一台机器并发请求同一服务端。", ""]
    (ROOT / "docs" / "全流程测试报告.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "docs" / "全流程测试结果.json").write_text(
        json.dumps({"summary": summary, "steps": STEPS}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())


