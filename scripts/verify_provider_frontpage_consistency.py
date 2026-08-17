from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    provider_pages = {
        'Kubernetes': read('app/templates/integrations/kubernetes.html'),
        'Metrics Source': read('app/templates/integrations/metrics.html'),
        'Alertmanager': read('app/templates/integrations/alertmanager.html'),
        'MinIO': read('app/templates/minio/index.html'),
    }
    shared_frontpage = read('app/templates/integrations/components/_provider_frontpage.html')
    shared_registry = read('app/templates/integrations/components/_provider_registry.html')
    shared_tabs = read('app/templates/components/integration_workspace_tabs.html')

    connection_registries = {
        'Kubernetes': read('app/templates/integrations/kubernetes/partials/_registry.html'),
        'Metrics Source': read('app/templates/integrations/metrics/partials/_inventory_content.html'),
        'Alertmanager': read('app/templates/integrations/alertmanager/partials/_inventory_content.html'),
        'MinIO': read('app/templates/minio/partials/_registry_content.html'),
    }
    direct_coverage = {
        'Kubernetes': read('app/templates/integrations/kubernetes/partials/_integration_coverage.html'),
        'MinIO': read('app/templates/minio/partials/_coverage_content.html'),
    }
    observability_coverage = read('app/templates/components/integration_coverage_content.html')
    workspace_standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    shared_registration_hero = read('app/templates/integrations/components/_provider_registration_hero.html')
    shared_registration_context = read('app/templates/integrations/components/_provider_registration_context.html')
    shared_registration_actions = read('app/templates/integrations/components/_provider_registration_actions.html')
    shared_detail_posture = read('app/templates/integrations/components/_provider_detail_posture.html')
    shared_configuration_contract = read('app/templates/integrations/components/_provider_configuration_contract.html')
    coverage_service = read('app/integrations/coverage.py')
    provider_registration_pages = {
        'Kubernetes': read('app/templates/cluster/add.html'),
        'Metrics Source': read('app/templates/metrics/instance_form.html'),
        'Alertmanager': read('app/templates/alertmanager/instance_form.html'),
        'MinIO': read('app/templates/minio/instance_form.html'),
    }

    for provider, page in provider_pages.items():
        assert 'integrations/components/_provider_frontpage.html' in page, provider
        assert 'components/integration_workspace_tabs.html' in page, provider
        assert 'provider_front.hero(' in page, provider
        assert 'provider_front.overview(' in page, provider
        assert 'integration_tabs.render(' in page, provider
        assert 'Coverage Gaps' in page, provider
        assert 'Uncovered Assets' not in page, provider
        assert 'Uncovered Scopes' not in page, provider

    assert 'stats.ready == stats.total' in provider_pages['Alertmanager']
    assert 'stats.ready == stats.configured' not in provider_pages['Alertmanager']

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

    overview = read('app/templates/integrations/overview.html')
    overview_service = read('app/integrations/service.py')
    for marker in (
        "available_provider_count ~ ' Providers'",
        'item.posture_state',
        'item.posture_label',
        'item.readiness_percent',
        'Operational Readiness',
        'progress_bar.bar(item.readiness_percent',
    ):
        assert marker in overview
    for marker in (
        "'ready': ready",
        "'total': total",
        "'attention': attention",
        "'readiness_percent':",
        "'posture_state': posture_state",
        "'posture_label': posture_label",
    ):
        assert marker in overview_service

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
    assert 'Consumer Asset | Environment | Primary Source | Consumer Binding | Coverage | Actions' in workspace_standard
    assert 'front page must not introduce a provider-only giant card layout' in workspace_standard

    for marker in (
        'data-kaori-provider-registration-hero',
        'Registration Posture',
        'Pre-Save Requirements',
        'Draft',
        'Before Save',
        'Test Connection',
        'Registration reuses the verified payload',
        'After Save',
        'Core Validation',
        'Then assign consumer bindings',
        'Back to Registry',
    ):
        assert marker in shared_registration_hero

    for provider, page in provider_registration_pages.items():
        assert 'integrations/components/_provider_registration_hero.html' in page, provider
        assert 'provider_registration_hero.render(' in page, provider
        assert 'integrations/components/_provider_registration_context.html' in page, provider
        assert 'provider_registration_context.render(' in page, provider

    for marker in (
        'data-kaori-provider-registration-context',
        'info_flow.render(',
        'related_page_card.render(',
        'Related Operational Workspace',
    ):
        assert marker in shared_registration_context
    assert 'information_guide_card' not in shared_registration_context
    assert 'context_guidance_card' not in shared_registration_context

    assert 'Register Kubernetes Connection' in provider_registration_pages['Kubernetes']
    assert 'Add Kubernetes Connection' not in provider_registration_pages['Kubernetes']
    assert 'Register Alertmanager Connection' in provider_registration_pages['Alertmanager']

    registration_forms = {
        'Kubernetes': read('app/templates/cluster/add.html') + read('app/templates/cluster/partials/_form.html'),
        'Metrics Source': provider_registration_pages['Metrics Source'],
        'Alertmanager': provider_registration_pages['Alertmanager'],
        'MinIO': provider_registration_pages['MinIO'],
    }
    for marker in (
        'data-kaori-provider-registration-actions',
        'Connection Test Required',
        'Complete Test Connection before registration.',
        'Connection Verified',
        'Verified connection payload is ready to register.',
        'Cancel',
        'Register Connection',
    ):
        assert marker in shared_registration_actions

    for provider, form in registration_forms.items():
        assert 'integrations/components/_provider_registration_actions.html' in form, provider
        assert 'provider_registration_actions.render(' in form, provider
        assert 'Run Test Connection successfully before KAORI enables Register Connection.' not in form, provider

    assert 'placeholder="Alertmanager Production"' in registration_forms['Alertmanager']
    assert 'placeholder="Operational purpose and ownership context"' in registration_forms['Alertmanager']
    assert 'Use a stable operational name' not in registration_forms['Alertmanager']
    assert 'What this controls:' not in registration_forms['Alertmanager']
    assert 'Allowed range: 1–30 seconds.' not in registration_forms['Alertmanager']

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
    minio_client = read('app/integrations/minio/client.py')
    minio_service = read('app/minio/service.py')
    assert 's3:ListAllMyBuckets' in minio_client
    assert '/minio/health/live' in minio_client
    assert 'identity_evidence' in minio_client
    assert "if result.product != 'minio'" not in minio_service

    for marker in (
        'data-kaori-provider-detail-posture',
        'Connection Posture',
        'Review Validation',
        'Back to Registry',
    ):
        assert marker in shared_detail_posture

    for marker in (
        'data-kaori-provider-configuration-contract',
        'Connection Contract',
        'Connection Evidence',
        'operational_context.render(',
        'Configure Connection',
    ):
        assert marker in shared_configuration_contract
    assert 'Operational Boundary' not in shared_configuration_contract
    assert 'Operational Flow' not in shared_configuration_contract

    assert 'registered_consumer_asset_definitions' in coverage_service
    assert 'definition.asset_type' in coverage_service
    assert "'scope_type': definition.asset_type" in coverage_service
    print(
        'PASS — KAORI provider front pages and connection forms share DRY Hero, two-surface context, gated registration actions, canonical field copy, coverage, and registry contracts.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
