"""客户端全流程冒烟：用 his_client.ApiClient 走真实服务端。

覆盖：建档/挂号 → 分诊 → 接诊/病历/开方/检验/检查/治疗 → 收费 → 入库/发药 → 治疗执行 → 打印。
用法：uv run python scripts/check_client_flow.py [base_url]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from his_client.api import ApiClient, ApiError  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
EXPECTED_STEPS = 18
ok = 0


def step(name: str, condition: bool, detail: str = "") -> None:
    global ok
    if condition:
        ok += 1
        print(f"[PASS] {name}{(' | ' + detail) if detail else ''}")
    else:
        print(f"[FAIL] {name}{(' | ' + detail) if detail else ''}")


def main() -> int:
    cashier = ApiClient(BASE, "cashier", "cashier123")
    doctor = ApiClient(BASE, "doctor", "doctor123")
    nurse = ApiClient(BASE, "nurse", "nurse123")
    pharmacist = ApiClient(BASE, "pharmacist", "pharm123")

    doctors = cashier.list_doctors()
    doctor_id = doctors[0]["id"]
    suffix = str(int(time.time()))[-8:]
    patient = cashier.create_patient(f"客户端冒烟{suffix}", f"110101{suffix}0000", "13800138000")
    step("建档", patient["id"] > 0, f"patient {patient['id']}")

    registration = cashier.create_registration(patient["id"], doctor_id)
    step("挂号", registration["status"] == "registered", f"reg {registration['id']}")

    ticket = nurse.create_triage_ticket(registration["id"])
    queue = nurse.triage_queue()
    step("分诊登记", any(t["id"] == ticket["id"] for t in queue), f"ticket {ticket['id']}")
    nurse.call_ticket(ticket["id"])
    step("叫号", nurse.triage_queue() is not None)

    encounter = doctor.create_encounter(registration["id"], "上呼吸道感染")
    step("接诊", encounter["id"] > 0, f"encounter {encounter['id']}")

    record = doctor.create_medical_record(
        encounter["id"],
        {"chief_complaint": "发热咳嗽 2 天", "treatment_advice": "多饮水休息"},
    )
    step("病历", record["chief_complaint"] == "发热咳嗽 2 天")
    quality = doctor.medical_record_quality(encounter["id"])
    step("病历质控", 0 <= quality["score"] <= 100, f"score {quality['score']}")

    drugs = doctor.list_drugs()
    prescription = doctor.add_prescription(
        encounter["id"],
        {
            "drug_id": drugs[0]["id"],
            "quantity": 2,
            "dosage": "0.5g",
            "frequency": "tid",
            "route": "口服",
            "days": 3,
        },
    )
    step("开方（含用法）", prescription["days"] == 3, prescription["drug_name"])

    lab_items = doctor.list_lab_items()
    lab = doctor.create_lab_request(encounter["id"], lab_items[0]["id"])
    step("检验开单", lab["status"] == "pending", lab["item_name"])

    imaging_items = doctor.list_imaging_items()
    imaging = doctor.create_imaging_request(encounter["id"], imaging_items[0]["id"])
    step("检查开单", imaging["status"] == "pending", imaging["item_name"])

    treatment_items = doctor.list_charge_items("treatment")
    treatment = doctor.create_treatment(encounter["id"], treatment_items[0]["id"], 1, "静滴")
    step("治疗开单", treatment["status"] == "pending", treatment["item_name"])

    charges = cashier.get_charges(encounter["id"])
    step("费用明细", len(charges) >= 4, f"{len(charges)} 条")
    payment = cashier.create_payment(encounter["id"])
    step("收费", payment["status"] == "paid", f"{payment['amount']:.2f} 元")

    pharmacist.stock_in(
        {
            "drug_id": drugs[0]["id"],
            "batch_no": f"SMOKE-{suffix}",
            "expiry": "2027-12-31",
            "location": "T-01",
            "quantity": 100,
        }
    )
    dispense = pharmacist.dispense(encounter["id"])
    step("发药", dispense["id"] > 0)
    stocks = pharmacist.list_stocks(drugs[0]["id"])
    step("库存查询", len(stocks) > 0, f"{len(stocks)} 批次")

    pending = nurse.list_pending_treatments()
    target = next((o for o in pending if o["encounter_id"] == encounter["id"]), None)
    if target:
        executed = nurse.execute_treatment(target["id"])
        step("治疗执行", executed["status"] == "done", executed["executed_by"])
    else:
        step("治疗执行", False, "未找到待执行治疗单")

    import urllib.request

    for label, url in (
        ("处方打印", doctor.prescription_print_url(encounter["id"])),
        ("小票打印", doctor.receipt_print_url(payment["id"])),
    ):
        with urllib.request.urlopen(url, timeout=10) as resp:
            step(label, resp.status == 200, f"HTTP {resp.status}")

    total = ok
    print(f"==== 客户端全流程：{total}/{EXPECTED_STEPS} 项通过 ====")
    return 0 if total == EXPECTED_STEPS else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ApiError as e:
        print(f"[FAIL] API 错误 {e.status_code}: {e.detail}")
        sys.exit(1)
