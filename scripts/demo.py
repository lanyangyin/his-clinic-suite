"""HIS 演示脚本：按角色走完整业务链路，每步断言期望输出（纯模拟期望输出的演示/冒烟测试）。

前提：
  1. 服务已启动（uv run uvicorn app.main:app --reload，默认 http://127.0.0.1:8000）
  2. 已运行种子脚本（uv run python scripts/seed_demo.py）

用法：
  uv run python scripts/demo.py [base_url]

脚本可重复运行（患者/药品按唯一键幂等，金额按实际返回动态计算）。
全部断言通过退出码为 0，任一失败退出码为 1。
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ACCOUNTS = {
    "admin": ("admin", "admin123"),
    "doctor": ("doctor", "doctor123"),
    "nurse": ("nurse", "nurse123"),
    "cashier": ("cashier", "cashier123"),
    "pharmacist": ("pharmacist", "pharm123"),
}

failures = 0
step_no = 0


def call(role, method, path, payload=None):
    """发起 HTTP 请求，返回 (status_code, json_body)。"""
    user, pwd = ACCOUNTS[role] if role else (None, None)
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        req.add_header("Content-Type", "application/json")
        req.data = body
    if user:
        token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode())
        except Exception:
            data = {}
        return e.code, data


def expect(label, actual, expected):
    """断言一步期望输出，打印对比结果。"""
    global failures, step_no
    step_no += 1
    ok = actual == expected
    print(f"[{'PASS' if ok else 'FAIL'}] {label} | 期望 {expected!r} | 实际 {actual!r}")
    if not ok:
        failures += 1


def main() -> int:
    print(f"目标服务：{BASE}")
    print("=" * 60)

    # 0. 未登录写操作 -> 401
    status, body = call(None, "POST", "/patients/", {"name": "X", "id_number": "X"})
    expect("未登录建档被拒（401）", status, 401)

    # 1. 医生站现场挂号（当前版本允许医生为患者挂号）
    status, body = call("doctor", "POST", "/registrations/", {"patient_id": 1, "doctor_id": 1})
    expect("医生站现场挂号（201）", status, 201)

    # 2. 收费员建档（幂等：重复运行返回已有记录）
    status, patient = call(
        "cashier", "POST", "/patients/",
        {"name": "演示患者", "id_number": "110101199001011234", "phone": "13800138000"},
    )
    expect("收费员建档（201）", status, 201)

    # 3. 收费员挂号（医生 1：种子数据里必存在）
    status, doctor = call(None, "GET", "/doctors/1")
    if status != 200:
        print("[FAIL] 医生 1 不存在，请先运行 scripts/seed_demo.py")
        return 1
    status, registration = call(
        "cashier", "POST", "/registrations/",
        {"patient_id": patient["id"], "doctor_id": doctor["id"]},
    )
    expect("收费员挂号（201 registered）", (status, registration.get("status")), (201, "registered"))

    # 4. 医生接诊
    status, encounter = call(
        "doctor", "POST", "/encounters/",
        {"registration_id": registration["id"], "diagnosis": "演示诊断-上呼吸道感染"},
    )
    expect("医生接诊（201 open）", (status, encounter.get("status")), (201, "open"))

    # 5. 医生开方（演示药品按名称幂等，基准价 15.0、报销比例 0.7 由服务端带出）
    status, drug = call(
        "admin", "POST", "/drugs/",
        {"name": "演示药(维生素D滴剂)", "spec": "400IU*30粒", "unit": "盒", "base_price": 15.0, "insurance_ratio": 0.7},
    )
    expect("管理员维护演示药品（201）", status, 201)
    price = drug["base_price"]
    status, item1 = call(
        "doctor", "POST", f"/encounters/{encounter['id']}/prescriptions",
        {"drug_id": drug["id"], "quantity": 2},
    )
    expect("医生开方 x2（201，单价自动带出，医保通过）", (status, item1.get("unit_price"), item1.get("insurance_warning")), (201, price, None))

    # 5b. 重复开立同一药品 -> 合理用药拦截（400）
    status, dup_item = call(
        "doctor", "POST", f"/encounters/{encounter['id']}/prescriptions",
        {"drug_id": drug["id"], "quantity": 1},
    )
    expect("重复开立同药被拦截（400）", (status, dup_item.get("detail")), (400, "该药品已在处方中，请勿重复开立"))

    # 5c. 超量开方 -> 医保事前提醒（warn 但放行，提醒写入处方行；用第二种演示药避免重复用药拦截）
    status, drug2 = call(
        "admin", "POST", "/drugs/",
        {"name": "演示药2(维生素D滴剂)", "spec": "400IU*30粒", "unit": "盒", "base_price": 15.0, "insurance_ratio": 0.7},
    )
    expect("管理员维护第二演示药品（201）", status, 201)
    status, item2 = call(
        "doctor", "POST", f"/encounters/{encounter['id']}/prescriptions",
        {"drug_id": drug2["id"], "quantity": 6},
    )
    expect("超量开方 x6（201，附医保超量提醒）", (status, "超量" in (item2.get("insurance_warning") or "")), (201, True))

    # 5d. 特殊使用级抗菌药物 -> 需会诊审批（400）
    status, restricted_drug = call(
        "admin", "POST", "/drugs/",
        {"name": "演示抗菌药(万古霉素)", "spec": "0.5g", "unit": "支", "base_price": 120.0, "insurance_ratio": 0.6, "antibiotic_level": 3},
    )
    expect("管理员维护特殊使用级抗菌药（201）", status, 201)
    status, restrict = call(
        "doctor", "POST", f"/encounters/{encounter['id']}/prescriptions",
        {"drug_id": restricted_drug["id"], "quantity": 1},
    )
    expect("特殊使用级抗菌药开立被拦截（400）", (status, "会诊审批" in restrict.get("detail", "")), (400, True))

    # 5e. 目录外药品 -> 医保事前审核禁止（400）
    status, self_pay_drug = call(
        "admin", "POST", "/drugs/",
        {"name": "演示自费药(进口钙片)", "spec": "60片", "unit": "盒", "base_price": 30.0, "insurance_ratio": 0},
    )
    expect("管理员维护目录外药品（201）", status, 201)
    status, forbid = call(
        "doctor", "POST", f"/encounters/{encounter['id']}/prescriptions",
        {"drug_id": self_pay_drug["id"], "quantity": 1},
    )
    expect("目录外药品开方被医保禁止（400）", (status, "不在医保目录" in forbid.get("detail", "")), (400, True))

    # 5e. 处方用法用量（剂次/频次/途径/天数）
    status, drug3 = call(
        "admin", "POST", "/drugs/",
        {"name": "演示药3(蒙脱石散)", "spec": "3g*10袋", "unit": "盒", "base_price": 12.0, "insurance_ratio": 0.7},
    )
    status, dosed = call(
        "doctor", "POST", f"/encounters/{encounter['id']}/prescriptions",
        {"drug_id": drug3["id"], "quantity": 1, "dosage": "3g", "frequency": "tid", "route": "口服", "days": 3},
    )
    expect(
        "处方带用法开方（201，用法字段透传）",
        (status, dosed.get("dosage"), dosed.get("frequency"), dosed.get("route"), dosed.get("days")),
        (201, "3g", "tid", "口服", 3),
    )

    # 5f. 治疗处置：医生开单（开单即计费）→ 护士执行
    status, treatment_item = call(None, "GET", "/charges/items/by-code/TREAT_INFUSION")
    expect("治疗项目字典可查（静脉输液）", (status, treatment_item.get("name")), (200, "静脉输液"))
    status, treat = call(
        "doctor", "POST", f"/treatments/encounters/{encounter['id']}",
        {"item_id": treatment_item["id"], "quantity": 1, "note": "头孢曲松 2g 静滴"},
    )
    expect("医生开治疗单（201 pending）", (status, treat.get("status")), (201, "pending"))
    status, executed = call("nurse", "POST", f"/treatments/{treat['id']}/execute", {})
    expect("护士执行治疗（200 done，记录执行人）", (status, executed.get("status"), executed.get("executed_by")), (200, "done", "nurse"))
    status, again = call("nurse", "POST", f"/treatments/{treat['id']}/execute", {})
    expect("重复执行治疗被拦截（400）", (status, again.get("detail")), (400, "该治疗单已执行或已取消"))

    # 6. 收费员收费（金额 = 该就诊费用明细合计：挂号费 + 诊疗费 + 药品费 + 治疗费）
    status, charges = call(None, "GET", f"/charges/encounters/{encounter['id']}")
    expect("费用明细可查（含挂号/诊疗/药品费）", status, 200)
    expected_amount = round(sum(c["amount"] for c in charges), 2)
    # 默认配置医保关闭：全额自费；开启医保时此脚本需同步调整
    expected_insurance = 0.0
    status, payment = call("cashier", "POST", "/payments/", {"encounter_id": encounter["id"]})
    expect(
        "收费员收费（201 paid，金额=费用明细合计）",
        (status, payment.get("amount"), payment.get("status")),
        (201, expected_amount, "paid"),
    )
    expect("医保结算金额", payment.get("insurance_amount"), expected_insurance)
    expect(
        "自费金额",
        payment.get("self_pay_amount"),
        round(expected_amount - expected_insurance, 2),
    )
    expect(
        "收费生成发票票据号",
        bool(payment.get("invoice_no")),
        True,
    )

    # 6b. 科室收入报表 + 处方点评（管理端）
    status, revenue = call("admin", "GET", "/reports/departments/revenue")
    expect(
        "科室收入报表可查（按科室汇总）",
        (status, isinstance(revenue, list), len(revenue or []) > 0),
        (200, True, True),
    )
    status, review = call("admin", "GET", "/review/summary")
    expect(
        "处方点评汇总可查（处方数>0、均金额>0）",
        (status, review.get("prescription_count", 0) > 0, review.get("avg_amount", 0) > 0),
        (200, True, True),
    )
    status, encounter_now = call(None, "GET", f"/encounters/{encounter['id']}")
    expect("收费后就诊关闭（closed）", encounter_now.get("status"), "closed")

    # 7. 医生对已关闭就诊加药 -> 409
    status, body = call(
        "doctor", "POST", f"/encounters/{encounter['id']}/prescriptions",
        {"drug_id": drug["id"], "quantity": 1},
    )
    expect("已关闭就诊不能再开方（409）", (status, body.get("detail")), (409, "就诊已收费，不能再开处方"))

    # 8. 药师入库（演示批次，可重复累加；两种演示药各入 100）
    expiry = (date.today() + timedelta(days=400)).isoformat()
    status, stock = call(
        "pharmacist", "POST", "/pharmacy/stock-in",
        {"drug_id": drug["id"], "batch_no": "DEMO-001", "expiry": expiry, "location": "D-01", "quantity": 100},
    )
    expect("药师入库（201）", status, 201)
    status, stock2 = call(
        "pharmacist", "POST", "/pharmacy/stock-in",
        {"drug_id": drug2["id"], "batch_no": "DEMO-001", "expiry": expiry, "location": "D-01", "quantity": 100},
    )
    expect("药师入库第二药品（201）", status, 201)

    # 第三种演示药（带用法开方）也需入库，否则发药会因库存不足被拦截
    status, stock3 = call(
        "pharmacist", "POST", "/pharmacy/stock-in",
        {"drug_id": drug3["id"], "batch_no": "DEMO-001", "expiry": expiry, "location": "D-01", "quantity": 100},
    )
    expect("药师入库第三药品（201）", status, 201)

    # 9. 药师发药（演示药扣 2、演示药2 扣 6、演示药3 扣 1）
    status, dispense = call("pharmacist", "POST", "/pharmacy/dispense", {"encounter_id": encounter["id"]})
    expect("药师发药（201）", status, 201)
    status, stock_now = call(None, "GET", f"/pharmacy/stocks/{stock['id']}")
    expect("库存已扣减（演示药 100-2）", stock_now.get("quantity"), stock["quantity"] - 2)
    status, stock2_now = call(None, "GET", f"/pharmacy/stocks/{stock2['id']}")
    expect("库存已扣减（演示药2 100-6）", stock2_now.get("quantity"), stock2["quantity"] - 6)

    # 10. 已发药后退费被拒 -> 400
    status, body = call("cashier", "POST", f"/payments/{payment['id']}/refund")
    expect("已发药不可退费（400）", (status, body.get("detail")), (400, "该就诊已发药，不能退费"))

    # 11. 审计日志有记录
    status, logs = call(None, "GET", "/audit/logs")
    expect("审计日志可查（200）", status, 200)
    has_entry = any(l["username"] == "cashier" and l["path"] == "/patients/" for l in logs)
    expect("审计日志包含收费员建档记录", has_entry, True)

    # 12. 对账汇总
    status, summary = call(None, "GET", "/payments/summary")
    expect("对账汇总可查（200）", status, 200)
    print(f"  汇总快照：已收 {summary['paid_count']} 笔 / {summary['paid_total']} 元，已退 {summary['refunded_count']} 笔 / {summary['refunded_total']} 元")

    # ============ 住院线 ============
    # 13. 病区与床位（幂等：病区复用、床位按床号探测）
    status, ward = call("admin", "POST", "/wards/", {"name": "演示住院病区"})
    expect("管理员建病区（201 或复用）", status, 201)
    status, beds = call(None, "GET", f"/wards/{ward['id']}/beds")
    expect("病区床位列表可查（200）", status, 200)
    by_code = {b["code"]: b for b in beds}
    for code in ("101", "102"):
        if code not in by_code:
            status, bed = call(
                "admin", "POST", "/beds/", {"ward_id": ward["id"], "code": code}
            )
            expect(f"管理员建床位 {code}（201）", status, 201)
            by_code[code] = bed
    expect("床位就绪（101/102）", sorted(by_code)[:2], ["101", "102"])

    # 14. 入院（收费员办理）
    status, admission = call(
        "cashier", "POST", "/admissions/",
        {"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": by_code["101"]["id"]},
    )
    expect("收费员办理入院（201 in）", (status, admission.get("status")), (201, "in"))
    status, bed_now = call(None, "GET", f"/beds/{by_code['101']['id']}")
    expect("床位 101 变为占用（occupied）", bed_now.get("status"), "occupied")

    # 15. 医生开长期医嘱 -> 护士执行两次 -> 住院计费
    status, in_order = call(
        "doctor", "POST", f"/admissions/{admission['id']}/orders",
        {"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "standing", "quantity": 2},
    )
    expect("医生开长期医嘱（201 standing/open）", (status, in_order.get("order_type"), in_order.get("status")), (201, "standing", "open"))
    for i in (1, 2):
        status, _ = call(f"nurse", "POST", f"/orders/{in_order['id']}/execute", {"note": f"第{i}次执行"})
        expect(f"护士执行医嘱第 {i} 次（201）", status, 201)
    status, bill = call(None, "GET", f"/admissions/{admission['id']}/bill")
    expect("住院账单（2 次执行 × 2 数量 × 15.0）", (status, bill.get("total_amount"), bill.get("charge_count")), (200, 60.0, 2))

    # 16. 出院 -> 床位释放 -> 出院后执行被拒
    status, _ = call("doctor", "POST", f"/admissions/{admission['id']}/discharge", None)
    expect("医生办理出院（200 discharged）", (status, _.get("status")), (200, "discharged"))
    status, bed_after = call(None, "GET", f"/beds/{by_code['101']['id']}")
    expect("床位 101 释放（empty）", bed_after.get("status"), "empty")
    status, body = call("nurse", "POST", f"/orders/{in_order['id']}/execute", {})
    expect("出院后不能再执行医嘱（400）", (status, body.get("detail")), (400, "该患者已出院，不能执行医嘱"))

    print("=" * 60)
    if failures:
        print(f"演示结束：{failures} 项断言失败（共 {step_no} 步）")
        return 1
    print(f"演示结束：全部 {step_no} 步断言通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
