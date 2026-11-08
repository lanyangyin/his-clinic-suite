"""并发正确性测试：抢号源 / 双收 / 扣库存 / 摆药单。

SQLite 的单写锁会让并发串行化，这正好用来验证"条件 UPDATE 原子性"本身：
每个线程独立 Session 调 service 层，断言最终计数恰好等于容量/一次。
"""
import time
from concurrent.futures import ThreadPoolExecutor

from app.modules.billing.schemas import PaymentCreate
from app.modules.billing.service import create_payment
from app.modules.inpatient.schemas import AdmissionCreate, OrderCreate
from app.modules.inpatient.service import (
    create_admission,
    create_dispense_request,
    create_order,
    dispense_request,
)
from app.modules.patient.schemas import PatientCreate
from app.modules.patient.service import create_patient
from app.modules.pharmacy.models import DrugStock
from app.modules.pharmacy.schemas import DispenseRequest, StockInRequest
from app.modules.pharmacy.service import dispense, stock_in
from app.modules.registration.schemas import RegistrationCreate, ScheduleCreate
from app.modules.registration.service import create_registration, create_schedule
from app.modules.staff.schemas import DepartmentCreate, DoctorCreate
from app.modules.staff.service import create_department, create_doctor
from tests.conftest import TestingSessionLocal


def _run_concurrently(fn, count: int, max_workers: int = 8):
    """用独立 Session 并发执行 fn(db, index)，收集 (状态, 返回/错误) 列表。

    SQLite 在极端写竞争下可能立即返回 "database is locked"，
    这里对 OperationalError 做有限重试（与生产客户端重试行为一致）。
    """
    from sqlalchemy.exc import OperationalError

    def worker(index: int):
        for attempt in range(5):
            db = TestingSessionLocal()
            try:
                return ("ok", fn(db, index))
            except ValueError as e:
                return ("value_error", str(e))
            except OperationalError as e:
                db.rollback()
                if attempt < 4:
                    time.sleep(0.05 + 0.05 * attempt)
                    continue
                return ("db_error", str(e))
            finally:
                db.close()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(worker, range(count)))


def _setup_schedule(client, auth, capacity=5):
    department = client.post(
        "/departments/", json={"name": "并发科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "并发医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    schedule = client.post(
        "/schedules/",
        json={
            "doctor_id": doctor["id"],
            "schedule_date": "2026-12-01",
            "period": "morning",
            "capacity": capacity,
        },
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/",
        json={"name": "并发患者", "id_number": "110101199901011234"},
        headers=auth["cashier"],
    ).json()
    return patient, doctor, schedule


def test_schedule_no_oversell(client, auth):
    patient, doctor, schedule = _setup_schedule(client, auth, capacity=5)

    def register(db, index):
        return create_registration(
            db,
            RegistrationCreate(
                patient_id=patient["id"],
                doctor_id=doctor["id"],
                schedule_id=schedule["id"],
            ),
        ).id

    results = _run_concurrently(register, count=10)
    successes = [r for r in results if r[0] == "ok"]
    failures = [r for r in results if r[0] == "value_error"]

    assert len(successes) == 5, f"应恰好 5 个成功: {results}"
    assert len(failures) == 5
    assert all("号源已满" in msg for _, msg in failures)

    booked = client.get(f"/schedules/{schedule['id']}").json()["booked"]
    assert booked == 5


def test_payment_single_charge(client, auth):
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )

    def pay(db, index):
        return create_payment(db, PaymentCreate(encounter_id=encounter["id"])).id

    results = _run_concurrently(pay, count=10)
    successes = [r for r in results if r[0] == "ok"]
    assert len(successes) == 1, f"应恰好 1 笔成功: {results}"

    payments = client.get(f"/payments/?encounter_id={encounter['id']}").json()
    assert len(payments) == 1


def test_stock_never_negative(client, auth):
    patient = client.post(
        "/patients/", json={"name": "李四", "id_number": "110101199501011234"},
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
    drug = client.post(
        "/drugs/", json={"name": "库存药", "base_price": 5.0}, headers=auth["admin"]
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": "C001", "expiry": "2027-06-30", "quantity": 10},
        headers=auth["pharmacist"],
    )

    # 5 个已收费就诊，每个处方 3 支（库存 10 只够 3 个）
    encounters = []
    for _ in range(5):
        reg = client.post(
            "/registrations/",
            json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
            headers=auth["cashier"],
        ).json()
        encounter = client.post(
            "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
        ).json()
        client.post(
            f"/encounters/{encounter['id']}/prescriptions",
            json={"drug_id": drug["id"], "quantity": 3},
            headers=auth["doctor"],
        )
        client.post(
            "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
        )
        encounters.append(encounter)

    def dispense_one(db, index):
        return dispense(db, DispenseRequest(encounter_id=encounters[index % len(encounters)]["id"])).id

    results = _run_concurrently(dispense_one, count=10)
    successes = [r for r in results if r[0] == "ok"]
    assert len(successes) == 3, f"10 单位库存、每单 3 支，应恰好 3 单成功: {results}"

    db = TestingSessionLocal()
    try:
        remaining = (
            db.query(DrugStock)
            .filter(DrugStock.drug_id == drug["id"])
            .order_by(DrugStock.id)
            .first()
            .quantity
        )
    finally:
        db.close()
    assert remaining >= 0
    assert remaining == 1  # 10 - 3*3


def test_dispense_request_single(client, auth):
    ward = client.post(
        "/wards/", json={"name": "并发病区"}, headers=auth["admin"]
    ).json()
    bed = client.post(
        "/beds/", json={"ward_id": ward["id"], "code": "1"}, headers=auth["admin"]
    ).json()
    patient = client.post(
        "/patients/", json={"name": "王五", "id_number": "110101199601011234"},
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
    drug = client.post(
        "/drugs/", json={"name": "住院药", "base_price": 8.0}, headers=auth["admin"]
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": "R001", "expiry": "2027-06-30", "quantity": 100},
        headers=auth["pharmacist"],
    )
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": bed["id"]},
        headers=auth["cashier"],
    ).json()
    order = client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "standing", "quantity": 2},
        headers=auth["doctor"],
    ).json()
    request = client.post(
        f"/orders/{order['id']}/dispense-request", headers=auth["nurse"]
    ).json()

    def dispense_req(db, index):
        return dispense_request(db, request["id"]).id

    results = _run_concurrently(dispense_req, count=10)
    successes = [r for r in results if r[0] == "ok"]
    assert len(successes) == 1, f"摆药单应只发一次: {results}"
    got = client.get(f"/dispense-requests/{request['id']}").json()
    assert got["status"] == "dispensed"
