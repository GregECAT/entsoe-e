#!/usr/bin/env python3
"""Bump integration version in manifest.json.

Usage:
    python3 scripts/bump_version.py 1.2.0
    python3 scripts/bump_version.py patch   # 1.0.0 → 1.0.1
    python3 scripts/bump_version.py minor   # 1.0.0 → 1.1.0
    python3 scripts/bump_version.py major   # 1.0.0 → 2.0.0
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MANIFEST = Path(__file__).parent.parent / "custom_components" / "entsoe_prices" / "manifest.json"


def parse_version(v: str) -> tuple[int, int, int]:
    """Parse semver string."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", v)
    if not match:
        raise ValueError(f"Invalid version: {v}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump(current: str, part: str) -> str:
    """Bump version by part name."""
    major, minor, patch = parse_version(current)
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "major":
        return f"{major + 1}.0.0"
    raise ValueError(f"Unknown part: {part}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: bump_version.py <version|patch|minor|major>")
        sys.exit(1)

    target = sys.argv[1]
    manifest = json.loads(MANIFEST.read_text())
    current = manifest["version"]

    if target in ("patch", "minor", "major"):
        new_version = bump(current, target)
    else:
        # Validate explicit version
        parse_version(target)
        new_version = target

    manifest["version"] = new_version
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    print(f"✅ Version bumped: {current} → {new_version}")
    print(f"   manifest.json updated")
    print()
    print(f"Next steps:")
    print(f"   git add custom_components/entsoe_prices/manifest.json")
    print(f"   git commit -m 'Bump version to {new_version}'")
    print(f"   git tag v{new_version}")
    print(f"   git push origin main --tags")


if __name__ == "__main__":
    main()
