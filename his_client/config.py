"""客户端配置：config.ini（服务器地址、超时、打印机）。

查找顺序：显式路径 → 环境变量 HIS_CLIENT_CONFIG → exe 同目录 → 当前目录 → 包内默认。
本地覆盖：config.local.ini（同目录/当前目录/包内，可只写需要覆盖的项，通常不入库）。
"""
import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SERVER = "http://127.0.0.1:8000"


@dataclass
class ClientConfig:
    server_url: str = DEFAULT_SERVER
    timeout: int = 10
    printer: str = ""
    insurance_enabled: bool = False
    remember_login: bool = True
    remember_limit: int = 10
    history_path: str = ""


def _candidate_paths(explicit: str | Path | None) -> list[Path]:
    paths = []
    if explicit:
        paths.append(Path(explicit))
    env = os.environ.get("HIS_CLIENT_CONFIG")
    if env:
        paths.append(Path(env))
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).parent / "config.ini")
    paths.append(Path.cwd() / "config.ini")
    paths.append(Path(__file__).with_name("config.ini"))
    return paths


def _override_paths() -> list[Path]:
    """本地覆盖配置（可只写需要覆盖的项）。"""
    paths = []
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).parent / "config.local.ini")
    paths.append(Path.cwd() / "config.local.ini")
    paths.append(Path(__file__).with_name("config.local.ini"))
    return paths


def _read_values(path: Path) -> dict:
    """只返回文件里实际出现的配置项，避免覆盖成默认值。"""
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    values: dict = {}
    if parser.has_option("server", "url"):
        values["server_url"] = parser.get("server", "url").strip() or DEFAULT_SERVER
    if parser.has_option("client", "timeout"):
        values["timeout"] = parser.getint("client", "timeout")
    if parser.has_option("client", "printer"):
        values["printer"] = parser.get("client", "printer").strip()
    if parser.has_option("features", "insurance"):
        values["insurance_enabled"] = parser.getboolean("features", "insurance")
    if parser.has_option("client", "remember_login"):
        values["remember_login"] = parser.getboolean("client", "remember_login")
    if parser.has_option("client", "remember_limit"):
        values["remember_limit"] = max(1, min(50, parser.getint("client", "remember_limit")))
    return values


def parse_config(path: Path) -> ClientConfig:
    config = ClientConfig()
    for key, value in _read_values(path).items():
        setattr(config, key, value)
    return config


def load_config(path: str | Path | None = None) -> ClientConfig:
    config = ClientConfig()
    found_path: Path | None = None
    for candidate in _candidate_paths(path):
        if candidate.is_file():
            config = parse_config(candidate)
            found_path = candidate
            break
    for candidate in _override_paths():
        if candidate.is_file():
            for key, value in _read_values(candidate).items():
                setattr(config, key, value)
    base_dir = (
        found_path.parent
        if found_path is not None
        else (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd())
    )
    config.history_path = str(base_dir / "login_history.json")
    return config
