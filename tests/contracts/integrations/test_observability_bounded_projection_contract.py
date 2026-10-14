"""Shared Observability fleet/detail reads remain SQL bounded and source-owned."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_coverage_sql_before_projection_and_batch_provider_loader() -> None:
    coverage = source('app/integrations/coverage.py')
    query = source('app/integrations/coverage_query.py')
    body = coverage.split('def build_provider_coverage(', 1)[1].split('def build_binding_workspace(', 1)[0]
    assert 'paged_coverage_scopes(' in body
    assert 'IntegrationBinding.id.in_(binding_ids)' in body
    assert 'for scoped in snapshot[' in body
    assert 'for scope in _managed_asset_scopes()' not in body
    assert '_provider_binding_indexes(integration_type)' not in body
    assert 'build_pagination_window(' in query
    assert re.search(r'\.offset\(window\.offset\)\s*\.limit\(window\.per_page\)', query)
    assert 'func.sum(case(' in query

    loader = coverage.split('def _instances(', 1)[1].split('def _coverage_status(', 1)[0]
    assert 'implementation.record_model' in loader
    assert 'model.query.join(model.integration_instance)' in loader
    assert 'identities = IntegrationInstance.query' in loader  # backwards-compatible fallback
    registry = source('app/integrations/kernel/registry.py')
    assert 'record_model: type[Any] | None = None' in registry
    for filename in (
        'app/integrations/observability/metrics_source/__init__.py',
        'app/integrations/observability/alert_source/providers/alertmanager/__init__.py',
    ):
        assert 'record_model=' in source(filename)


def test_provider_details_resolve_only_visible_binding_page() -> None:
    for path in (
        'app/integrations/observability/metrics_source/application/presentation.py',
        'app/integrations/observability/alert_source/providers/alertmanager/application/presentation.py',
    ):
        presentation = source(path)
        detail = presentation.split('def build_instance_context(', 1)[1].split(
            'def _instance_row(' if 'alertmanager' in path else 'def build_runtime_history_context(', 1
        )[0]
        assert 'paginate_query(' in detail
        assert "'binding_total': binding_total" in detail
        assert "'validated_binding_total':" in detail
        assert "'operational_binding_total':" in detail
        assert "'resolution_scope_total':" in detail
        assert "'binding_registry_rows': binding_registry_rows" in detail
    alert = source('app/integrations/observability/alert_source/providers/alertmanager/application/presentation.py')
    index = alert.split('def build_inventory_context(', 1)[1].split('def _alertmanager_request_target(', 1)[0]
    assert 'page_instances, pagination = paginate_query(' in index
    assert 'binding_summary' in index
    assert 'instances = list_instances()' not in index

    for path in (
        'app/templates/integrations/observability/metrics_source/partials/_detail_scope.html',
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html',
    ):
        template = source(path)
        assert 'binding_total' in template
        assert 'validated_binding_total' in template
        assert 'operational_binding_total' in template
        assert 'visible binding page' in template.lower()
