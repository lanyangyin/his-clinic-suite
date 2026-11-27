"""独立岗位客户端、版本与兼容矩阵。"""
from app.client_compat import CLIENT_COMPATIBILITY, check_client
from app.main import app
from app.modules.auth.service import ROLES
from his_client.profiles import CLIENT_PROFILES


def test_every_role_has_a_dedicated_client():
    covered = set()
    for key, profile in CLIENT_PROFILES.items():
        if key == "universal":
            continue
        covered.update(profile.roles)
    # admin 是通用管理端；其余 15 个岗位都应有独立客户端
    assert set(ROLES) - {"admin"} <= covered


def test_client_tabs_are_known_and_unique():
    from his_client.ui.main_window import _TAB_BUILDERS

    for key, profile in CLIENT_PROFILES.items():
        if key == "universal":
            continue
        assert profile.tabs, key
        assert len(profile.tabs) == len(set(profile.tabs)), key
        assert set(profile.tabs) <= set(_TAB_BUILDERS), key


def test_versions_are_independent():
    from app.version import APP_VERSION
    from his_client import CLIENT_VERSION

    assert APP_VERSION == "2.0.0"
    assert CLIENT_VERSION == "1.0.0"
    assert all(profile.version == "1.0.0" for profile in CLIENT_PROFILES.values())
    assert set(CLIENT_COMPATIBILITY) == set(CLIENT_PROFILES)


def test_compatibility_matrix(client):
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["server_version"] == "2.0.0"
    assert body["clients"]["cashier"]["min"] == "1.0.0"
    ok = client.get(
        "/client/compatibility", params={"profile": "cashier", "version": "1.0.0"}
    )
    assert ok.status_code == 200
    assert ok.json()["supported"] is True
    old = client.get(
        "/client/compatibility", params={"profile": "cashier", "version": "0.9.0"}
    )
    assert old.json()["supported"] is False
    unknown = client.get(
        "/client/compatibility", params={"profile": "unknown", "version": "1.0.0"}
    )
    assert unknown.json()["supported"] is False


def test_legacy_universal_client_still_covers_all_roles():
    from his_client.ui.main_window import _legacy_tabs

    for role in ROLES:
        assert _legacy_tabs(role) or role in {"anesthesia", "surgery_nurse"}


def test_main_window_shows_only_profile_tabs():
    from PySide6.QtWidgets import QApplication

    from his_client.api import ApiClient
    from his_client.profiles import CLIENT_PROFILES
    from his_client.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    api = ApiClient("http://127.0.0.1:1")
    cases = {
        "cashier": ("cashier", ["收费员工作站"]),
        "doctor": ("doctor", ["门诊工作站", "患者 360", "中药处方"]),
        "nurse": ("nurse", ["护士工作站"]),
    }
    for key, (role, expected) in cases.items():
        window = MainWindow(api, {"username": role, "role": role, "display_name": role},
                            profile=CLIENT_PROFILES[key])
        titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert titles == expected, (key, titles)
        window.close()
        window.deleteLater()
    app.processEvents()


def test_wrong_role_is_rejected_by_profile_client():
    from PySide6.QtWidgets import QApplication

    from his_client.api import ApiClient
    from his_client.profiles import CLIENT_PROFILES
    from his_client.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        ApiClient("http://127.0.0.1:1"),
        {"username": "doctor", "role": "doctor", "display_name": "医生"},
        profile=CLIENT_PROFILES["cashier"],
    )
    assert window.tabs.count() == 1
    assert "不能使用" in window.tabs.tabText(0) or "不能使用" in window.tabs.widget(0).findChild(type(window.tabs.widget(0))).text()
    window.close()
    window.deleteLater()
    app.processEvents()


def test_admin_client_releases_page(client, auth):
    login = client.post(
        "/admin/login", data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert login.status_code == 302
    response = client.get("/admin/client-releases")
    assert response.status_code == 200
    assert "客户端版本与下载" in response.text
    assert "cashier" in response.text and "管理端客户端" in response.text
