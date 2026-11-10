"""服务端打包入口：先执行内置数据库初始化/迁移，再启动 uvicorn。

打包（PyInstaller onedir）后双击 exe 即可运行，无需安装 Python。
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.migrate import ensure_initial_admin, ensure_initial_director, ensure_schema
from app.settings import BASE_DIR, DATABASE_URL, HOST, PORT


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    print(f"程序目录: {BASE_DIR}")
    print(f"数据库:   {DATABASE_URL}")
    print(f"监听:     http://{HOST}:{PORT}")

    print("正在检查/升级数据库结构...")
    result = ensure_schema()
    labels = {
        "created": "新建数据库：已建表并标记 head",
        "stamped": "已存在业务表：已标记 head",
        "upgraded": "存量数据库：已升级到 head",
    }
    print(labels.get(result, "数据库已是最新"))

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        if ensure_initial_admin(db):
            print("已创建初始管理员：admin / admin123（请尽快修改密码）")
        if ensure_initial_director(db):
            print("已创建院长账号：director / director123（请尽快修改密码）")
    finally:
        db.close()

    print("数据库就绪，启动服务...")

    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
