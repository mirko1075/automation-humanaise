#!/usr/bin/env python3
"""
scripts/bump_version.py

Small utility to bump the project `VERSION` file and prepend a changelog stub
for the new version in `CHANGELOG.md`.

Usage:
  # bump patch
  ./scripts/bump_version.py patch --commit

  # bump minor
  ./scripts/bump_version.py minor

  # set exact version
  ./scripts/bump_version.py set 1.4.0 --commit

The script supports optional `--commit` to automatically git add/commit the
changed files with a sensible message. It does not push.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import re
import sys
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
CHANGELOG = ROOT / "CHANGELOG.md"

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def read_version() -> str:
    if not VERSION_FILE.exists():
        return "0.0.0"
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def write_version(v: str) -> None:
    VERSION_FILE.write_text(v + "\n", encoding="utf-8")


def bump_version(current: str, part: str) -> str:
    m = SEMVER_RE.match(current)
    if not m:
        raise SystemExit(f"Current version '{current}' is not semver")
    major, minor, patch = map(int, m.groups())
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise SystemExit("Invalid part. Use major|minor|patch")
    return f"{major}.{minor}.{patch}"


def prepend_changelog_stub(new_version: str, message: str | None = None) -> None:
    today = date.today().isoformat()
    header = f"## v{new_version} — <short title> ({today})\n\n"
    body = (
        "### Added\n- \n\n"
        "### Changed\n- \n\n"
        "### Fixed\n- \n\n"
    )
    stub = header + body

    if not CHANGELOG.exists():
        CHANGELOG.write_text(stub, encoding="utf-8")
        return

    original = CHANGELOG.read_text(encoding="utf-8")
    # If the version already exists at the top, don't duplicate
    if original.lstrip().startswith(f"## v{new_version}"):
        print("Changelog already contains this version at the top; skipping insertion.")
        return

    CHANGELOG.write_text(stub + original, encoding="utf-8")


def git_commit(files: list[Path], message: str) -> None:
    try:
        subprocess.run(["git", "add", *[str(p) for p in files]], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        print("Committed changes locally.")
    except subprocess.CalledProcessError as e:
        print("Git commit failed:", e)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump project version and add changelog stub")
    parser.add_argument("action", choices=["major", "minor", "patch", "set"], help="bump part or set exact version")
    parser.add_argument("value", nargs="?", help="version to set when using 'set'")
    parser.add_argument("--commit", action="store_true", help="git commit the changed files")
    args = parser.parse_args(argv)

    cur = read_version()
    if args.action == "set":
        if not args.value:
            print("Please provide a version to set, e.g. 1.4.0")
            return 2
        new = args.value
        if not SEMVER_RE.match(new):
            print("Version must be semver x.y.z")
            return 2
    else:
        new = bump_version(cur, args.action)

    write_version(new)
    prepend_changelog_stub(new)
    print(f"Bumped version {cur} -> {new}")

    if args.commit:
        git_commit([VERSION_FILE, CHANGELOG], f"chore(release): bump version to {new}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
