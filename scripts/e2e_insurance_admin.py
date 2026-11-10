"""医保 / 收费后台真实页面操作与截图。

管理员会话实际导入医保目录、对码、上传进销存，并截取目录、工作台、进销存、发票页。
产出：docs/screenshots/insurance_catalog.png 等。
"""
import base64
import subprocess
import time
from datetime import date, datetime
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001"
ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / "docs" / "screenshots"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def basic(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def shot(session: requests.Session, path: str, name: str) -> Path:
    page = session.get(BASE + path, timeout=30)
    assert page.status_code == 200, (path, page.status_code)
    html = ROOT / "docs" / f"{name}.html"
    html.write_text(page.text, encoding="utf-8")
    target = SHOT_DIR / f"{name}.png"
    target.unlink(missing_ok=True)
    profile = Path.home() / "AppData" / "Local" / "Temp" / f"his-{name}-{int(time.time())}"
    subprocess.run(
        [
            str(EDGE), "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", f"--user-data-dir={profile}",
            f"--screenshot={target}", "--window-size=1500,1200", html.as_uri(),
        ],
        capture_output=True,
        timeout=120,
    )
    for _ in range(30):
        if target.is_file() and target.stat().st_size > 1000:
            break
        time.sleep(0.5)
    assert target.is_file(), target
    return target


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

    code = f"INS{suffix}"
    csv = (
        "national_code,name,category,spec,unit\n"
        f"{code},医保后台演示药{suffix},甲,10mg,盒\n"
    ).encode("utf-8-sig")
    imported = requests.post(
        f"{BASE}/insurance/catalog/import",
        files={"file": (f"catalog_{suffix}.csv", csv, "text/csv")},
        headers=admin,
        timeout=30,
    )
    assert imported.status_code == 200, imported.text
    drug = requests.post(
        f"{BASE}/drugs/",
        json={"name": f"医保后台匹配药{suffix}", "base_price": 18, "insurance_code": code},
        headers=admin,
        timeout=30,
    ).json()
    matched = requests.post(
        f"{BASE}/insurance/catalog/match?only_unmatched=true", headers=admin, timeout=30
    ).json()
    assert matched["matched"] >= 1
    resolved = requests.get(
        f"{BASE}/insurance/catalog/resolve/{drug['id']}", headers=admin, timeout=30
    ).json()
    assert resolved["insurance_code"] == code
    today = date.today().isoformat()
    upload = requests.post(
        f"{BASE}/insurance/inventory/upload",
        json={"start_date": today, "end_date": today},
        headers=admin,
        timeout=30,
    ).json()
    assert upload["upload_no"]

    shot(session, "/admin/insurance-catalog", "insurance_catalog")
    shot(session, "/admin/insurance-workbench", "insurance_workbench")
    shot(session, "/admin/insurance-inventory", "insurance_inventory")
    shot(session, "/admin/invoice-batches", "invoice_batches")
    print(f"医保目录导入/对码/进销存上传通过：{code} / {upload['upload_no']}")
    print("截图：docs/screenshots/insurance_catalog.png")
    print("截图：docs/screenshots/insurance_workbench.png")
    print("截图：docs/screenshots/insurance_inventory.png")
    print("截图：docs/screenshots/invoice_batches.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
