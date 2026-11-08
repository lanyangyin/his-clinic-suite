"""客户端配置：config.ini（服务器地址、超时、打印机）。

查找顺序：显式路径 → 环境变量 HIS_CLIENT_CONFIG → exe 同目录 → 当前目录 → 包内默认。
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


def load_config(path: str | Path | None = None) -> ClientConfig:
    for candidate in _candidate_paths(path):
        if candidate.is_file():
            return parse_config(candidate)
    return ClientConfig()


def parse_config(path: Path) -> ClientConfig:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    url = parser.get("server", "url", fallback=DEFAULT_SERVER).strip()
    timeout = parser.getint("client", "timeout", fallback=10)
    printer = parser.get("client", "printer", fallback="").strip()
    return ClientConfig(server_url=url or DEFAULT_SERVER, timeout=timeout, printer=printer)
