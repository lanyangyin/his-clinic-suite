import base64
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.database as dbmod
import app.modules.auth.service as auth_service
from app.database import Base, get_db
from app.main import app
from app.modules.auth.schemas import UserCreate
from app.modules.auth.service import create_user

# 测试提速：测试不需要生产级 KDF 迭代强度
auth_service._ITERATIONS = 1_000

# 测试专用：临时文件 SQLite（跨线程访问比内存库可靠），不碰开发库 his.db
_TEST_DB = Path(tempfile.gettempdir()) / "his_pytest.db"
test_engine = create_engine(
    f"sqlite:///{_TEST_DB}",
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(test_engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    """并发测试需要：WAL 降低锁竞争 + 长 busy timeout。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# 让所有 get_db 调用方（含审计中间件）都使用测试库
dbmod.set_session_factory(TestingSessionLocal)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def basic_auth(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture(scope="session", autouse=True)
def _prepare_schema():
    """整个测试会话只建一次表（DDL 慢，避免每个用例重建）。"""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture(scope="session")
def test_client():
    """整个测试会话共用一个 TestClient（避免每个用例重建门户线程）。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client(test_client):
    """每个用例一个干净的数据状态（清空所有表）。"""
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    return test_client


@pytest.fixture()
def auth(client):
    """四个演示角色账号 + 各自的 Basic 认证头。"""
    demo_users = [
        UserCreate(username="admin", password="admin123", role="admin", display_name="管理员"),
        UserCreate(username="doctor", password="doctor123", role="doctor", display_name="陈医生"),
        UserCreate(username="nurse", password="nurse123", role="nurse", display_name="李护士"),
        UserCreate(username="cashier", password="cashier123", role="cashier", display_name="收费员"),
        UserCreate(username="pharmacist", password="pharm123", role="pharmacist", display_name="药师"),
        UserCreate(username="warehouse", password="warehouse123", role="warehouse", display_name="库房管理员"),
        UserCreate(username="lab", password="lab123", role="lab", display_name="检验技师"),
        UserCreate(username="radiology", password="rad123", role="radiology", display_name="影像技师"),
        UserCreate(username="archive", password="archive123", role="archive", display_name="病案管理员"),
        UserCreate(username="decoction", password="decoction123", role="decoction", display_name="煎药员"),
        UserCreate(username="surgery", password="surgery123", role="surgery", display_name="手术室护士"),
        UserCreate(username="treatment", password="treatment123", role="treatment", display_name="治疗室护士"),
    ]
    with TestingSessionLocal() as db:
        for data in demo_users:
            create_user(db, data)
    return {
        "admin": basic_auth("admin", "admin123"),
        "doctor": basic_auth("doctor", "doctor123"),
        "nurse": basic_auth("nurse", "nurse123"),
        "cashier": basic_auth("cashier", "cashier123"),
        "pharmacist": basic_auth("pharmacist", "pharm123"),
        "warehouse": basic_auth("warehouse", "warehouse123"),
        "lab": basic_auth("lab", "lab123"),
        "radiology": basic_auth("radiology", "rad123"),
        "archive": basic_auth("archive", "archive123"),
        "decoction": basic_auth("decoction", "decoction123"),
        "surgery": basic_auth("surgery", "surgery123"),
        "treatment": basic_auth("treatment", "treatment123"),
    }
