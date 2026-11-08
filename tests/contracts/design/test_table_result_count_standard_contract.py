"""Canonical KAORI table Results badges; source-only review contract (#1675)."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / 'app' / 'templates'


def _template(path: str) -> str:
    return (TEMPLATES / path).read_text(encoding='utf-8')


def test_shared_result_count_badge_pluralization_and_missing_evidence() -> None:
    template = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True).get_template(
        'components/table_label.html'
    )
    counter = template.module.result_count
    zero = str(counter(0))
    one = str(counter(1))
    three = str(counter(3))
    assert '0 Results' in zero
    assert '1 Result' in one and '1 Results' not in one
    assert '3 Results' in three
    assert 'data-lucide="list-filter"' in three
    assert 'kaori-semantic-label' in three and 'bg-kaori-soft' in three
    assert str(counter(None)).strip() == ''


def test_shared_block_header_accepts_count_without_replacing_info_tip_or_actions() -> None:
    content = _template('components/table.html')
    assert "title_extra='', result_count=none" in content
    assert '{% if title_extra %}{{ title_extra }}{% endif %}' in content
    assert '{% if result_count is not none %}{{ table_label.result_count(result_count) }}{% endif %}' in content
    assert 'class="flex min-h-6 flex-wrap items-center gap-1.5"' in content
    assert 'data-kaori-table-header-actions' in content


def test_inventory_and_tenant_results_use_filtered_total_not_visible_rows() -> None:
    inventory = (
        'configuration',
        'ingresses',
        'namespaces',
        'nodes',
        'pods',
        'services',
        'storage',
        'workloads',
    )
    for resource in inventory:
        content = _template(f'kubernetes/inventory/{resource}/partials/_table_card.html')
        assert 'result_count=pagination.total_items' in content

    for resource in ('systems', 'buckets'):
        content = _template(f'storage/object_storage/inventory/{resource}/partials/_table_card.html')
        assert 'result_count=inventory.pagination.total_items' in content

    counts = {
        '_tenant_registry.html': 'tenant_pagination',
        '_namespace_registry.html': 'namespace_pagination',
        '_resource_profile_registry.html': 'profile_pagination',
        '_group_registry.html': 'group_pagination',
        '_membership_registry.html': 'membership_pagination',
        '_credential_registry.html': 'credential_pagination',
        '_access_grant_registry.html': 'access_grant_pagination',
        '_namespace_access_registry.html': 'namespace_access_pagination',
    }
    for name, pagination in counts.items():
        content = _template(f'kubernetes/tenant/partials/{name}')
        assert f'result_count={pagination}.total_items' in content


def test_registry_inventory_has_only_one_shared_result_badge() -> None:
    content = _template('artifact_registry/partials/_inventory_workspace.html')
    assert 'result_count=inventory.total' in content
    assert 'title_extra=registry_title_tip' in content
    assert 'registry_title_tip ~ result_badge' not in content
    assert '{% set result_badge %}' not in content


def test_other_domain_tables_reuse_same_badge() -> None:
    sources = {
        'access/roles/partials/_registry.html': 'summary.matching',
        'access/permissions/partials/_registry.html': 'matching_count',
        'access/identity_providers/partials/_registry.html': 'summary.matching',
        'access/activity_audit/partials/_activity_table_card.html': 'pagination.total',
        'reports/generated/index.html': 'payload.pagination.total_items',
        'reports/report_templates/index.html': 'payload.pagination.total_items',
        'reports/schedules/index.html': 'payload.run_pagination.total_items',
        'platform_operations/jobs/executions/partials/_registry.html': 'job_pagination.total_items',
        'kubernetes/governance/tls_certificates/partials/_table.html': 'payload.pagination.total_items',
        'integrations/components/_asset_owner_observability_sources.html': 'visible_total',
    }
    for path, count_expr in sources.items():
        assert f'table_label.result_count({count_expr})' in _template(path) or (
            f'result_count={count_expr}' in _template(path)
        )


def test_connection_registry_shared_header_preserves_filter_actions() -> None:
    header = _template('integrations/components/_provider_registry.html')
    assert "action_html='', result_count=none" in header
    assert 'table_label.result_count(result_count)' in header
    assert 'if action_html' in header

    for path in (
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html',
        'integrations/storage/object_storage/providers/minio/partials/_registry.html',
        'integrations/registry/providers/harbor/partials/_registry.html',
    ):
        assert 'result_count=pagination.total_items' in _template(path)


def test_additional_table_workspaces_use_filtered_results_badges() -> None:
    cases = {
        'integrations/delivery/notification_channels/partials/_channels_workspace.html': (
            'payload.channel_pagination.total_items'
        ),
        'reports/overview/partials/_recent_reports.html': 'payload.recent_reports|length',
        'intelligence/partials/_catalog_results.html': 'payload.pagination.total_items',
        'intelligence/partials/_recommendations_results.html': 'payload.pagination.total_items',
        'storage/object_storage/analytics/partials/_bucket_table.html': 'bucket_table.pagination.total_items',
        'storage/object_storage/analytics/partials/_bucket_forecast_table.html': 'forecast_table.pagination.total_items',
    }
    for path, count in cases.items():
        source = _template(path)
        assert f'table_label.result_count({count})' in source or f'result_count={count}' in source

    channels = _template('integrations/delivery/notification_channels/partials/_channels_workspace.html')
    assert 'table_block.inventory_block_header(' in channels
    assert 'result_count=payload.channel_pagination.total_items' in channels


def test_integration_binding_headers_are_title_adjacent() -> None:
    for path in (
        'integrations/observability/metrics_source/partials/_binding_registry.html',
        'integrations/observability/alert_source/providers/alertmanager/partials/_binding_registry.html',
    ):
        content = _template(path)
        assert 'table_label.result_count(binding_registry_pagination.total_items)' in content
        assert 'flex flex-wrap items-center gap-2' in content


def test_tenant_operations_tables_have_filtered_result_counts() -> None:
    pagination_by_template = {
        '_operations_namespace_registry.html': 'operations_namespace_pagination.total_items',
        '_operations_evidence_registry.html': 'operations_evidence_pagination.total_items',
        '_operations_drift_registry.html': 'operations_drift_pagination.total_items',
        '_operations_provider_registry.html': 'operations_provider_pagination.total_items',
        '_operations_access_reconciliation_registry.html': 'operations_access_pagination.total_items',
    }
    for name, pagination in pagination_by_template.items():
        source = _template(f'kubernetes/tenant/partials/{name}')
        assert f'result_count={pagination}' in source
        assert 'table_ui.inventory_block_header(' in source


def test_special_registry_headers_share_one_result_badge() -> None:
    users = _template('access/users/partials/_directory.html')
    assert 'table_label.result_count(pagination.total_items)' in users
    assert "Matching {{ 'User'" not in users

    alerts = _template('storage/object_storage/analytics/partials/_alert_records.html')
    assert 'table_label.result_count(alert_table.pagination.total_items)' in alerts
    assert "alert_table.pagination.total_items ~ ' Alerts'" not in alerts
    assert 'table_label.status_label(alert_source.label, alert_source.tone)' in alerts
