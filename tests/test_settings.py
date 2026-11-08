from pathlib import Path

from app import settings
from app.database import SQLALCHEMY_DATABASE_URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_base_dir_is_absolute_project_root():
    assert settings.BASE_DIR.is_absolute()
    assert settings.BASE_DIR == PROJECT_ROOT


def test_database_url_is_absolute_sqlite_path():
    url = settings.DATABASE_URL
    assert url.startswith("sqlite:///")
    path = Path(url.removeprefix("sqlite:///"))
    assert path.is_absolute()
    assert path.parent == PROJECT_ROOT


def test_engine_uses_settings_url():
    assert SQLALCHEMY_DATABASE_URL == settings.DATABASE_URL


def test_backup_and_client_paths_under_base_dir():
    assert settings.BACKUP_DIR.parent == PROJECT_ROOT
    assert settings.CLIENT_ZIP_PATH.parent == PROJECT_ROOT / "dist"


def test_server_config_defaults_from_ini():
    assert settings.HOST in ("0.0.0.0", "127.0.0.1")
    assert isinstance(settings.PORT, int)
    assert settings.SECRET_KEY
