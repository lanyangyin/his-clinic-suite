"""服务端启动入口：读取 config.ini 的 host/port（也可用 HIS_HOST/HIS_PORT 覆盖）。

用法：uv run python scripts/run_server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

from app.settings import BASE_DIR, DATABASE_URL, HOST, PORT  # noqa: E402


def main() -> int:
    print(f"数据目录: {BASE_DIR}")
    print(f"数据库:   {DATABASE_URL}")
    print(f"监听:     http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
