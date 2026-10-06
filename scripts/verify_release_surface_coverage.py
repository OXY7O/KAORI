#!/usr/bin/env python3
"""Fail closed when a KAORI navigation or registered web domain lacks release ownership."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from release_surface_registry import SURFACES, blueprint_vars, navigation_endpoints

ROOT = Path(__file__).resolve().parents[1]
NAVIGATION_DIR = ROOT / 'app/templates/components/navigation'
BLUEPRINTS = ROOT / 'app/bootstrap/blueprints.py'
QUALITY_GATE = ROOT / 'scripts/quality_gate.sh'
COVERAGE_DOC = ROOT / 'docs/architecture/RELEASE_SURFACE_COVERAGE.md'
INTEGRATION_TAXONOMY_CATALOG = ROOT / 'app/definitions/catalogs/integrations/taxonomy.yaml'

EXPECTED_MENU_TEMPLATES = {
    'access_management_menu.html',
    'analytics_menu.html',
    'dashboards_menu.html',
    'governance_menu.html',
    'integrations_menu.html',
    'intelligence_menu.html',
    'inventory_menu.html',
    'kubernetes_operations_menu.html',
    'object_storage_menu.html',
    'platform_operations_menu.html',
    'reports_menu.html',
    'settings_menu.html',
    'tenant_menu.html',
}

LEGACY_CLUSTER_TEMPLATES = (
    'app/templates/kubernetes/cluster/index.html',
    'app/templates/kubernetes/cluster/partials/_delete_modal.html',
    'app/templates/kubernetes/cluster/partials/_inventory_badge.html',
    'app/templates/kubernetes/cluster/partials/_loading_bar.html',
    'app/templates/kubernetes/cluster/partials/_pagination.html',
    'app/templates/kubernetes/cluster/partials/_status_badge.html',
    'app/templates/kubernetes/cluster/partials/_table.html',
)


def _read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise AssertionError(f'Missing release-coverage file: {relative}')
    return path.read_text(encoding='utf-8')


def _literal_url_for_endpoints(source: str) -> set[str]:
    return {match for match in re.findall(r"url_for\(\s*['\"]([^'\"]+)['\"]", source) if match != 'static'}


def _integration_domain_endpoints() -> set[str]:
    source = INTEGRATION_TAXONOMY_CATALOG.read_text(encoding='utf-8')
    return set(re.findall(r'^\s*workspace_endpoint:\s*([^\s#]+)', source, re.M))


def _intelligence_link_endpoints(source: str) -> set[str]:
    match = re.search(r'{% set intelligence_links = \[(.*?)\] %}', source, re.S)
    if not match:
        return set()
    return set(re.findall(r"\(\s*['\"]([^'\"]+)['\"]\s*,", match.group(1)))


def _navigation_source_endpoints(relative: str) -> set[str]:
    source = _read(relative)
    endpoints = _literal_url_for_endpoints(source)
    if relative.endswith('intelligence_menu.html'):
        endpoints.update(_intelligence_link_endpoints(source))
    if relative.endswith('integrations_menu.html') and 'integration_navigation.domains' in source:
        endpoints.update(_integration_domain_endpoints())
    return endpoints


def _registered_blueprint_vars() -> set[str]:
    tree = ast.parse(BLUEPRINTS.read_text(encoding='utf-8'), filename=str(BLUEPRINTS))
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != 'blueprint':
            continue
        if not isinstance(node.iter, (ast.Tuple, ast.List)):
            continue
        names = {item.id for item in node.iter.elts if isinstance(item, ast.Name)}
        if names:
            return names
    raise AssertionError('app/bootstrap/blueprints.py: registered blueprint tuple was not found')


def verify() -> None:
    errors: list[str] = []
    navigation_count = len(navigation_endpoints())
    blueprint_count = len(blueprint_vars())

    actual_menu_templates = {path.name for path in NAVIGATION_DIR.glob('*_menu.html')}
    if actual_menu_templates != EXPECTED_MENU_TEMPLATES:
        missing = sorted(EXPECTED_MENU_TEMPLATES - actual_menu_templates)
        extra = sorted(actual_menu_templates - EXPECTED_MENU_TEMPLATES)
        if missing:
            errors.append(f'Navigation menu templates missing from source: {", ".join(missing)}')
        if extra:
            errors.append(f'Navigation menu templates lack release ownership: {", ".join(extra)}')

    seen_navigation: dict[str, str] = {}
    for surface in SURFACES:
        if surface.lock_state not in {'LOCKED', 'BASELINE LOCKED', 'SYSTEM LOCKED'}:
            errors.append(f'{surface.title}: unsupported lock state {surface.lock_state!r}')

        for verifier in surface.verifiers:
            if not (ROOT / verifier).exists():
                errors.append(f'{surface.title}: missing verifier {verifier}')

        for contract_path in surface.contract_paths:
            if not (ROOT / contract_path).exists():
                errors.append(f'{surface.title}: missing release evidence {contract_path}')

        if surface.navigation_source is None:
            if surface.navigation_endpoints:
                errors.append(f'{surface.title}: non-navigation surface unexpectedly declares sidebar endpoints')
            continue

        actual = _navigation_source_endpoints(surface.navigation_source)
        expected = set(surface.navigation_endpoints)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            if missing:
                errors.append(f'{surface.title}: navigation endpoint missing: {", ".join(missing)}')
            if extra:
                errors.append(f'{surface.title}: unowned navigation endpoint: {", ".join(extra)}')

        for endpoint in surface.navigation_endpoints:
            owner = seen_navigation.setdefault(endpoint, surface.title)
            if owner != surface.title:
                errors.append(f'{endpoint}: navigation ownership overlaps {owner} and {surface.title}')

    expected_navigation = set(navigation_endpoints())
    if set(seen_navigation) != expected_navigation:
        errors.append('Canonical navigation endpoint registry did not close exactly')

    registered_blueprints = _registered_blueprint_vars()
    expected_blueprints = set(blueprint_vars())
    if registered_blueprints != expected_blueprints:
        missing = sorted(expected_blueprints - registered_blueprints)
        extra = sorted(registered_blueprints - expected_blueprints)
        if missing:
            errors.append(f'Registered blueprint missing from application bootstrap: {", ".join(missing)}')
        if extra:
            errors.append(f'Registered blueprint lacks release-surface owner: {", ".join(extra)}')

    sidebar = _read('app/templates/components/navigation/sidebar.html')
    if 'can_clusters' in sidebar:
        errors.append('sidebar.html: stale can_clusters capability remains without a direct menu owner')
    kubernetes_registration = _read(
        'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/__init__.py'
    )
    if "navigation_endpoint_prefixes=('integrations.kubernetes', 'cluster.')" not in kubernetes_registration:
        errors.append(
            'Integrations → Orchestration must remain the navigation owner for Kubernetes and cluster.* routes'
        )

    for relative in LEGACY_CLUSTER_TEMPLATES:
        if (ROOT / relative).exists():
            errors.append(f'Legacy Cluster Management listing surface returned: {relative}')
    for path in (ROOT / 'app/templates').rglob('*.html'):
        if 'cluster.list_clusters' in path.read_text(encoding='utf-8'):
            errors.append(f'{path.relative_to(ROOT)}: retired cluster.list_clusters endpoint returned')

    quality_gate = QUALITY_GATE.read_text(encoding='utf-8')
    if 'python scripts/verify_release_surface_coverage.py' not in quality_gate:
        errors.append('scripts/quality_gate.sh must execute release-surface coverage before domain verifiers')
    for surface in SURFACES:
        for verifier in surface.verifiers:
            command = f'python {verifier}'
            if command not in quality_gate:
                errors.append(f'{surface.title}: {verifier} is not wired into scripts/quality_gate.sh')

    if not COVERAGE_DOC.exists():
        errors.append('docs/architecture/RELEASE_SURFACE_COVERAGE.md is missing')
    else:
        documentation = COVERAGE_DOC.read_text(encoding='utf-8')
        for surface in SURFACES:
            if surface.title not in documentation or surface.lock_state not in documentation:
                errors.append(f'{surface.title}: release coverage documentation is incomplete')
        for token in (
            f'{navigation_count} navigation links',
            f'{blueprint_count} registered blueprints',
            'Cluster Management',
            'Integrations → Orchestration → Kubernetes',
        ):
            if token not in documentation:
                errors.append(f'Release coverage documentation missing: {token}')

    if errors:
        print('FAIL — KAORI Release Coverage')
        for error in errors:
            print(f'- {error}')
        raise SystemExit(1)

    print(f'PASS — KAORI Release Coverage · {navigation_count} links / {blueprint_count} blueprints')


if __name__ == '__main__':
    verify()
