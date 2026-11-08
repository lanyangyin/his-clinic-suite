from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.settings import DATABASE_URL

SQLALCHEMY_DATABASE_URL = DATABASE_URL

_connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # timeout：写锁竞争时等待而非立即失败（并发挂号/收费场景）
    _connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, connection_record):
        """并发友好设置：WAL 允许读写并行；busy_timeout 让写入排队等待。"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def set_session_factory(factory):
    """测试隔离钩子：替换会话工厂。

    中间件等直接调用 get_db 的代码依赖模块级 SessionLocal，
    测试中将其指向测试库，避免审计日志写入开发库。
    """
    global SessionLocal
    SessionLocal = factory

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
