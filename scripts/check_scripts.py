"""Check Windows batch and Linux shell scripts for encoding/line-ending issues.

Run:
    python scripts/check_scripts.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SKIP_PARTS = {".git", ".venv", "build", "dist", "__pycache__"}


def files(suffixes):
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def main() -> int:
    errors = []
    checked = 0
    for path in files({".bat", ".cmd"}):
        checked += 1
        data = path.read_bytes()
        rel = path.relative_to(ROOT)
        if data.startswith(b"\xef\xbb\xbf"):
            errors.append(f"{rel}: has UTF-8 BOM")
        if b"\n" in data.replace(b"\r\n", b""):
            errors.append(f"{rel}: contains bare LF; batch files must be CRLF")
        if any(byte > 127 for byte in data):
            errors.append(f"{rel}: contains non-ASCII bytes")
        if b"chcp " in data.lower():
            errors.append(f"{rel}: contains chcp; keep batch files ASCII/CRLF")
        first = data.split(b"\r\n", 1)[0].strip().lower()
        if first not in (b"@echo off", b"@echo off "):
            errors.append(f"{rel}: first line should be @echo off")

    for path in files({".sh"}):
        checked += 1
        data = path.read_bytes()
        rel = path.relative_to(ROOT)
        if b"\r\n" in data or b"\r" in data:
            errors.append(f"{rel}: contains CR; shell scripts must be LF")
        if not data.startswith(b"#!"):
            errors.append(f"{rel}: missing shebang")

    print(f"checked {checked} scripts")
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    print("all scripts OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
