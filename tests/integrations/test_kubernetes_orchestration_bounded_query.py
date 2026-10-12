"""SQL-first Kubernetes front page never hydrates a fleet before pagination."""

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.integrations.orchestration.container_orchestrator import fleet_query


def test_kubernetes_fleet_projection_is_single_row_per_connection_and_lifecycle_aware():
    fleet = fleet_query.fleet_statement()
    compiled = str(select(fleet).compile(dialect=postgresql.dialect()))
    assert 'kubernetes_connections' in compiled
    assert 'integration_bindings' in compiled
    assert 'lifecycle_status' in compiled
    assert 'metrics_sources' in compiled
    assert 'alertmanager_instances' in compiled
    assert 'LIMIT' in compiled  # one preferred binding per source type


def test_kubernetes_frontpage_pagination_is_sql_scoped():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    front = (root / 'app/integrations/orchestration/container_orchestrator/frontpage.py').read_text()
    coverage = (root / 'app/integrations/coverage.py').read_text()
    body = front.split('def build_kubernetes_page(', 1)[1]
    assert 'page_connection_ids(' in body
    assert '_hydrate_connection_rows(' in body
    assert body.index('page_connection_ids(') < body.index('_hydrate_connection_rows(')
    assert '_load_rows()' not in body
    assert 'fleet_stats(fleet)' in body
    assert 'model.integration_instance_id.in_(canonical_ids)' in coverage
    assert 'scope_keys=[str(connection.cluster_id) for connection in connections]' in front


def test_kubernetes_page_sizes_use_existing_pagination_window():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / 'app/integrations/orchestration/container_orchestrator/fleet_query.py'
    ).read_text()
    assert 'build_pagination_window(' in source
    assert '.offset(window.offset).limit(window.per_page)' in source
