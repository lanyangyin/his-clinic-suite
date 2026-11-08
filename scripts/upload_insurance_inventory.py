"""医保进销存定时上传（Mock 接收）。

用法：
  uv run python scripts/upload_insurance_inventory.py --days 1
  uv run python scripts/upload_insurance_inventory.py --start 2026-11-01 --end 2026-11-30

定时执行：
  Windows: schtasks /create /tn "HIS-医保进销存" /sc daily /st 01:30 ^
           /tr "D:\\HIS\\.venv\\Scripts\\python.exe D:\\HIS\\scripts\\upload_insurance_inventory.py --days 1"
  Linux:   30 1 * * * cd /opt/his && .venv/bin/python scripts/upload_insurance_inventory.py --days 1
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.modules.insurance_inventory.service import create_upload  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="医保进销存上传")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--days", type=int, default=1, help="回溯天数（配合默认日期）")
    parser.add_argument("--by", default="scheduler", help="操作人标识")
    args = parser.parse_args()

    today = date.today()
    end = date.fromisoformat(args.end) if args.end else today
    start = (
        date.fromisoformat(args.start)
        if args.start
        else end - timedelta(days=max(args.days, 1) - 1)
    )

    with SessionLocal() as db:
        try:
            upload = create_upload(db, start, end, created_by=args.by)
        except ValueError as e:
            print(f"上传失败：{e}")
            return 1
        print(
            f"上传成功：{upload.upload_no} 期间 {upload.start_date}~{upload.end_date} "
            f"{upload.record_count} 条 金额 {upload.total_amount:.2f} 状态 {upload.status}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
