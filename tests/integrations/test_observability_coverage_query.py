"""SQL Coverage must page managed assets before hydrating provider/binding rows."""

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.integrations import coverage_query
from app.integrations.binding_selectors import build_selector
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.object_storage import ObjectStorageSystem


def test_coverage_sql_pagination_preserves_counts_filter_and_lifecycle(monkeypatch) -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.__table__.create(engine)
    IntegrationBinding.__table__.create(engine)
    ObjectStorageSystem.__table__.create(engine)

    with Session(engine) as session:
        monkeypatch.setattr(coverage_query, 'db', SimpleNamespace(session=session))
        monkeypatch.setattr(
            coverage_query,
            'registered_consumer_asset_definitions',
            lambda: (SimpleNamespace(
                asset_type='object_storage_system', model=ObjectStorageSystem,
                label='Object Storage', integration_type=None,
            ),),
        )
        session.add(IntegrationInstance(
            id=1, name='Prometheus', integration_type='metrics_source',
            provider_key='prometheus', adapter_key='prometheus_http',
            readiness_status='ready', enabled=True, lifecycle_status='active',
        ))
        for number in range(1, 8):
            session.add(ObjectStorageSystem(
                id=f'asset-{number}', name=f'Scope {number}', environment='production',
            ))
        session.add(IntegrationBinding(
            integration_instance_id=1, asset_type='object_storage_system',
            asset_key='asset-1', enabled=True, validation_status='ready',
            binding_role='primary', priority=10,
            selector_json=build_selector(label='service', value='minio-1'),
        ))
        session.flush()

        first = coverage_query.paged_coverage_scopes('metrics_source', page=1, per_page=5)
        assert first['stats'] == {'total': 7, 'ready': 1, 'attention': 0, 'uncovered': 6}
        assert first['pagination']['total_items'] == 7
        assert len(first['rows']) == 5
        assert first['rows'][0]['coverage_status'] == 'ready'
        assert first['rows'][0]['asset_key'] == 'asset-1'
        last = coverage_query.paged_coverage_scopes('metrics_source', page=2, per_page=5)
        assert last['pagination']['total_items'] == 7
        assert len(last['rows']) == 2

        ready = coverage_query.paged_coverage_scopes(
            'metrics_source', page=1, per_page=5, status='ready',
        )
        assert ready['pagination']['total_items'] == 1
        assert ready['rows'][0]['asset_key'] == 'asset-1'
        search = coverage_query.paged_coverage_scopes(
            'metrics_source', page=1, per_page=5, query='Scope 7', environment='Production',
        )
        assert search['pagination']['total_items'] == 1
        assert search['rows'][0]['asset_key'] == 'asset-7'

        source = session.get(IntegrationInstance, 1)
        source.enabled = False
        session.flush()
        changed = coverage_query.paged_coverage_scopes('metrics_source', page=1, per_page=5)
        assert changed['stats']['ready'] == 0
        assert changed['stats']['attention'] == 1
        blocked = coverage_query.paged_coverage_scopes(
            'metrics_source', page=1, per_page=5, status='blocked',
        )
        assert blocked['pagination']['total_items'] == 1
        assert blocked['rows'][0]['asset_key'] == 'asset-1'
    engine.dispose()


def test_coverage_rejects_unvalidated_bindings_even_when_provider_ready(monkeypatch) -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.__table__.create(engine)
    IntegrationBinding.__table__.create(engine)
    ObjectStorageSystem.__table__.create(engine)
    with Session(engine) as session:
        monkeypatch.setattr(coverage_query, 'db', SimpleNamespace(session=session))
        monkeypatch.setattr(
            coverage_query,
            'registered_consumer_asset_definitions',
            lambda: (SimpleNamespace(
                asset_type='object_storage_system', model=ObjectStorageSystem,
                label='Object Storage', integration_type=None,
            ),),
        )
        session.add(IntegrationInstance(
            id=2, name='Alerts', integration_type='alert_source',
            provider_key='alertmanager', adapter_key='alertmanager_api_v2',
            readiness_status='ready', enabled=True, lifecycle_status='active',
        ))
        session.add(ObjectStorageSystem(id='asset-9', name='Scope 9', environment='testing'))
        session.add(IntegrationBinding(
            integration_instance_id=2, asset_type='object_storage_system',
            asset_key='asset-9', enabled=True, validation_status=None,
            binding_role='primary',
        ))
        session.flush()
        result = coverage_query.paged_coverage_scopes('alert_source', page=1, per_page=5)
        assert result['stats']['ready'] == 0
        assert result['rows'][0]['coverage_status'] == 'validation_required'
    engine.dispose()
