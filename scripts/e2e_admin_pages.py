"""医保工作台 / GSP / 病案后台真实页面操作与截图。

管理员会话实际提交页面表单，再用 Edge 无头模式截图留证。
运行：.venv\\Scripts\\python.exe scripts\\e2e_admin_pages.py
产出：
    docs/screenshots/admin_insurance.png
    docs/screenshots/admin_gsp.png
    docs/screenshots/admin_archive.png
"""
import base64
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001"
ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / "docs" / "screenshots"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def basic(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def shot(session: requests.Session, path: str, name: str) -> None:
    page = session.get(BASE + path, timeout=30)
    assert page.status_code == 200, (path, page.status_code)
    html = ROOT / "docs" / f"{name}.html"
    html.write_text(page.text, encoding="utf-8")
    target = SHOT_DIR / f"{name}.png"
    target.unlink(missing_ok=True)
    profile = Path.home() / "AppData" / "Local" / "Temp" / f"his-{name}-{int(time.time())}"
    subprocess.run(
        [
            str(EDGE),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            f"--screenshot={target}",
            "--window-size=1500,1200",
            html.as_uri(),
        ],
        capture_output=True,
        timeout=120,
    )
    for _ in range(30):
        if target.is_file() and target.stat().st_size > 1000:
            break
        time.sleep(0.5)
    assert target.is_file(), f"截图未生成：{target}"


def main() -> int:
    suffix = datetime.now().strftime("%m%d%H%M%S")
    session = requests.Session()
    session.trust_env = False
    login = session.post(
        f"{BASE}/admin/login",
        data={"username": "admin", "password": "admin123"},
        allow_redirects=False,
        timeout=30,
    )
    assert login.status_code in (302, 303)
    admin = basic("admin", "admin123")
    cashier = basic("cashier", "cashier123")

    # 医保工作台：造一个未对码药品，确保风险可见
    drug = requests.post(
        f"{BASE}/drugs/",
        json={"name": f"后台未对码药{suffix}", "base_price": 6.0},
        headers=admin,
        timeout=30,
    ).json()
    insurance = session.get(f"{BASE}/admin/insurance-workbench", timeout=30)
    assert insurance.status_code == 200
    assert "医保工作台" in insurance.text
    assert "未对码" in insurance.text
    shot(session, "/admin/insurance-workbench", "admin_insurance")

    # GSP：验收、温湿度异常、不良反应、召回
    acceptance = session.post(
        f"{BASE}/admin/gsp/acceptances",
        data={
            "supplier_name": f"GSP后台供应商{suffix}",
            "delivery_no": f"GSP-PAGE-{suffix}",
            "transport_temp": "22",
            "transport_ok": "on",
            "item_name": f"GSP后台药{suffix}",
            "batch_no": f"GB-{suffix}",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": "10",
        },
        allow_redirects=False,
        timeout=30,
    )
    assert acceptance.status_code in (302, 303)
    session.post(
        f"{BASE}/admin/gsp/storage-logs",
        data={"area": "药房", "temperature": "32", "humidity": "80", "note": "页面验证"},
        allow_redirects=False,
        timeout=30,
    )
    session.post(
        f"{BASE}/admin/gsp/adverse-reactions",
        data={
            "patient_name": f"GSP患者{suffix}",
            "drug_name": f"GSP后台药{suffix}",
            "batch_no": f"GB-{suffix}",
            "reaction": "皮疹",
            "severity": "moderate",
        },
        allow_redirects=False,
        timeout=30,
    )
    session.post(
        f"{BASE}/admin/gsp/recalls",
        data={
            "drug_name": f"GSP后台药{suffix}",
            "batch_no": f"GB-{suffix}",
            "reason": "页面验证召回",
            "level": "2",
        },
        allow_redirects=False,
        timeout=30,
    )
    gsp = session.get(f"{BASE}/admin/gsp", timeout=30)
    assert gsp.status_code == 200
    assert f"GSP-PAGE-{suffix}" in gsp.text
    assert "异常" in gsp.text
    assert "皮疹" in gsp.text
    shot(session, "/admin/gsp", "admin_gsp")

    # 病案：建档 → 归档上架
    patient = requests.post(
        f"{BASE}/patients/",
        json={"name": f"病案后台患者{suffix}", "id_number": f"1101011996{suffix[-8:]}"},
        headers=cashier,
        timeout=30,
    ).json()
    created = session.post(
        f"{BASE}/admin/archive/records",
        data={"patient_id": patient["id"], "record_type": "outpatient", "note": "页面验证"},
        allow_redirects=False,
        timeout=30,
    )
    assert created.status_code in (302, 303)
    listing = session.get(f"{BASE}/admin/archive", timeout=30)
    ids = [int(x) for x in __import__("re").findall(r"/admin/archive\?record_id=(\d+)", listing.text)]
    record_id = max(ids)
    archived = session.post(
        f"{BASE}/admin/archive/records/{record_id}/archive",
        data={"storage_location": f"A-{suffix[-4:]}", "page_count": "12", "completeness": "complete"},
        allow_redirects=False,
        timeout=30,
    )
    assert archived.status_code in (302, 303)
    archive = session.get(f"{BASE}/admin/archive?record_id={record_id}", timeout=30)
    assert archive.status_code == 200
    assert "已归档" in archive.text
    assert f"A-{suffix[-4:]}" in archive.text
    shot(session, f"/admin/archive?record_id={record_id}", "admin_archive")

    print("医保 / GSP / 病案后台页面操作通过")
    print("截图：docs/screenshots/admin_insurance.png")
    print("截图：docs/screenshots/admin_gsp.png")
    print("截图：docs/screenshots/admin_archive.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
