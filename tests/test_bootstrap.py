from app.migrate import ensure_initial_admin
from tests.conftest import TestingSessionLocal


def test_initial_admin_created_once(client):
    db = TestingSessionLocal()
    try:
        assert ensure_initial_admin(db) is True
        assert ensure_initial_admin(db) is False
    finally:
        db.close()

    # 初始管理员可直接登录
    import base64

    token = base64.b64encode(b"admin:admin123").decode()
    me = client.get("/auth/me", headers={"Authorization": f"Basic {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
