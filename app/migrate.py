"""数据库初始化/升级：兼容"全新库"与"存量库"两条路径。

背景：早期迁移并非从零基线（0001 假设基础表已由模型创建），
因此新库用 Base.metadata.create_all 建表后 stamp head；
已有 alembic_version 的存量库继续走增量迁移。
"""
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app import settings


def ensure_schema() -> str:
    """确保数据库结构为最新，返回 created / upgraded / ok。"""
    # 确保所有模型已注册到 Base.metadata
    import app.main  # noqa: F401

    from app.database import Base, engine

    config = Config(str(settings.ALEMBIC_INI))
    config.set_main_option("script_location", str(settings.ALEMBIC_DIR))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables and "users" not in tables:
        Base.metadata.create_all(engine)
        command.stamp(config, "head")
        return "created"
    if "alembic_version" not in tables:
        # 有业务表但没有版本表（历史遗留）：直接标记为 head，避免重复建表
        command.stamp(config, "head")
        return "stamped"
    command.upgrade(config, "head")
    return "upgraded"


def ensure_initial_admin(db) -> bool:
    """全新部署时创建初始管理员 admin/admin123；已存在则跳过。

    返回 True 表示本次创建了初始账号（调用方应提示尽快修改密码）。
    """
    from app.modules.auth.schemas import UserCreate
    from app.modules.auth.service import create_user, get_user_by_username

    if get_user_by_username(db, "admin"):
        return False
    create_user(
        db,
        UserCreate(
            username="admin",
            password="admin123",
            role="admin",
            display_name="管理员",
        ),
    )
    return True
