#!/usr/bin/env python3
"""Lock KAORI's domain-first package and MVC/application-layer architecture."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
BASELINE = ROOT / 'docs/architecture/mvc-debt-baseline.json'

ALLOWED_APP_ROOT_DIRS = {
    'access',
    'analytics',
    'artifact_storage',
    'bootstrap',
    'commands',
    'common',
    'config',
    'dashboards',
    'definitions',
    'extensions',
    'integrations',
    'intelligence',
    'kubernetes',
    'models',
    'platform_operations',
    'reports',
    'security',
    'settings',
    'static',
    'storage',
    'templates',
    'welcome',
}

REQUIRED_PATHS = (
    'app/access/authentication',
    'app/access/users',
    'app/access/identity_providers',
    'app/access/rbac',
    'app/access/roles',
    'app/access/permissions',
    'app/access/activity_audit',
    'app/integrations/observability/metrics_source/application',
    'app/integrations/observability/alert_source/providers/alertmanager/application',
    'app/integrations/storage/object_storage/providers/minio/application',
    'app/integrations/delivery/notification_channels',
    'app/kubernetes/cluster',
    'app/kubernetes/dashboard',
    'app/kubernetes/inventory',
    'app/kubernetes/analytics',
    'app/kubernetes/governance',
    'app/kubernetes/operations',
    'app/storage/object_storage/inventory',
    'app/storage/object_storage/analytics',
    'app/intelligence/alert_intelligence',
    'app/intelligence/automation_control',
    'app/intelligence/knowledge',
    'app/intelligence/resolver',
    'app/platform_operations/jobs',
    'app/platform_operations/notifications',
    'app/platform_operations/data_lifecycle/retention',
    'app/platform_operations/health',
    'app/artifact_storage',
    'app/templates/access/authentication',
    'app/templates/access/users',
    'app/templates/kubernetes/inventory',
    'app/templates/kubernetes/analytics',
    'app/templates/storage/object_storage/inventory',
    'app/templates/storage/object_storage/analytics',
)

FORBIDDEN_ROOTS = {
    'alert_delivery',
    'alert_intelligence',
    'alert_sources',
    'auth',
    'automation_control',
    'cluster',
    'governance',
    'health',
    'identity_providers',
    'inventory',
    'jobs',
    'knowledge',
    'kubernetes_operations',
    'metrics_sources',
    'notification_channels',
    'notifications',
    'object_storage',
    'rbac',
    'resolver',
    'retention',
    'users',
    'utils',
}

RETIRED_IMPORT_PREFIXES = tuple(f'app.{name}' for name in sorted(FORBIDDEN_ROOTS))


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            values.append(node.module)
    return tuple(values)


def _route_persistence_files() -> set[str]:
    result: set[str] = set()
    for path in APP.rglob('*.py'):
        if path.name != 'routes.py' and not path.name.endswith('_routes.py'):
            continue
        source = path.read_text(encoding='utf-8')
        if 'db.session' in source or '.query' in source:
            result.add(path.relative_to(ROOT).as_posix())
    return result


def _presentation_mutation_files() -> set[str]:
    result: set[str] = set()
    mutations = ('db.session.add', 'db.session.commit', 'db.session.delete', 'db.session.flush')
    for path in APP.rglob('*.py'):
        if path.name != 'presentation.py' and not path.name.endswith('_presentation.py'):
            continue
        source = path.read_text(encoding='utf-8')
        if any(marker in source for marker in mutations):
            result.add(path.relative_to(ROOT).as_posix())
    return result


def _strict_layer_checks(errors: list[str]) -> None:
    for path in APP.rglob('*.py'):
        source = path.read_text(encoding='utf-8')
        relative = path.relative_to(ROOT).as_posix()
        if path.name == 'repository.py' or path.name.endswith('_repository.py'):
            for forbidden in (
                'from flask import request',
                'from flask_login import current_user',
                'render_template',
                'redirect(',
            ):
                if forbidden in source:
                    errors.append(
                        f'repository layer depends on web presentation/request state: {relative} -> {forbidden}'
                    )
        if path.name in {'service.py', 'services.py'} or path.name.endswith('_service.py'):
            if 'render_template' in source:
                errors.append(f'service layer renders templates instead of returning application data: {relative}')


def main() -> int:
    errors: list[str] = []

    root_dirs = {path.name for path in APP.iterdir() if path.is_dir() and path.name != '__pycache__'}
    unexpected = sorted(root_dirs - ALLOWED_APP_ROOT_DIRS)
    for name in unexpected:
        errors.append(f'non-canonical top-level app package: app/{name}')
    for name in sorted(FORBIDDEN_ROOTS & root_dirs):
        errors.append(f'retired top-level package still exists: app/{name}')

    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).exists():
            errors.append(f'canonical package/template path is missing: {relative}')

    for path in APP.rglob('*.py'):
        for target in _imports(path):
            if any(target == prefix or target.startswith(f'{prefix}.') for prefix in RETIRED_IMPORT_PREFIXES):
                errors.append(f'{path.relative_to(ROOT)} imports retired top-level namespace {target}')

    try:
        baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f'cannot load MVC debt baseline: {exc}')
        baseline = {}

    actual_routes = _route_persistence_files()
    allowed_routes = set(baseline.get('route_persistence_files') or ())
    for path in sorted(actual_routes - allowed_routes):
        errors.append(f'new controller persistence debt is forbidden: {path}')
    for path in sorted(allowed_routes - actual_routes):
        errors.append(f'MVC debt baseline is stale; remove resolved controller persistence entry: {path}')

    actual_presentations = _presentation_mutation_files()
    allowed_presentations = set(baseline.get('presentation_mutation_files') or ())
    for path in sorted(actual_presentations - allowed_presentations):
        errors.append(f'new presentation mutation debt is forbidden: {path}')
    for path in sorted(allowed_presentations - actual_presentations):
        errors.append(f'MVC debt baseline is stale; remove resolved presentation mutation entry: {path}')

    _strict_layer_checks(errors)

    readme = (ROOT / 'docs/architecture/APPLICATION_PACKAGE_STANDARD.md').read_text(encoding='utf-8')
    for marker in ('modular monolith', 'domain-first MVC', 'route -> form/contract -> service/policy'):
        if marker.lower() not in readme.lower():
            errors.append(f'application package standard is missing architecture marker: {marker}')

    if errors:
        print('FAIL — KAORI Application Package Architecture')
        for error in errors:
            print(f'- {error}')
        return 1

    print(
        'PASS — KAORI Application Package Architecture · '
        f'{len(root_dirs)} top-level packages · '
        f'{len(actual_routes)} controller persistence debt files · '
        f'{len(actual_presentations)} presentation mutation debt files'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
