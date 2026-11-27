from pathlib import Path

from app import settings
from app.modules.download import router as download_module


def test_version(client):
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["name"]
    assert body["version"]
    assert body["client_min_version"]


def test_auth_me(client, auth):
    r = client.get("/auth/me", headers=auth["admin"])
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert r.json()["role"] == "admin"

    assert client.get("/auth/me").status_code == 401

    bad = client.get("/auth/me", headers={"Authorization": "Basic " + "YWRtaW46d3Jvbmc="})
    assert bad.status_code == 401


def test_download_client_without_package(client, monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_DOWNLOAD_URL", "")
    monkeypatch.setattr(download_module, "CLIENT_ZIP", Path("missing-client-package.zip"))
    r = client.get("/download/client")
    assert r.status_code == 404
    assert "客户端安装包尚未生成" in r.json()["detail"]


def test_download_client_with_package(client, monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_DOWNLOAD_URL", "")
    path = Path("tmp_fake_client.zip")
    try:
        path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
        monkeypatch.setattr(download_module, "CLIENT_ZIP", path)
        r = client.get("/download/client")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
    finally:
        path.unlink(missing_ok=True)


def test_download_client_redirects_to_github(client, monkeypatch):
    url = "https://github.com/lanyangyin/his-clinic-suite/releases/latest/download/his-client.zip"
    monkeypatch.setattr(settings, "CLIENT_DOWNLOAD_URL", url)
    response = client.get("/download/client", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == url


def test_profile_download_redirects_and_unknown_404(client):
    response = client.get("/download/client/cashier", follow_redirects=False)
    assert response.status_code == 307
    assert "his-client-cashier-1.0.1.zip" in response.headers["location"]
    missing = client.get("/download/client/not-a-profile", follow_redirects=False)
    assert missing.status_code == 404
