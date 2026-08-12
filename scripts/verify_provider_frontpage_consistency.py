from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    provider_pages = {
        'Kubernetes': read('app/templates/integrations/kubernetes.html'),
        'Prometheus': read('app/templates/integrations/prometheus.html'),
        'Alertmanager': read('app/templates/integrations/alertmanager.html'),
        'MinIO': read('app/templates/minio/index.html'),
    }
    shared_frontpage = read('app/templates/integrations/components/_provider_frontpage.html')
    shared_registry = read('app/templates/integrations/components/_provider_registry.html')
    shared_tabs = read('app/templates/components/integration_workspace_tabs.html')

    connection_registries = {
        'Kubernetes': read('app/templates/integrations/kubernetes/partials/_registry.html'),
        'Prometheus': read('app/templates/integrations/prometheus/partials/_inventory_content.html'),
        'Alertmanager': read('app/templates/integrations/alertmanager/partials/_inventory_content.html'),
        'MinIO': read('app/templates/minio/partials/_registry_content.html'),
    }
    direct_coverage = {
        'Kubernetes': read('app/templates/integrations/kubernetes/partials/_integration_coverage.html'),
        'MinIO': read('app/templates/minio/partials/_coverage_content.html'),
    }
    observability_coverage = read('app/templates/components/integration_coverage_content.html')
    workspace_standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    for provider, page in provider_pages.items():
        assert 'integrations/components/_provider_frontpage.html' in page, provider
        assert 'components/integration_workspace_tabs.html' in page, provider
        assert 'provider_front.hero(' in page, provider
        assert 'provider_front.overview(' in page, provider
        assert 'integration_tabs.render(' in page, provider

    for marker in (
        'data-kaori-provider-frontpage-hero',
        'Operational Integration',
        'Registered Connections',
        'Ready Connections',
        'Consumer Bindings',
        'Register Connection',
        'Integration Contract',
        'Consumer Resolution',
        'Authority Boundary',
    ):
        assert marker in shared_frontpage

    for marker in ('Integration Coverage', 'Connection Registry'):
        assert marker in shared_tabs

    for marker in (
        'connection_registry_table_classes',
        'connection_registry_colgroup',
        'connection_registry_head',
        'Endpoint / Scope',
        'Core Readiness',
        'Compatibility',
        'Bindings',
        'Actions',
        'asset_coverage_table_classes',
        'asset_coverage_colgroup',
        'asset_coverage_head',
        'scope_coverage_colgroup',
        'scope_coverage_head',
    ):
        assert marker in shared_registry

    for provider, content in connection_registries.items():
        assert 'provider_registry.connection_registry_table_classes()' in content, provider
        assert 'provider_registry.connection_registry_colgroup()' in content, provider
        assert 'provider_registry.connection_registry_head()' in content, provider
        assert 'table-fixed' not in content, provider

    for provider, content in direct_coverage.items():
        assert 'provider_registry.asset_coverage_table_classes()' in content, provider
        assert 'provider_registry.asset_coverage_colgroup()' in content, provider
        assert 'provider_registry.asset_coverage_head(' in content, provider
        assert 'table-fixed' not in content, provider

    assert 'Operational Readiness Paths' not in direct_coverage['Kubernetes']
    assert 'provider_registry.scope_coverage_colgroup()' in observability_coverage
    assert 'provider_registry.scope_coverage_head()' in observability_coverage
    assert 'table-fixed' not in observability_coverage

    assert '## Provider Front Page Contract' in workspace_standard
    assert 'Connection | Endpoint / Scope | Core Readiness | Compatibility | Bindings | Actions' in workspace_standard
    assert 'Asset / Scope | Provider API | Metrics Source | Alert Source | Coverage | Actions' in workspace_standard
    assert (
        'Operational Scope | Environment | Primary Source | Consumer Binding | Coverage | Actions' in workspace_standard
    )
    assert 'front page must not introduce a provider-only giant card layout' in workspace_standard

    coverage = (ROOT / 'app/templates/components/integration_coverage_content.html').read_text()
    registry = (ROOT / 'app/templates/integrations/components/_provider_registry.html').read_text()
    minio_form = (ROOT / 'app/templates/minio/instance_form.html').read_text()
    minio_routes = (ROOT / 'app/minio/routes.py').read_text()
    assert 'Consumer Asset' in registry
    assert "item_label='Assets'" in coverage or 'item_label="Assets"' in coverage
    assert 'empty_state_show_admin_required' not in coverage
    assert 'connection_validation_header.render(' in minio_form
    assert 'minio.test_new_instance_connection' in minio_form
    assert 'minio-connection-tested' in minio_routes

    print('PASS — KAORI provider front pages share DRY Hero, coverage, and connection-registry contracts.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
