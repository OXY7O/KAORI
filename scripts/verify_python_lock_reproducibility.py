#!/usr/bin/env python3
"""Fail-closed, non-mutating reproduction of the canonical KAORI pip-tools locks.

Run inside the Python 3.12 CI toolchain. The documented pip-compile commands
execute only against temporary copies of requirements/, never the checkout.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILES = ("base.txt", "dev.txt")
COMMANDS = (
    ("pip-compile", "requirements/base.in", "--output-file", "requirements/base.txt"),
    ("pip-compile", "requirements/dev.in", "--output-file", "requirements/dev.txt"),
)
TIMEOUT_SECONDS = 360
MAX_DIFF_LINES = 40


def normalized_requirements(source: str) -> dict[str, str]:
    """Compare requirement semantics, not pip-tools annotation/header noise."""
    records: dict[str, str] = {}
    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.partition("#")[0].strip()
        if not line:
            continue
        if line.startswith(("-r ", "-r=", "--requirement ", "--requirement=")):
            continue
        if line.startswith(("-c ", "-c=", "--constraint ", "--constraint=")):
            continue
        if line.startswith("--"):
            # pip-compile generated index options are not installed packages.
            continue
        if line.startswith("-"):
            raise ValueError(f"unsupported lock option on line {number}: {line}")
        try:
            parsed = Requirement(line)
        except Exception as error:
            raise ValueError(f"unparseable lock entry on line {number}: {line}") from error
        key = canonicalize_name(parsed.name)
        extras = ",".join(sorted(canonicalize_name(x) for x in parsed.extras))
        specifier = str(parsed.specifier)
        marker = str(parsed.marker) if parsed.marker is not None else ""
        url = parsed.url or ""
        identity = f"extras={extras};spec={specifier};marker={marker};url={url}"
        if key in records:
            raise ValueError(f"duplicate lock package {key} on line {number}")
        records[key] = identity
    return records


def lock_differences(committed: str, regenerated: str) -> list[str]:
    expected = normalized_requirements(committed)
    actual = normalized_requirements(regenerated)
    issues: list[str] = []
    for name in sorted(set(expected) | set(actual)):
        old, new = expected.get(name), actual.get(name)
        if old == new:
            continue
        if old is None:
            issues.append(f"ADDED by resolver: {name} {new}")
        elif new is None:
            issues.append(f"MISSING from resolver: {name} {old}")
        else:
            issues.append(f"DRIFT: {name} committed={old} generated={new}")
    return issues


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> int:
    if sys.version_info[:2] != (3, 12):
        print("BLOCK: Python 3.12 is mandatory for KAORI lock reproduction.", file=sys.stderr)
        return 2
    if shutil.which("pip-compile") is None:
        print("BLOCK: pip-compile is absent from the canonical CI toolchain.", file=sys.stderr)
        return 2
    try:
        tools_version = version("pip-tools")
    except PackageNotFoundError:
        print("BLOCK: pip-tools is not installed.", file=sys.stderr)
        return 2
    print(f"Lock reproduction toolchain: Python {sys.version.split()[0]} / pip-tools {tools_version}", flush=True)

    checkout = ROOT / "requirements"
    originals = {name: fingerprint(checkout / name) for name in LOCK_FILES}
    failure = False

    with tempfile.TemporaryDirectory(prefix="kaori-pip-compile-") as temporary:
        workspace = Path(temporary)
        shutil.copytree(checkout, workspace / "requirements")
        for command, lock_name in zip(COMMANDS, LOCK_FILES):
            print(f"REPRODUCE: {' '.join(command)} (temporary workspace)", flush=True)
            try:
                result = subprocess.run(
                    command,
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SECONDS,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                print(f"BLOCK: {lock_name} resolver exceeded {TIMEOUT_SECONDS}s.", file=sys.stderr)
                failure = True
                continue

            if result.returncode:
                print(f"BLOCK: {lock_name} pip-compile failed (exit {result.returncode}).", file=sys.stderr)
                lines = (result.stdout + "\n" + result.stderr).splitlines()
                for line in lines[-35:]:
                    print(line, file=sys.stderr)
                failure = True
                continue
            try:
                drift = lock_differences(
                    (checkout / lock_name).read_text(encoding="utf-8"),
                    (workspace / "requirements" / lock_name).read_text(encoding="utf-8"),
                )
            except (OSError, ValueError) as error:
                print(f"BLOCK: {lock_name} cannot be compared: {error}", file=sys.stderr)
                failure = True
                continue

            if drift:
                print(f"BLOCK: {lock_name} has {len(drift)} semantic lock differences.", file=sys.stderr)
                for line in drift[:MAX_DIFF_LINES]:
                    print(f"  {line}", file=sys.stderr)
                if len(drift) > MAX_DIFF_LINES:
                    print(f"  ... {len(drift) - MAX_DIFF_LINES} more entries", file=sys.stderr)
                failure = True
            else:
                print(f"PASS: {lock_name} resolver output matches committed requirement semantics.", flush=True)

    if any(fingerprint(checkout / name) != original for name, original in originals.items()):
        print("BLOCK: checked-in requirement locks changed during reproduction.", file=sys.stderr)
        return 2
    if failure:
        print("FAIL: preserve Draft; regenerate/reconcile locks through a separate issue-owned review.", file=sys.stderr)
        return 1
    print("PASS: both base and dev semantic locks reproduced without modifying source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
