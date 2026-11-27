"""构建单个岗位客户端。

用法：
    python scripts/build_client.py --profile cashier
    python scripts/build_client.py --profile doctor --no-zip
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from his_client.profiles import CLIENT_PROFILES  # noqa: E402


def build(profile_key: str, *, zip_it: bool = True, clean: bool = True) -> Path:
    profile = CLIENT_PROFILES.get(profile_key)
    if not profile:
        raise SystemExit(f"未知客户端岗位：{profile_key}")
    name = f"his-client-{profile.key}"
    build_dir = ROOT / "build" / name
    dist_dir = ROOT / "dist" / name
    if clean:
        shutil.rmtree(build_dir, ignore_errors=True)
        shutil.rmtree(dist_dir, ignore_errors=True)
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm",
        "--windowed", "--name", name, "--onedir", "--paths", str(ROOT),
        str(ROOT / "his_client" / "__main__.py"),
    ]
    if clean:
        cmd.insert(3, "--clean")
    subprocess.run(cmd, cwd=ROOT, check=True)
    target = ROOT / "dist" / name
    config = target / "config.ini"
    if not config.exists():
        shutil.copy2(ROOT / "his_client" / "config.ini", config)
    (target / "client_profile.json").write_text(
        json.dumps({
            "profile": profile.key,
            "title": profile.title,
            "version": profile.version,
            "roles": list(profile.roles),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if zip_it:
        archive = ROOT / "dist" / f"{name}-{profile.version}.zip"
        archive.unlink(missing_ok=True)
        shutil.make_archive(str(archive.with_suffix("")), "zip", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(CLIENT_PROFILES))
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    target = build(args.profile, zip_it=not args.no_zip, clean=not args.no_clean)
    print(f"BUILT {args.profile}: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
