#!/usr/bin/env python3
"""Create and push a release tag from the version in version.txt."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version.txt"
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True)


def read_version() -> str:
    try:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing {VERSION_FILE.name}. Create it with a semver like 0.1.0.") from exc

    if not SEMVER_RE.match(version):
        raise SystemExit(f"Invalid semver in {VERSION_FILE.name}: {version!r}")

    return version


def tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "tag", "--list", tag],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return bool(result.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and push a version tag for this repository.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the tag and push command without creating or pushing anything.",
    )
    args = parser.parse_args()

    version = read_version()
    tag = f"v{version}"

    if tag_exists(tag):
        raise SystemExit(f"Tag {tag} already exists locally. Update {VERSION_FILE.name} before releasing.")

    command = ["git", "tag", tag]
    push_command = ["git", "push", "origin", "HEAD", "--follow-tags"]

    print(f"Release version: {version}")
    print(f"Tag to create: {tag}")

    if args.dry_run:
        print("Dry run only; no tag or push was created.")
        print(f"Would run: {' '.join(command)}")
        print(f"Would run: {' '.join(push_command)}")
        return 0

    run_git("tag", tag)
    print(f"Created tag {tag}")
    run_git("push", "origin", "HEAD", "--follow-tags")
    print(f"Pushed tag {tag} to origin")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        if stderr:
            print(stderr, file=sys.stderr)
        raise SystemExit(exc.returncode)
