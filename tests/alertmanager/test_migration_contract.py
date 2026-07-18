from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION_PATH = Path('migrations/versions/20260718_alertmanager_instances.py')


def test_alertmanager_migration_backfills_instances_and_bindings() -> None:
    source = MIGRATION_PATH.read_text(encoding='utf-8')
    for fragment in (
        "op.create_table(\n        'alertmanager_instances'",
        "op.create_table(\n        'alertmanager_bindings'",
        "scope_type='kubernetes_cluster'",
        "binding_role='primary'",
        "deployment_type='cluster_managed'",
        '_backfill_cluster_scoped_configs()',
    ):
        assert fragment in source


def test_alertmanager_migration_executes_backfill_against_legacy_schema() -> None:
    module = _load_migration_module()
    engine = sa.create_engine('sqlite:///:memory:')
    metadata = sa.MetaData()
    clusters = sa.Table(
        'clusters',
        metadata,
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
    )
    legacy = sa.Table(
        'alertmanager_configs',
        metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('cluster_id', sa.String(36), nullable=False),
        sa.Column('endpoint', sa.String(500), nullable=False),
        sa.Column('auth_type', sa.String(30), nullable=False),
        sa.Column('username', sa.String(255)),
        sa.Column('password', sa.Text),
        sa.Column('bearer_token', sa.Text),
        sa.Column('timeout', sa.Integer, nullable=False),
        sa.Column('verify_ssl', sa.Boolean, nullable=False),
        sa.Column('detected_version', sa.String(64)),
        sa.Column('compatibility_status', sa.String(40)),
        sa.Column('compatibility_profile', sa.String(100)),
        sa.Column('capability_profile', sa.String(100)),
        sa.Column('readiness_status', sa.String(40)),
        sa.Column('validation_message', sa.Text),
        sa.Column('last_validated_at', sa.DateTime(timezone=True)),
        sa.Column('last_status', sa.String(50)),
        sa.Column('last_error', sa.Text),
        sa.Column('last_response_time_ms', sa.Integer),
        sa.Column('last_checked_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(clusters.insert().values(id='cluster-a', name='Cluster A'))
        connection.execute(
            legacy.insert().values(
                cluster_id='cluster-a',
                endpoint='https://alertmanager.example',
                auth_type='none',
                timeout=5,
                verify_ssl=True,
                detected_version='0.33.1',
                compatibility_status='supported',
                compatibility_profile='alertmanager-api-v2-current',
                capability_profile='alert-management-v1',
                readiness_status='ready',
                last_status='connected',
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()

        instances = sa.Table('alertmanager_instances', sa.MetaData(), autoload_with=connection)
        bindings = sa.Table('alertmanager_bindings', sa.MetaData(), autoload_with=connection)
        instance = connection.execute(sa.select(instances)).mappings().one()
        binding = connection.execute(sa.select(bindings)).mappings().one()

    assert instance['name'] == 'Cluster A Alertmanager'
    assert instance['capabilities'] == ['status_v2', 'alerts_v2', 'silences_v2']
    assert binding['scope_type'] == 'kubernetes_cluster'
    assert binding['scope_key'] == 'cluster-a'
    assert binding['binding_role'] == 'primary'


def test_analytics_consumes_alertmanager_facade_not_http_client() -> None:
    source = Path('app/analytics/alerts/service.py').read_text(encoding='utf-8')
    assert 'from app.alertmanager.service import (' in source
    assert 'AlertmanagerClient' not in source
    assert 'requests.get(' not in source


def _load_migration_module():
    spec = importlib.util.spec_from_file_location('alertmanager_instance_migration', MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
