"""Integrations Overview SQL-first read-model regression contracts."""

from pathlib import Path

from app.common.pagination import build_pagination_window
from app.integrations.overview_runtime_sql import runtime_page, runtime_stats

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_global_overview_aggregates_portfolio_without_entity_fleet_hydration():
    source = read('app/integrations/overview_workspace.py')
    aggregation = read('app/integrations/overview_sql.py')
    assert 'provider_counts, stats = overview_portfolio_counts()' in source
    assert 'provider_counts_override=provider_counts' in source
    assert 'kubernetes_query.order_by(' not in source
    assert 'metrics_query.order_by(' not in source
    assert 'load_extension_integration_instances()' not in source
    assert '.group_by(identity.integration_type)' in aggregation
    assert "identity.lifecycle_status == 'active'" in aggregation


def test_runtime_filters_and_pagination_are_sql_first():
    workspace = read('app/integrations/overview_workspace.py')
    sql = read('app/integrations/overview_runtime_sql.py')
    builder = workspace.split('def build_integrations_overview(', 1)[1]
    assert builder.index('selected = (') < builder.index('specs, pagination = runtime_page(')
    assert builder.index('specs, pagination = runtime_page(') < builder.index('_visible_runtime_rows(specs)')
    assert '.offset(window.offset).limit(window.per_page)' in sql
    assert 'lookup.observed_at.desc()' in sql
    assert 'lookup.instance_id == cast(candidates.c.provider_record_id, String)' in sql
    assert 'select(IntegrationRuntimeObservation).where(' in workspace
    assert 'IntegrationRuntimeObservation.id.in_(observation_ids)' in workspace
    assert 'select(model).where(model.id.in_(ids))' in workspace


def test_registered_providers_expose_bounded_record_model():
    paths = {
        'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/__init__.py': 'record_model=KubernetesConnection',
        'app/integrations/observability/metrics_source/__init__.py': 'record_model=MetricsSource',
        'app/integrations/observability/alert_source/providers/alertmanager/__init__.py': 'record_model=AlertmanagerInstance',
        'app/integrations/storage/object_storage/providers/minio/__init__.py': 'record_model=MinioInstance',
        'app/integrations/registry/providers/harbor/__init__.py': 'record_model=HarborInstance',
    }
    for path, assertion in paths.items():
        assert assertion in read(path), path


def test_runtime_empty_page_uses_canonical_pagination_contract():
    rows, page = runtime_page(None, page=16, per_page=800)
    assert rows == []
    assert (page['page'], page['per_page'], page['total_items']) == (1, 5, 0)
    assert (page['start_item'], page['end_item']) == (0, 0)
    assert runtime_stats(None)['total'] == 0
    assert build_pagination_window(total_items=0).page == 1


def test_sql_reuses_existing_provider_neutral_runtime_contract():
    sql = read('app/integrations/overview_runtime_sql.py')
    assert 'registry.implementations_for_type(module.integration_type)' in sql
    assert 'canonical.provider_key == implementation.provider_key' in sql
    assert "fleet.c.health_status == 'unhealthy', 0" in sql
    assert 'func.coalesce(observation.health_status' in sql
