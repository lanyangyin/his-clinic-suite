"""并发验证脚本：10 个并发挂号抢 1 个 5 号源排班，应恰好 5 个成功。

前提：服务已启动（uv run uvicorn app.main:app --reload），演示账号已种子。

用法：uv run python scripts/check_concurrency.py [base_url]
"""
import base64
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def call(method: str, path: str, payload: dict | None = None, auth: tuple | None = None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        req.add_header("Content-Type", "application/json")
        req.data = body
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def main() -> int:
    admin = ("admin", "admin123")
    cashier = ("cashier", "cashier123")

    # 准备：排班（capacity=5）+ 已建档患者
    status, doctor = call("GET", "/doctors/1", auth=admin)
    if status != 200:
        print("[FAIL] 医生 1 不存在，请先运行 scripts/seed_demo.py")
        return 1
    capacity = 5
    # 每次运行用不同日期，保证号源从 0 开始（脚本可重复运行）
    schedule_date = (
        dt.date.today() + dt.timedelta(days=500 + int(time.time()) % 1000)
    ).isoformat()
    status, schedule = call(
        "POST",
        "/schedules/",
        {"doctor_id": doctor["id"], "schedule_date": schedule_date, "period": "morning", "capacity": capacity},
        auth=admin,
    )
    if status == 400 and "已有排班" in str(schedule.get("detail", "")):
        # 幂等：复用已存在的排班
        _, rows = call(
            "GET", f"/doctors/{doctor['id']}/schedules?schedule_date={schedule_date}", auth=admin
        )
        schedule = next((row for row in rows if row["period"] == "morning"), None)
        if not schedule:
            print("[FAIL] 无法复用已存在的排班")
            return 1
    elif status not in (200, 201):
        print(f"[FAIL] 建排班失败: {status} {schedule}")
        return 1

    status, patient = call(
        "POST", "/patients/",
        {"name": "并发压测患者", "id_number": "110101203001011234"},
        auth=cashier,
    )
    if status not in (200, 201):
        print(f"[FAIL] 建档失败: {status} {patient}")
        return 1
    id_number = patient["id_number"]

    # 并发：20 个线程同时自助挂号抢 5 个号源
    def register(_):
        return call(
            "POST",
            "/kiosk/registrations",
            {"patient_id_number": id_number, "doctor_id": doctor["id"], "schedule_id": schedule["id"]},
        )

    workers = 20
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(register, range(workers)))

    successes = [r for r in results if r[0] == 201]
    failures = [r for r in results if r[0] == 400]
    others = [r for r in results if r[0] not in (201, 400)]

    status, final = call("GET", f"/schedules/{schedule['id']}", auth=admin)
    booked = final.get("booked")

    print(f"并发 {workers} 请求抢 {capacity} 个号源：成功 {len(successes)} / 失败 {len(failures)} / 其他 {len(others)}")
    print(f"排班 booked = {booked} / capacity {capacity}")
    if others:
        print(f"其他响应: {others[:3]}")
    if len(successes) == capacity and booked == capacity and len(failures) == workers - capacity:
        print("[PASS] 号源未超卖")
        return 0
    print("[FAIL] 出现超卖或异常")
    return 1


if __name__ == "__main__":
    sys.exit(main())
