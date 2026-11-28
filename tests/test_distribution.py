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


def test_download_client_redirects_to_clients_release(client, monkeypatch):
    monkeypatch.setattr(settings, "CLIENT_DOWNLOAD_URL", "")
    r = client.get("/download/client", follow_redirects=False)
    assert r.status_code == 307
    assert "clients-v1.0.3" in r.headers["location"]


def test_download_client_config_override(client, monkeypatch):
    url = "https://github.com/lanyangyin/his-clinic-suite/releases/latest/download/his-client.zip"
    monkeypatch.setattr(settings, "CLIENT_DOWNLOAD_URL", url)
    response = client.get("/download/client", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == url


def test_profile_download_redirects_and_unknown_404(client):
    response = client.get("/download/client/cashier", follow_redirects=False)
    assert response.status_code == 307
    assert "his-client-cashier-1.0.3.zip" in response.headers["location"]
    missing = client.get("/download/client/not-a-profile", follow_redirects=False)
    assert missing.status_code == 404
