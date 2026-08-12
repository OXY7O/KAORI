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
    domain_service = read('app/integrations/domain_service.py')
    domain_template = read('app/templates/integrations/domain.html')
    breadcrumbs = read('app/common/navigation.py')
    presentation = read('app/bootstrap/presentation.py')

    for endpoint in (
        "workspace_endpoint='integrations.orchestration'",
        "workspace_endpoint='integrations.observability'",
        "workspace_endpoint='integrations.storage'",
    ):
        if endpoint not in taxonomy:
            errors.append(f'taxonomy missing domain workspace endpoint: {endpoint}')

    for marker in (
        'asset_types: tuple[str, ...] = ()',
        "asset_types=('kubernetes_cluster',)",
        "asset_types=('object_storage_system',)",
        'def asset_types_for_domain(domain_key: str)',
        'def domain_key_for_asset_type(asset_type: str)',
    ):
        if marker not in taxonomy:
            errors.append(f'taxonomy missing asset-ownership contract: {marker}')

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
        "provider_type == 'minio'",
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
        "active_tab=request.args.get('tab', 'registry').strip()",
        "provider_per_page=request.args.get('provider_per_page', 5, type=int) or 5",
        "binding_per_page=request.args.get('binding_per_page', 5, type=int) or 5",
    ):
        if marker not in routes:
            errors.append(f'domain route contract missing: {marker}')

    if 'from app.integrations.domain_service import build_integration_domain_page' not in routes:
        errors.append('domain routes must import the dedicated domain page builder from its owning module')
    if 'from app.integrations.domain_service import build_integration_domain_page' in service:
        errors.append('integration service must not re-export the domain page builder')

    for marker in (
        'get_domain_definition(domain_key)',
        'for module in registry.all() if module.domain_key == domain.key',
        'IntegrationInstance.query.options(selectinload(IntegrationInstance.bindings))',
        'IntegrationInstance.provider_type.in_(provider_types)',
        'asset_types_for_domain(domain_key)',
        'IntegrationBinding.asset_type.in_(owned_asset_types)',
        'domain_key_for_asset_type(binding.asset_type)',
        'selector_summary(binding.selector_json',
        'paginate_sequence(',
        "'bindings': sum(1 for binding in related_bindings if binding.enabled)",
        'consumer_bindings = [binding for binding in related_bindings if not _is_owner_asset_binding(binding)]',
        'module.domain_key == owner_domain',
        '_consumer_binding_count(instance, consumer_bindings)',
    ):
        if marker not in domain_service:
            errors.append(f'domain page is not canonical asset/binding driven: {marker}')

    for forbidden in (
        'KubernetesConnection.query',
        'PrometheusInstance.query',
        'AlertmanagerInstance.query',
        'MinioInstance.query',
    ):
        if forbidden in domain_service:
            errors.append(f'domain page contains provider-specific query: {forbidden}')

    for marker in (
        'Capability Registry',
        'Provider Registry',
        'Bindings',
        'Registry and Consumer Bindings',
        'data-kaori-domain-provider-registry',
        'data-kaori-domain-binding-registry',
        'No {{ domain.label }} Provider Registered',
        'No {{ domain.label }} Bindings Yet',
        'Core Validation',
        'Add Consumer Binding',
        'Consumer Contract',
        'Domain Operating Boundary',
        'provider_registry_pagination.allowed_per_page',
        'binding_registry_pagination.allowed_per_page',
        'Open {{ item.runtime_label }}',
        'hx_target="#domain-workspace"',
        'hx_select="#domain-workspace"',
        'hx_indicator="#integration-domain-workspace-loading"',
    ):
        if marker not in domain_template:
            errors.append(f'domain template missing canonical registry/binding boundary: {marker}')

    if (
        'Native provider ownership is represented by the Provider Registry and is not duplicated as a consumer binding.'
        not in domain_template
    ):
        errors.append('domain binding empty state does not explain consumer-only binding semantics')
    if 'Native Provider Contract' in domain_service:
        errors.append('domain binding registry still exposes native provider ownership as a consumer contract')
    if 'Consumer Profile Pending' not in domain_service:
        errors.append('domain binding registry does not use consumer-profile fallback semantics')

    for marker in (
        "BreadcrumbItem(integration_owner['domain_label'])",
        "BreadcrumbItem(integration_owner['provider_label'])",
        "'integrations.storage': 'Storage'",
        'integration_owner: Mapping[str, str] | None = None',
    ):
        if marker not in breadcrumbs:
            errors.append(f'breadcrumb taxonomy missing: {marker}')
    for marker in ('integration_endpoint_owner(request.endpoint)', 'integration_owner=integration_owner'):
        if marker not in presentation:
            errors.append(f'bootstrap breadcrumb ownership missing: {marker}')

    registrations = {
        'app/integrations/kubernetes/__init__.py': "navigation_endpoint_prefixes=('integrations.kubernetes', 'cluster.')",
        'app/integrations/prometheus/__init__.py': "navigation_endpoint_prefixes=('integrations.prometheus', 'prometheus.')",
        'app/integrations/alertmanager/__init__.py': "navigation_endpoint_prefixes=('integrations.alertmanager', 'alertmanager.')",
        'app/integrations/minio/__init__.py': "navigation_endpoint_prefixes=('minio.',)",
    }
    for relative, marker in registrations.items():
        if marker not in read(relative):
            errors.append(f'{relative}: navigation ownership missing')

    if '{% call integration_ui.section_header(' in domain_template:
        errors.append('domain template must render section_header directly; it is not a caller macro')
    if '{{ integration_ui.section_header(' not in domain_template:
        errors.append('domain template is missing direct section_header macro rendering')

    if errors:
        print('FAIL — KAORI Integration Domain Navigation')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Integration Domain Navigation')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
