#!/usr/bin/env python3
"""Run KAORI release checks with concise PASS output and detailed failures."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from release_surface_registry import SURFACES

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

SHORT_LABELS = {
    'Welcome': 'Welcome',
    'Kubernetes Dashboard': 'Dashboard',
    'Kubernetes Inventory': 'Inventory',
    'Object Storage Inventory': 'Object Storage',
    'Kubernetes Operations': 'Kubernetes Ops',
    'Kubernetes Governance': 'Governance',
    'Analytics': 'Analytics',
    'Intelligence': 'Intelligence',
    'Reports': 'Reports',
    'Integrations': 'Integrations',
    'Platform Operations': 'Platform Ops',
    'Access': 'Access',
    'Settings': 'Settings',
    'Authentication': 'Authentication',
    'Notification Center': 'Notifications',
    'Runtime Health': 'Runtime Health',
}

QUICK_DEFERRED_VERIFIERS = {'scripts/verify_report_runtime_imports.py'}


def _purge_generated_python_cache() -> None:
    for cache_name in ('__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache'):
        for path in ROOT.rglob(cache_name):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
    for pattern in ('*.pyc', '*.pyo'):
        for path in ROOT.rglob(pattern):
            path.unlink(missing_ok=True)


SHARED_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('Domain Namespaces', (PYTHON, 'scripts/verify_domain_namespace_architecture.py')),
    ('Sidebar', (PYTHON, 'scripts/verify_sidebar_navigation_standard.py')),
    ('App Shell', (PYTHON, 'scripts/verify_application_shell_standard.py')),
    ('Dark Mode', (PYTHON, 'scripts/verify_dark_mode_standard.py')),
    ('UI Style', (PYTHON, 'scripts/verify_ui_style.py')),
    ('UI Reuse', (PYTHON, 'scripts/verify_ui_reuse.py')),
    ('JavaScript', (PYTHON, 'scripts/verify_javascript_syntax.py')),
    ('Release Governance', (PYTHON, 'scripts/verify_release_governance.py')),
    ('Environment Contract', (PYTHON, 'scripts/verify_environment_contract.py')),
    ('Notification Channels', (PYTHON, 'scripts/verify_notification_channels.py')),
    ('Obsolete Files', (PYTHON, 'scripts/verify_obsolete_files.py')),
)


def _is_success_chatter(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith('PASS — KAORI '):
        return True
    if stripped.startswith('[KAORI hygiene] tracked source is clean'):
        return True
    if stripped in {'All checks passed!', 'Checking formatting...'}:
        return True
    if stripped.endswith(' files already formatted') or stripped == '0 files would be updated.':
        return True
    if stripped == '0 errors, 0 warnings, 0 informations':
        return True
    if stripped.startswith('Checking ') and ' files' in stripped:
        return True
    if not stripped.startswith('KAORI '):
        return False
    success_markers = (
        ' passed',
        ': PASS',
        ' is valid',
        ' are valid',
        ' is bounded',
        ' is acyclic',
        ' is closed',
        ' coverage is present',
        ' syntax passed',
    )
    return any(marker in stripped for marker in success_markers)


def _failure_output(stdout: str, stderr: str) -> str:
    lines: list[str] = []
    for part in (stdout, stderr):
        if not part.strip():
            continue
        lines.extend(line.rstrip() for line in part.splitlines())
    return '\n'.join(line for line in lines if not _is_success_chatter(line)).strip()


def _run(label: str, command: tuple[str, ...], *, env: dict[str, str] | None = None) -> bool:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        print(f'PASS — KAORI {label}')
        return True

    print(f'FAIL — KAORI {label}')
    output = _failure_output(result.stdout, result.stderr)
    if output:
        print(output)
    else:
        print(f'- command exited with status {result.returncode}: {" ".join(command)}')
    return False


def _run_group(label: str, commands: tuple[tuple[str, ...], ...]) -> bool:
    for command in commands:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            print(f'FAIL — KAORI {label}')
            output = _failure_output(result.stdout, result.stderr)
            if output:
                print(output)
            else:
                print(f'- command exited with status {result.returncode}: {" ".join(command)}')
            return False
    print(f'PASS — KAORI {label}')
    return True


def _run_surface_checks() -> bool:
    if not _run('Release Coverage', (PYTHON, 'scripts/verify_release_surface_coverage.py')):
        return False

    for surface in SURFACES:
        commands = tuple(
            (PYTHON, verifier) for verifier in surface.verifiers if verifier not in QUICK_DEFERRED_VERIFIERS
        )
        if not commands:
            continue
        if not _run_group(SHORT_LABELS[surface.title], commands):
            return False

    for label, command in SHARED_CHECKS:
        if not _run(label, command):
            return False
    return True


def _run_full_gate() -> bool:
    phases = (
        ('Static Quality', ('bash', 'scripts/quality_gate.sh', '--static')),
        ('Test Suite', ('bash', 'scripts/quality_gate.sh', '--tests')),
        ('Frontend', ('bash', 'scripts/quality_gate.sh', '--frontend')),
    )
    return all(_run(label, command) for label, command in phases)


def _run_runtime_checks() -> bool:
    checks = (
        (
            'Endpoint Registry',
            (PYTHON, '-m', 'pytest', '-q', 'tests/integration/release/test_release_endpoint_registry.py'),
        ),
        ('Reports Worker', (PYTHON, 'scripts/verify_reports_worker_runtime.py')),
    )
    return all(_run(label, command) for label, command in checks)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            'Run concise KAORI general release checks. Successful steps stay short; '
            'failed steps print full diagnostics.'
        )
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Also run static quality, the full test suite, and frontend gates.',
    )
    parser.add_argument(
        '--runtime',
        action='store_true',
        help='Also require registered endpoints and live Reports worker readiness.',
    )
    args = parser.parse_args()

    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    _purge_generated_python_cache()

    if not _run_surface_checks():
        return 1
    if args.all and not _run_full_gate():
        return 1
    if args.runtime and not _run_runtime_checks():
        return 1

    print('PASS — KAORI Final Release')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
