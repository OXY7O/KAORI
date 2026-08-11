#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def main() -> int:
    errors: list[str] = []

    taxonomy = read('app/integrations/taxonomy.py')
    registry = read('app/integrations/registry.py')
    navigation = read('app/integrations/navigation.py')
    sidebar = read('app/templates/components/navigation/integrations_menu.html')
    routes = read('app/integrations/routes.py')
    service = read('app/integrations/service.py')
    domain_template = read('app/templates/integrations/domain.html')
    breadcrumbs = read('app/common/navigation.py')

    for endpoint in (
        "workspace_endpoint='integrations.orchestration'",
        "workspace_endpoint='integrations.observability'",
        "workspace_endpoint='integrations.storage'",
    ):
        if endpoint not in taxonomy:
            errors.append(f'taxonomy missing domain workspace endpoint: {endpoint}')

    if 'navigation_endpoint_prefixes: tuple[str, ...]' not in registry:
        errors.append('IntegrationModule is missing navigation endpoint ownership metadata')

    for marker in (
        'for module in registry.all()',
        'module.navigation_endpoint_prefixes',
        'active_domain_key = module.domain_key',
    ):
        if marker not in navigation:
            errors.append(f'registry-driven navigation missing: {marker}')

    for forbidden in (
        "provider_type == 'kubernetes'",
        "provider_type == 'prometheus'",
        "provider_type == 'alertmanager'",
    ):
        if forbidden in navigation:
            errors.append(f'provider-specific navigation branching returned: {forbidden}')

    for marker in (
        'integration_navigation.domains',
        'url_for(domain.workspace_endpoint)',
        '{{ domain.label }}',
    ):
        if marker not in sidebar:
            errors.append(f'sidebar domain projection missing: {marker}')

    for forbidden in (
        "url_for('integrations.kubernetes')",
        "url_for('integrations.prometheus')",
        "url_for('integrations.alertmanager')",
    ):
        if forbidden in sidebar:
            errors.append(f'product-specific Integration sidebar link returned: {forbidden}')

    for marker in (
        "@integrations_bp.get('/orchestration')",
        "@integrations_bp.get('/observability')",
        "@integrations_bp.get('/storage')",
        "'integrations/domain.html'",
    ):
        if marker not in routes:
            errors.append(f'domain route contract missing: {marker}')

    builder = service.split('def build_integration_domain_page', 1)[1].split(
        'def _kubernetes_readiness', 1
    )[0]
    for marker in (
        'IntegrationInstance.query.options(selectinload(IntegrationInstance.bindings))',
        'IntegrationInstance.provider_type.in_(provider_types)',
        'capability_definitions_for_domain(domain.key)',
        "'bindings': bindings",
        "'status': status",
    ):
        if marker not in builder:
            errors.append(f'domain page is not canonical-identity driven: {marker}')
    for forbidden in ('KubernetesConnection.query', 'PrometheusInstance.query', 'AlertmanagerInstance.query'):
        if forbidden in builder:
            errors.append(f'domain page contains provider-specific query: {forbidden}')

    for marker in (
        'Capability Portfolio',
        'Provider Workspaces',
        'Domain Operating Boundary',
        'Ready for provider registration',
        'Register Provider',
        'Validate Runtime',
        'Bind Assets',
    ):
        if marker not in domain_template:
            errors.append(f'domain template missing KAORI boundary: {marker}')

    if '{% call integration_ui.section_header(' in domain_template:
        errors.append('domain template must render section_header directly; the macro does not accept a caller block')
    if '{{ integration_ui.section_header(' not in domain_template:
        errors.append('domain template is missing the direct section_header macro render')

    for marker in (
        "BreadcrumbItem('Orchestration')",
        "BreadcrumbItem('Observability')",
        "'integrations.storage': 'Storage'",
    ):
        if marker not in breadcrumbs:
            errors.append(f'breadcrumb taxonomy missing: {marker}')

    registrations = {
        'app/integrations/kubernetes/__init__.py': "navigation_endpoint_prefixes=('integrations.kubernetes', 'cluster.')",
        'app/integrations/prometheus/__init__.py': "navigation_endpoint_prefixes=('integrations.prometheus', 'prometheus.')",
        'app/integrations/alertmanager/__init__.py': "navigation_endpoint_prefixes=('integrations.alertmanager', 'alertmanager.')",
    }
    for relative, marker in registrations.items():
        if marker not in read(relative):
            errors.append(f'{relative}: navigation ownership missing')

    if errors:
        print('FAIL — KAORI Integration Domain Navigation')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Integration Domain Navigation')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
