"""构建全部岗位独立客户端，并生成版本清单。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from his_client.profiles import CLIENT_PROFILES  # noqa: E402
from scripts.build_client import build  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", default="", help="逗号分隔；默认所有非 universal 岗位")
    parser.add_argument("--no-zip", action="store_true")
    args = parser.parse_args()
    keys = [key.strip() for key in args.profiles.split(",") if key.strip()]
    if not keys:
        keys = [key for key in CLIENT_PROFILES if key != "universal"]
    from app.version import APP_VERSION
    manifest = {"server": APP_VERSION, "clients": {}}
    failures = []
    for key in keys:
        try:
            build(key, zip_it=not args.no_zip)
            profile = CLIENT_PROFILES[key]
            manifest["clients"][key] = {
                "title": profile.title,
                "version": profile.version,
                "roles": list(profile.roles),
                "package": f"his-client-{key}-{profile.version}.zip",
            }
        except subprocess.CalledProcessError as exc:  # type: ignore[name-defined]
            failures.append(f"{key}: {exc}")
    (ROOT / "dist" / "clients-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if failures:
        print("FAILED:", failures, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
