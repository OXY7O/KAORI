#!/usr/bin/env python3
"""Resolve the canonical KAORI Developer Check validation plan.

This module is planning authority only. It selects existing KAORI validation
commands and focused pytest paths from the changed-path blast radius so the
same decision can be consumed by Dev Container and GitHub Actions.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ValidationPlan:
    python: bool = False
    templates: bool = False
    frontend: bool = False
    migrations: bool = False
    contracts: bool = False
    reports: bool = False
    wide: bool = False
    test_paths: set[str] = field(default_factory=set)
    capabilities: set[str] = field(default_factory=set)

    def add_test_path(self, path: str) -> None:
        if (ROOT / path).exists():
            self.test_paths.add(path)

    def add_test_glob(self, pattern: str) -> None:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file():
                self.test_paths.add(path.relative_to(ROOT).as_posix())

    def normalized_test_paths(self) -> list[str]:
        paths = set(self.test_paths)
        if 'tests/contracts' in paths:
            paths = {path for path in paths if path == 'tests/contracts' or not path.startswith('tests/contracts/')}
        return sorted(paths)

    def summary(self) -> str:
        tests = ' '.join(self.normalized_test_paths()) or 'none'
        capabilities = ','.join(sorted(self.capabilities)) or 'shared'
        return (
            f'python={str(self.python).lower()} '
            f'templates={str(self.templates).lower()} '
            f'frontend={str(self.frontend).lower()} '
            f'migrations={str(self.migrations).lower()} '
            f'contracts={str(self.contracts).lower()} '
            f'reports={str(self.reports).lower()} '
            f'wide={str(self.wide).lower()} '
            f'capabilities={capabilities} tests={tests}'
        )


def _is_wide_authority(path: str) -> bool:
    prefixes = ('.github/', 'requirements/')
    exact = {
        'Dockerfile',
        'compose.yml',
        'compose.production.yml',
        'scripts/ci_admission.py',
        'scripts/ci_admission_policy.py',
        'scripts/developer_check_plan.py',
        'scripts/quality_gate.sh',
        'scripts/verify_analytics_pdf_publication.py',
        'scripts/verify_pre_release_type_safety.py',
        'scripts/verify_code_health.py',
        'scripts/verify_code_health_baseline_integrity.py',
        'docs/architecture/code-health-debt-baseline.json',
        'docs/engineering/KAORI_DELIVERY_WORKFLOW.md',
    }
    return (
        path.startswith(prefixes) or path in exact or path.startswith('Dockerfile') or path.startswith('docker-compose')
    )


def _select_contract_family(plan: ValidationPlan, path: str) -> bool:
    families = (
        'access',
        'analytics',
        'architecture',
        'dashboards',
        'definitions',
        'design',
        'integrations',
        'intelligence',
        'kubernetes',
        'platform_operations',
        'release',
        'reports',
        'settings',
        'storage',
        'welcome',
    )
    for family in families:
        prefix = f'tests/contracts/{family}/'
        if path.startswith(prefix):
            plan.contracts = True
            if family == 'release':
                plan.python = True
                plan.templates = True
                plan.frontend = True
                plan.migrations = True
                plan.wide = True
            if family in {'analytics', 'reports'}:
                plan.reports = True
            plan.add_test_path(f'tests/contracts/{family}')
            return True
    return False


def build_plan(changed_paths: list[str]) -> ValidationPlan:
    plan = ValidationPlan()

    for path in changed_paths:
        if not path:
            continue

        if _is_wide_authority(path):
            plan.wide = True
            plan.python = True
            plan.templates = True
            plan.frontend = True
            plan.migrations = True
            plan.contracts = True

        if path.endswith('.py'):
            plan.python = True
        if path.startswith('app/templates/') or (path.startswith('app/') and '/templates/' in path):
            plan.templates = True
        if (
            path.startswith('app/static/')
            or path.startswith('frontend/')
            or path in {'package.json', 'package-lock.json'}
        ):
            plan.frontend = True
        if path.startswith('migrations/') or path.endswith('/models.py') or '/models/' in path:
            plan.migrations = True
            plan.contracts = True

        if path.startswith(('app/welcome/', 'tests/welcome/')):
            plan.capabilities.add('welcome')
            plan.add_test_path('tests/welcome')
        elif path.startswith(('app/access/', 'app/users/', 'tests/access/')):
            plan.capabilities.add('access')
            plan.add_test_path('tests/access')
        elif path.startswith(('app/integrations/', 'tests/integrations/')):
            plan.capabilities.add('integrations')
            plan.add_test_path('tests/integrations')
        elif path.startswith(('app/kubernetes/tenant/', 'tests/kubernetes/tenant/')):
            plan.capabilities.add('kubernetes/tenant')
            plan.add_test_path('tests/kubernetes/tenant')
            plan.add_test_glob('tests/contracts/kubernetes/test_tenant_*.py')
        elif path.startswith(('app/kubernetes/', 'tests/kubernetes/')):
            plan.capabilities.add('kubernetes')
            plan.add_test_path('tests/kubernetes')
        elif path.startswith(
            (
                'app/storage/',
                'app/object_storage/',
                'tests/storage/',
                'tests/object_storage/',
            )
        ):
            plan.capabilities.add('storage')
            plan.add_test_path('tests/storage')
            plan.add_test_path('tests/object_storage')
        elif path.startswith(('app/platform_operations/', 'tests/platform_operations/')):
            plan.capabilities.add('platform_operations')
            plan.contracts = True
            plan.add_test_path('tests/platform_operations')
        elif (
            path.startswith(('app/reports/', 'tests/reports/')) or path == 'scripts/verify_analytics_pdf_publication.py'
        ):
            plan.capabilities.add('reports')
            plan.reports = True
            plan.contracts = True
            plan.add_test_path('tests/reports')
        elif path.startswith(('app/settings/', 'tests/settings/')):
            plan.capabilities.add('settings')
            plan.add_test_path('tests/settings')
        elif path.startswith(('app/intelligence/', 'tests/intelligence/')):
            plan.capabilities.add('intelligence')
            plan.add_test_path('tests/intelligence')
        elif path.startswith(('app/vault/', 'tests/vault/')):
            plan.capabilities.add('vault')
            plan.add_test_path('tests/vault')
            plan.add_test_path('tests/access')
        elif path.startswith('tests/ui/'):
            plan.capabilities.add('ui')
            plan.frontend = True
            plan.add_test_path('tests/ui')

        if _select_contract_family(plan, path):
            continue

        if path.startswith('app/'):
            plan.contracts = True
        elif path.startswith('tests/contracts/'):
            plan.contracts = True

    if plan.wide:
        plan.add_test_path('tests/contracts')
        plan.add_test_path('tests/migrations')

    return plan


def git_changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ['git', 'diff', '--name-only', base, head],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def write_github_output(path: Path, plan: ValidationPlan) -> None:
    values = {
        'python': plan.python,
        'templates': plan.templates,
        'frontend': plan.frontend,
        'migrations': plan.migrations,
        'contracts': plan.contracts,
        'reports': plan.reports,
        'wide': plan.wide,
    }
    test_paths = ' '.join(plan.normalized_test_paths())
    with path.open('a', encoding='utf-8') as handle:
        for key, value in values.items():
            handle.write(f'{key}={str(value).lower()}\n')
        handle.write(f'test_paths={test_paths}\n')
        handle.write(f'summary={plan.summary()}\n')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='kaori/staging')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument(
        '--changed-file',
        type=Path,
        help='Read newline-delimited changed paths instead of running git diff.',
    )
    parser.add_argument(
        '--github-output',
        type=Path,
        help='Append canonical route outputs to this GitHub Actions output file.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.changed_file:
        changed_paths = [
            line.strip() for line in args.changed_file.read_text(encoding='utf-8').splitlines() if line.strip()
        ]
    else:
        changed_paths = git_changed_paths(args.base, args.head)

    plan = build_plan(changed_paths)

    print('KAORI Developer Check Plan')
    print(f'Changed paths: {len(changed_paths)}')
    print(f'Plan: {plan.summary()}')

    if args.github_output:
        write_github_output(args.github_output, plan)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
