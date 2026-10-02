#!/usr/bin/env python3
"""Resolve the bounded KAORI Developer Check plan for a source diff.

This module is the single path-routing authority for both GitHub Developer Check
and the Local-First Dev Container feedback loop. It selects existing validators
and pytest boundaries; it does not replace those validators.
'''

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE_TEST_DOMAINS = {
    'access': 'access',
    'users': 'access',
    'integrations': 'integrations',
    'kubernetes': 'kubernetes',
    'object_storage': 'storage',
    'storage': 'storage',
    'platform_operations': 'platform_operations',
    'reports': 'reports',
    'settings': 'settings',
    'intelligence': 'intelligence',
    'vault': 'vault',
    'welcome': 'welcome',
}

AUTHORITY_EXACT_PATHS = {
    '.vscode/tasks.json',
    'docs/DEVELOPMENT.md',
    'docs/TESTING.md',
    'docs/engineering/KAORI_DELIVERY_WORKFLOW.md',
    'docs/architecture/code-health-debt-baseline.json',
    'pyproject.toml',
    'pyrightconfig.json',
    'pytest.ini',
    'scripts/ci_admission.py',
    'scripts/ci_admission_policy.py',
    'scripts/quality_gate.sh',
    'scripts/resolve_developer_check_plan.py',
    'scripts/verify_analytics_pdf_publication.py',
    'scripts/verify_code_health.py',
    'scripts/verify_code_health_baseline_integrity.py',
    'scripts/verify_pre_release_type_safety.py',
}

AUTHORITY_PREFIXES = (
    '.github/',
    'requirements/',
    'tests/contracts/release/',
)


@dataclass(frozen=True)
class ValidationPlan:
    python: bool
    templates: bool
    frontend: bool
    migrations: bool
    contracts: bool
    reports: bool
    wide: bool
    capabilities: tuple[str, ...]
    test_paths: tuple[str, ...]

    @property
    def summary(self) -> str:
        capabilities = ','.join(self.capabilities) or 'none'
        tests = ' '.join(self.test_paths) or 'none'
        return (
            f'python={_bool(self.python)} templates={_bool(self.templates)} '
            f'frontend={_bool(self.frontend)} migrations={_bool(self.migrations)} '
            f'contracts={_bool(self.contracts)} reports={_bool(self.reports)} '
            f'wide={_bool(self.wide)} capabilities={capabilities} tests={tests}'
        )

    def github_outputs(self) -> dict[str, str]:
        return {
            'python': _bool(self.python),
            'templates': _bool(self.templates),
            'frontend': _bool(self.frontend),
            'migrations': _bool(self.migrations),
            'contracts': _bool(self.contracts),
            'reports': _bool(self.reports),
            'wide': _bool(self.wide),
            'capabilities': ','.join(self.capabilities),
            'test_paths': ' '.join(self.test_paths),
            'summary': self.summary,
        }


def _bool(value: bool) -> str:
    return 'true' if value else 'false'


def _is_authority_path(path: str) -> bool:
    if path in AUTHORITY_EXACT_PATHS:
        return True
    if path.startswith(AUTHORITY_PREFIXES):
        return True
    name = Path(path).name
    return name.startswith('Dockerfile') or name.startswith('docker-compose') or (
        name.startswith('compose') and name.endswith(('.yml', '.yaml'))
    )


def _existing(root: Path, relative: str) -> bool:
    return (root / relative).exists()


def _nearest_test_boundary(root: Path, test_domain: str, source_tail: tuple[str, ...]) -> str | None:
    domain_root = f'tests/{test_domain}'
    if not _existing(root, domain_root):
        return None

    directory_tail = source_tail[:-1] if source_tail and '.' in source_tail[-1] else source_tail
    for depth in range(len(directory_tail), 0, -1):
        candidate = '/'.join((domain_root, *directory_tail[:depth]))
        if _existing(root, candidate):
            return candidate
    return domain_root


def _test_boundary_for_source(root: Path, path: str) -> tuple[str | None, str | None]:
    parts = Path(path).parts
    if len(parts) < 2 or parts[0] != 'app':
        return None, None

    source_domain = parts[1]
    test_domain = SOURCE_TEST_DOMAINS.get(source_domain)
    if test_domain is None:
        return source_domain, None

    source_tail = tuple(parts[2:])
    boundary = _nearest_test_boundary(root, test_domain, source_tail)
    capability = test_domain
    if boundary and boundary != f'tests/{test_domain}':
        capability = boundary.removeprefix('tests/')
    return capability, boundary


def _test_boundary_for_test_path(root: Path, path: str) -> tuple[str | None, str | None]:
    parts = Path(path).parts
    if len(parts) < 2 or parts[0] != 'tests':
        return None, None

    if parts[1] == 'contracts':
        if len(parts) >= 3:
            family = parts[2]
            return f'contracts/{family}', f'tests/contracts/{family}'
        return 'contracts', 'tests/contracts/release'

    if parts[1] == 'migrations':
        return 'migrations', 'tests/migrations'

    domain = parts[1]
    parent = Path(path).parent
    while str(parent).startswith('tests/') and parent != Path('tests'):
        relative = parent.as_posix()
        if _existing(root, relative):
            return relative.removeprefix('tests/'), relative
        parent = parent.parent

    fallback = f'tests/{domain}'
    if _existing(root, fallback):
        return domain, fallback
    return domain, None


def _normalize_test_paths(paths: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for candidate in sorted(set(paths)):
        if any(candidate == parent or candidate.startswith(parent + '/') for parent in normalized):
            continue
        normalized = [parent for parent in normalized if not parent.startswith(candidate + '/')]
        normalized.append(candidate)
    return tuple(normalized)


def resolve_plan(changed_paths: Iterable[str], *, root: Path = ROOT) -> ValidationPlan:
    python = False
    templates = False
    frontend = False
    migrations = False
    contracts = False
    reports = False
    wide = False
    capabilities: set[str] = set()
    selected_tests: set[str] = set()

    paths = tuple(sorted({path.strip() for path in changed_paths if path.strip()}))

    for path in paths:
        if _is_authority_path(path):
            wide = True
            python = True
            templates = True
            frontend = True
            migrations = True
            contracts = True
            capabilities.add('delivery/validation-authority')
            selected_tests.update(('tests/contracts/release', 'tests/migrations'))

        if path.endswith('.py'):
            python = True

        if path.startswith('app/templates/') or '/templates/' in path:
            templates = True

        if path.startswith(('app/static/', 'frontend/')) or path in {'package.json', 'package-lock.json'}:
            frontend = True

        if (
            path.startswith('migrations/')
            or path.startswith('app/models/')
            or path.endswith('/models.py')
            or '/models/' in path
        ):
            migrations = True
            contracts = True
            capabilities.add('persistence/migrations')
            if _existing(root, 'tests/migrations'):
                selected_tests.add('tests/migrations')

        if path.startswith(('app/reports/', 'tests/reports/', 'tests/contracts/reports/')) or (
            path == 'scripts/verify_analytics_pdf_publication.py'
        ):
            reports = True
            contracts = True

        if path.startswith('app/'):
            contracts = True
            capability, boundary = _test_boundary_for_source(root, path)
            if capability:
                capabilities.add(capability)
            if boundary:
                selected_tests.add(boundary)

            if path.startswith('app/vault/') and not boundary and _existing(root, 'tests/access'):
                capabilities.add('access')
                selected_tests.add('tests/access')

        if path.startswith('tests/'):
            capability, boundary = _test_boundary_for_test_path(root, path)
            if capability:
                capabilities.add(capability)
            if boundary:
                selected_tests.add(boundary)

            if path.startswith('tests/ui/'):
                frontend = True
            if path.startswith('tests/contracts/'):
                contracts = True
            if path.startswith('tests/migrations/'):
                migrations = True
                contracts = True

    if contracts and not selected_tests:
        selected_tests.add('tests/contracts/release')
        capabilities.add('contracts/release')

    test_paths = _normalize_test_paths(path for path in selected_tests if _existing(root, path))

    return ValidationPlan(
        python=python,
        templates=templates,
        frontend=frontend,
        migrations=migrations,
        contracts=contracts,
        reports=reports,
        wide=wide,
        capabilities=tuple(sorted(capabilities)),
        test_paths=test_paths,
    )


def changed_paths_from_git(base_ref: str, head_ref: str, *, root: Path = ROOT) -> tuple[str, ...]:
    completed = subprocess.run(
        ['git', 'diff', '--name-only', base_ref, head_ref, '--'],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line for line in completed.stdout.splitlines() if line)


def _write_github_output(path: Path, plan: ValidationPlan) -> None:
    with path.open('a', encoding='utf-8') as handle:
        for key, value in plan.github_outputs().items():
            handle.write(f'{key}={value}\n')


def _print_human(plan: ValidationPlan, changed_count: int) -> None:
    print('📦 KAORI Developer Validation Plan')
    print(f'Changed files: {changed_count}')
    print(f'Capabilities: {", ".join(plan.capabilities) or "none"}')
    print(
        'Checks: '
        f'python={_bool(plan.python)} templates={_bool(plan.templates)} '
        f'frontend={_bool(plan.frontend)} migrations={_bool(plan.migrations)} '
        f'contracts={_bool(plan.contracts)} reports={_bool(plan.reports)} wide={_bool(plan.wide)}'
    )
    print('Focused tests:')
    if plan.test_paths:
        for path in plan.test_paths:
            print(f'  - {path}')
    else:
        print('  - none')
    print(f'➡️ {plan.summary}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-ref', default='origin/kaori/staging')
    parser.add_argument('--head-ref', default='HEAD')
    parser.add_argument('--paths-file', type=Path)
    parser.add_argument('--github-output', type=Path)
    parser.add_argument('--json', action='store_true')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.paths_file:
        changed_paths = tuple(
            line.strip() for line in args.paths_file.read_text(encoding='utf-8').splitlines() if line.strip()
        )
    else:
        changed_paths = changed_paths_from_git(args.base_ref, args.head_ref)

    plan = resolve_plan(changed_paths)
    if args.github_output:
        _write_github_output(args.github_output, plan)

    if args.json:
        print(json.dumps(plan.github_outputs(), indent=2, sort_keys=True))
    else:
        _print_human(plan, len(changed_paths))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
