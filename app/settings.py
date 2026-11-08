"""服务端运行配置：程序目录基准 + config.ini + 环境变量覆盖。

原则：所有运行期文件（数据库、备份、日志）都相对**程序所在目录**，
与启动时的工作目录无关；换机器/换目录只需整体拷贝。
"""
import configparser
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：exe 所在目录
    BASE_DIR = Path(sys.executable).resolve().parent
    # PyInstaller 数据文件目录（--add-data 内容）
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    # 源码运行：项目根目录（app/settings.py 的上一级）
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR

# 管理台模板目录（打包后位于 _MEIPASS 数据目录）
ADMIN_TEMPLATES_DIR = BUNDLE_DIR / "app" / "modules" / "admin" / "templates"
# 内置的 Alembic 脚本目录（打包版启动时自动升级数据库）
ALEMBIC_DIR = BUNDLE_DIR / "alembic"
ALEMBIC_INI = BUNDLE_DIR / "alembic.ini"


def _load_ini() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    # 先读主配置，再用本地覆盖配置（config.local.ini，不入库；后读的覆盖前面的）
    for candidate in (
        BASE_DIR / "config.ini",
        Path.cwd() / "config.ini",
        BASE_DIR / "config.local.ini",
        Path.cwd() / "config.local.ini",
    ):
        if candidate.is_file():
            parser.read(candidate, encoding="utf-8")
    return parser


_ini = _load_ini()

# 监听地址：局域网部署用 0.0.0.0；仅本机用 127.0.0.1
HOST = os.environ.get("HIS_HOST") or _ini.get("server", "host", fallback="0.0.0.0")
PORT = int(os.environ.get("HIS_PORT") or _ini.get("server", "port", fallback="8000"))
SECRET_KEY = (
    os.environ.get("HIS_SECRET_KEY")
    or _ini.get("server", "secret_key", fallback="his-dev-secret-change-me-0123456789")
)

# 数据库：默认程序目录下 his.db（绝对路径，与 CWD 无关）
_DEFAULT_DB_PATH = BASE_DIR / "his.db"
DATABASE_URL = (
    os.environ.get("HIS_DATABASE_URL")
    or _ini.get("database", "url", fallback="")
    or f"sqlite:///{_DEFAULT_DB_PATH.as_posix()}"
)

# 客户端下载包位置（相对程序目录）
CLIENT_ZIP_PATH = BASE_DIR / "dist" / "his-client.zip"

# 备份目录
BACKUP_DIR = BASE_DIR / "backups"
