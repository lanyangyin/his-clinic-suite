"""初始化数据库：uv run python scripts/init_db.py

- 全新库：建表并标记 Alembic 版本为 head
- 存量库：增量升级到 head
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.migrate import ensure_schema  # noqa: E402
from app.settings import BASE_DIR, DATABASE_URL  # noqa: E402


def main() -> int:
    print(f"程序目录: {BASE_DIR}")
    print(f"数据库:   {DATABASE_URL}")
    result = ensure_schema()
    labels = {
        "created": "新建数据库：已建表并标记 head",
        "stamped": "已存在业务表：已标记 head",
        "upgraded": "存量数据库：已升级到 head",
        "ok": "数据库已是最新",
    }
    print(labels.get(result, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
