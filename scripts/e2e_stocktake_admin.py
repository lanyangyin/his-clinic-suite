"""盘点后台真实页面操作 + 打印验证。

用管理员会话实际打开/提交盘点页面：
  新建盘点单 → 录入实盘 → 完成盘点 → 校验库存
再保存完成后的页面，用 Edge 无头模式生成打印 PDF 和页面截图。

运行：
    .venv\\Scripts\\python.exe scripts\\e2e_stocktake_admin.py
产出：
    docs/盘点单打印预览.pdf
    docs/screenshots/stocktake_admin.png
"""
import base64
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001"
ROOT = Path(__file__).resolve().parent.parent
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
PDF_PATH = ROOT / "docs" / "盘点单打印预览.pdf"
SHOT_PATH = ROOT / "docs" / "screenshots" / "stocktake_admin.png"
HTML_PATH = ROOT / "docs" / "stocktake_admin_preview.html"


def basic(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def main() -> int:
    session = requests.Session()
    session.trust_env = False
    session.headers["User-Agent"] = "HIS-stocktake-check"

    login = session.post(
        f"{BASE}/admin/login",
        data={"username": "admin", "password": "admin123"},
        allow_redirects=False,
        timeout=30,
    )
    assert login.status_code in (302, 303), login.status_code
    admin = basic("admin", "admin123")
    warehouse = basic("warehouse", "warehouse123")
    suffix = datetime.now().strftime("%m%d%H%M%S")

    drug = requests.post(
        f"{BASE}/drugs/",
        json={"name": f"盘点页面药{suffix}", "base_price": 9.5},
        headers=admin,
        timeout=30,
    ).json()
    purchase = requests.post(
        f"{BASE}/warehouse/purchase",
        json={
            "drug_id": drug["id"],
            "batch_no": f"STPAGE-{suffix}",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 10,
        },
        headers=admin,
        timeout=30,
    )
    assert purchase.status_code == 201, purchase.text

    created = session.post(
        f"{BASE}/admin/stocktakes",
        data={
            "kind": "drug",
            "warehouse": "总库",
            "title": f"盘点页面验证{suffix}",
            "note": "实际页面操作",
        },
        allow_redirects=False,
        timeout=30,
    )
    assert created.status_code in (302, 303), created.text
    takes = requests.get(
        f"{BASE}/stocktakes", headers=warehouse, timeout=30
    ).json()
    take = next(row for row in takes if row["title"] == f"盘点页面验证{suffix}")
    take_id = take["id"]

    detail = session.get(f"{BASE}/admin/stocktakes/{take_id}", timeout=30)
    assert detail.status_code == 200
    assert 'name="actual_' in detail.text, "盘点页面没有实盘输入框"
    target = next(row for row in take["items"] if row["drug_id"] == drug["id"])
    data = {
        f"actual_{row['id']}": str(row["book_quantity"]) for row in take["items"]
    }
    data[f"actual_{target['id']}"] = str(max(target["book_quantity"] - 1, 0))
    saved = session.post(
        f"{BASE}/admin/stocktakes/{take_id}/counts",
        data=data,
        allow_redirects=False,
        timeout=30,
    )
    assert saved.status_code in (302, 303)
    before = session.get(f"{BASE}/admin/stocktakes/{take_id}", timeout=30)
    assert "盘点中" in before.text

    completed = session.post(
        f"{BASE}/admin/stocktakes/{take_id}/complete",
        allow_redirects=False,
        timeout=30,
    )
    assert completed.status_code in (302, 303)
    page = session.get(f"{BASE}/admin/stocktakes/{take_id}", timeout=30)
    assert page.status_code == 200
    assert "已完成" in page.text
    assert "打印盘点单" in page.text
    assert "@media print" in page.text

    stocks = requests.get(
        f"{BASE}/warehouse/stocks?drug_id={drug['id']}", headers=admin, timeout=30
    ).json()
    assert stocks and stocks[0]["quantity"] == 9, stocks

    HTML_PATH.write_text(page.text, encoding="utf-8")
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    SHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PDF_PATH.unlink(missing_ok=True)
    SHOT_PATH.unlink(missing_ok=True)
    stamp = str(int(datetime.now().timestamp()))
    pdf_profile = Path.home() / "AppData" / "Local" / "Temp" / f"his-edge-pdf-{stamp}"
    shot_profile = Path.home() / "AppData" / "Local" / "Temp" / f"his-edge-shot-{stamp}"
    common = [
        str(EDGE),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    subprocess.run(
        common
        + [
            f"--user-data-dir={pdf_profile}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={PDF_PATH}",
            HTML_PATH.as_uri(),
        ],
        capture_output=True,
        timeout=120,
    )
    subprocess.run(
        common
        + [
            f"--user-data-dir={shot_profile}",
            f"--screenshot={SHOT_PATH}",
            "--window-size=1400,1200",
            HTML_PATH.as_uri(),
        ],
        capture_output=True,
        timeout=120,
    )

    def wait_file(path: Path) -> bool:
        for _ in range(30):
            if path.is_file() and path.stat().st_size > 1000:
                return True
            time.sleep(0.5)
        return False

    assert wait_file(PDF_PATH), "打印 PDF 未生成"
    assert wait_file(SHOT_PATH), "页面截图未生成"

    print("盘点后台页面操作通过")
    print(f"盘点单：{take['take_no']} / id={take_id}")
    print(f"库存：10 -> 9")
    print(f"打印 PDF：{PDF_PATH}")
    print(f"页面截图：{SHOT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
