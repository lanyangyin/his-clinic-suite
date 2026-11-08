"""医保药品目录同步：手动/定时拉取更新。

用法：
  uv run python scripts/sync_insurance_catalog.py                  # 读 config.ini [insurance_catalog] url
  uv run python scripts/sync_insurance_catalog.py --url <URL>      # 指定 URL
  uv run python scripts/sync_insurance_catalog.py --file <路径>    # 本地文件（CSV/XLSX）

定时执行（Windows 任务计划 / Linux cron）：
  Windows: schtasks /create /tn "HIS-医保目录同步" /sc daily /st 02:00 ^
           /tr "D:\HIS\.venv\Scripts\python.exe D:\HIS\scripts\sync_insurance_catalog.py"
  Linux:   0 2 * * * cd /opt/his && .venv/bin/python scripts/sync_insurance_catalog.py
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.modules.insurance_catalog.service import import_bytes, sync_from_url  # noqa: E402
from app.settings import BASE_DIR  # noqa: E402


def _url_from_config() -> str:
    import configparser

    parser = configparser.ConfigParser()
    for candidate in (BASE_DIR / "config.ini", BASE_DIR / "config.local.ini"):
        if candidate.is_file():
            parser.read(candidate, encoding="utf-8")
    return parser.get("insurance_catalog", "url", fallback="").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="医保药品目录同步")
    parser.add_argument("--url", help="目录文件 URL")
    parser.add_argument("--file", help="本地 CSV/XLSX 文件")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.file:
            path = Path(args.file)
            if not path.is_file():
                print(f"[错误] 文件不存在：{path}")
                return 1
            result = import_bytes(
                db,
                path.read_bytes(),
                file_name=path.name,
                source="auto",
                imported_by="scheduler",
            )
        else:
            url = args.url or _url_from_config()
            if not url:
                print("[错误] 未提供 URL，且 config.ini 未配置 [insurance_catalog] url")
                return 1
            result = sync_from_url(db, url, imported_by="scheduler")
    except ValueError as e:
        print(f"[失败] {e}")
        return 1
    finally:
        db.close()

    print(
        f"[{result['status']}] 版本={result.get('version')} "
        f"新增={result['inserted']} 更新={result['updated']} "
        f"跳过={result['skipped']} 行数={result['row_count']}"
    )
    return 0 if result["status"] in ("created", "unchanged") else 1


if __name__ == "__main__":
    raise SystemExit(main())
