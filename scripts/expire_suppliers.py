"""供应商证照过期批量停用：供 cron / Windows Task Scheduler 调用。

用法：
    python scripts/expire_suppliers.py           # 只统计，不改数据
    python scripts/expire_suppliers.py --apply   # 真正停用
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.modules.supplier.service import suspend_expired


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="实际写入停用状态")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.apply:
            count = suspend_expired(db)
            print(f"已停用 {count} 家证照过期供应商")
        else:
            from datetime import date

            from app.modules.supplier.models import Supplier

            count = (
                db.query(Supplier)
                .filter(
                    Supplier.status == "active",
                    Supplier.license_expiry.is_not(None),
                    Supplier.license_expiry < date.today(),
                )
                .count()
            )
            print(f"待停用 {count} 家证照过期供应商（dry-run；加 --apply 执行）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
