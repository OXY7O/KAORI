"""Normalize integration identity into integration type, provider, and adapter layers.

Revision ID: 20260817_integration_type_v1
Revises: 20260817_metrics_source_v2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260817_integration_type_v1'
down_revision = '20260817_metrics_source_v2'
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    return {str(item['name']) for item in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {str(item['name']) for item in sa.inspect(op.get_bind()).get_indexes(table_name) if item.get('name')}


def _unique_constraints(table_name: str) -> set[str]:
    return {
        str(item['name']) for item in sa.inspect(op.get_bind()).get_unique_constraints(table_name) if item.get('name')
    }


def _rewrite_identity_metadata() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text('SELECT id, metadata_json FROM integration_instances')).mappings()
    for row in rows:
        metadata = row['metadata_json'] or {}
        if not isinstance(metadata, dict):
            continue
        updated = dict(metadata)
        updated.pop('metrics_provider_key', None)
        updated.pop('metrics_adapter_key', None)
        bind.execute(
            sa.text('UPDATE integration_instances SET metadata_json = :metadata WHERE id = :id').bindparams(
                sa.bindparam('metadata', type_=sa.JSON())
            ),
            {'metadata': updated, 'id': row['id']},
        )


def upgrade() -> None:
    tables = _tables()

    columns = _columns('integration_instances')
    with op.batch_alter_table('integration_instances') as batch:
        if 'provider_type' in columns and 'integration_type' not in columns:
            batch.alter_column(
                'provider_type',
                new_column_name='integration_type',
                existing_type=sa.String(length=80),
                existing_nullable=False,
            )
        if 'provider_key' not in columns:
            batch.add_column(sa.Column('provider_key', sa.String(length=80), nullable=True))
        if 'adapter_key' not in columns:
            batch.add_column(sa.Column('adapter_key', sa.String(length=80), nullable=True))

    # Metrics Source is already provider-neutral from the prior migration. Move its
    # implementation identity to the canonical integration row before dropping the
    # duplicate child-table fields.
    if 'metrics_sources' in tables and {'provider_key', 'adapter_key'}.issubset(_columns('metrics_sources')):
        op.execute(
            sa.text(
                'UPDATE integration_instances SET '
                'provider_key = (SELECT ms.provider_key FROM metrics_sources ms '
                'WHERE ms.integration_instance_id = integration_instances.id), '
                'adapter_key = (SELECT ms.adapter_key FROM metrics_sources ms '
                'WHERE ms.integration_instance_id = integration_instances.id) '
                "WHERE integration_type = 'metrics_source'"
            )
        )

    op.execute(
        sa.text(
            "UPDATE integration_instances SET provider_key = 'kubernetes', adapter_key = 'kubernetes_api', "
            "integration_type = 'container_orchestrator' WHERE integration_type = 'kubernetes'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE integration_instances SET provider_key = 'alertmanager', adapter_key = 'alertmanager_api_v2', "
            "integration_type = 'alert_source' WHERE integration_type = 'alertmanager'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE integration_instances SET provider_key = 'minio', adapter_key = 's3', "
            "integration_type = 'object_storage' WHERE integration_type = 'minio'"
        )
    )
    # Extension rows remain valid without a core refactor. Their prior registry key
    # becomes the provider key; adapter implementation must be declared by the
    # extension before runtime operations are enabled.
    op.execute(
        sa.text(
            'UPDATE integration_instances SET provider_key = integration_type '
            "WHERE provider_key IS NULL OR provider_key = ''"
        )
    )
    op.execute(
        sa.text(
            "UPDATE integration_instances SET adapter_key = 'extension' WHERE adapter_key IS NULL OR adapter_key = ''"
        )
    )

    with op.batch_alter_table('integration_instances') as batch:
        batch.alter_column('provider_key', existing_type=sa.String(length=80), nullable=False)
        batch.alter_column('adapter_key', existing_type=sa.String(length=80), nullable=False)

    indexes = _indexes('integration_instances')
    if 'ix_integration_instances_provider_enabled' in indexes:
        op.drop_index('ix_integration_instances_provider_enabled', table_name='integration_instances')
    if 'ix_integration_instances_readiness' in indexes:
        op.drop_index('ix_integration_instances_readiness', table_name='integration_instances')
    constraints = _unique_constraints('integration_instances')
    if 'uq_integration_instance_provider_name' in constraints:
        with op.batch_alter_table('integration_instances') as batch:
            batch.drop_constraint('uq_integration_instance_provider_name', type_='unique')
    op.create_index(
        'ix_integration_instances_type_enabled',
        'integration_instances',
        ['integration_type', 'enabled'],
    )
    op.create_index(
        'ix_integration_instances_readiness',
        'integration_instances',
        ['integration_type', 'readiness_status'],
    )
    with op.batch_alter_table('integration_instances') as batch:
        batch.create_unique_constraint('uq_integration_instance_type_name', ['integration_type', 'name'])

    if 'metrics_sources' in tables:
        metrics_columns = _columns('metrics_sources')
        with op.batch_alter_table('metrics_sources') as batch:
            if 'provider_key' in metrics_columns:
                batch.drop_column('provider_key')
            if 'adapter_key' in metrics_columns:
                batch.drop_column('adapter_key')

    if 'integration_runtime_observations' in tables:
        runtime_columns = _columns('integration_runtime_observations')
        with op.batch_alter_table('integration_runtime_observations') as batch:
            if 'provider' in runtime_columns and 'integration_type' not in runtime_columns:
                batch.alter_column(
                    'provider',
                    new_column_name='integration_type',
                    existing_type=sa.String(length=80),
                    existing_nullable=False,
                )
            if 'provider_key' not in runtime_columns:
                batch.add_column(sa.Column('provider_key', sa.String(length=80), nullable=True))
            if 'adapter_key' not in runtime_columns:
                batch.add_column(sa.Column('adapter_key', sa.String(length=80), nullable=True))
        op.execute(
            sa.text(
                'UPDATE integration_runtime_observations SET '
                'provider_key = (SELECT ii.provider_key FROM integration_instances ii '
                'WHERE ii.id = integration_runtime_observations.integration_instance_id), '
                'adapter_key = (SELECT ii.adapter_key FROM integration_instances ii '
                'WHERE ii.id = integration_runtime_observations.integration_instance_id), '
                'integration_type = COALESCE((SELECT ii.integration_type FROM integration_instances ii '
                'WHERE ii.id = integration_runtime_observations.integration_instance_id), integration_type) '
                'WHERE integration_instance_id IS NOT NULL'
            )
        )
        op.execute(
            sa.text(
                'UPDATE integration_runtime_observations SET integration_type = CASE integration_type '
                "WHEN 'kubernetes' THEN 'container_orchestrator' "
                "WHEN 'alertmanager' THEN 'alert_source' "
                "WHEN 'minio' THEN 'object_storage' ELSE integration_type END"
            )
        )
        op.execute(
            sa.text(
                'UPDATE integration_runtime_observations SET provider_key = CASE integration_type '
                "WHEN 'container_orchestrator' THEN 'kubernetes' "
                "WHEN 'metrics_source' THEN COALESCE(provider_key, 'prometheus') "
                "WHEN 'alert_source' THEN 'alertmanager' "
                "WHEN 'object_storage' THEN 'minio' ELSE integration_type END "
                "WHERE provider_key IS NULL OR provider_key = ''"
            )
        )
        op.execute(
            sa.text(
                'UPDATE integration_runtime_observations SET adapter_key = CASE integration_type '
                "WHEN 'container_orchestrator' THEN 'kubernetes_api' "
                "WHEN 'metrics_source' THEN 'prometheus_http' "
                "WHEN 'alert_source' THEN 'alertmanager_api_v2' "
                "WHEN 'object_storage' THEN 's3' ELSE 'extension' END "
                "WHERE adapter_key IS NULL OR adapter_key = ''"
            )
        )
        with op.batch_alter_table('integration_runtime_observations') as batch:
            batch.alter_column('provider_key', existing_type=sa.String(length=80), nullable=False)
            batch.alter_column('adapter_key', existing_type=sa.String(length=80), nullable=False)
        runtime_indexes = _indexes('integration_runtime_observations')
        if 'ix_integration_runtime_provider_instance' in runtime_indexes:
            op.drop_index('ix_integration_runtime_provider_instance', table_name='integration_runtime_observations')
        if 'ix_integration_runtime_health' in runtime_indexes:
            op.drop_index('ix_integration_runtime_health', table_name='integration_runtime_observations')
        op.create_index(
            'ix_integration_runtime_type_instance',
            'integration_runtime_observations',
            ['integration_type', 'instance_id', 'observed_at'],
        )
        op.create_index(
            'ix_integration_runtime_health',
            'integration_runtime_observations',
            ['integration_type', 'health_status', 'observed_at'],
        )

    if 'job_executions' in tables:
        job_columns = _columns('job_executions')
        with op.batch_alter_table('job_executions') as batch:
            if 'provider_type' in job_columns and 'integration_type' not in job_columns:
                batch.alter_column(
                    'provider_type',
                    new_column_name='integration_type',
                    existing_type=sa.String(length=80),
                    existing_nullable=True,
                )
            if 'integration_instance_id' not in job_columns:
                batch.add_column(sa.Column('integration_instance_id', sa.Integer(), nullable=True))
        op.execute(
            sa.text(
                'UPDATE job_executions SET integration_type = CASE integration_type '
                "WHEN 'kubernetes' THEN 'container_orchestrator' "
                "WHEN 'alertmanager' THEN 'alert_source' "
                "WHEN 'minio' THEN 'object_storage' ELSE integration_type END"
            )
        )
        if 'provider_instance_id' in job_columns:
            op.execute(
                sa.text(
                    'UPDATE job_executions SET integration_instance_id = CASE integration_type '
                    "WHEN 'container_orchestrator' THEN (SELECT kc.integration_instance_id FROM kubernetes_connections kc WHERE kc.id = job_executions.provider_instance_id) "
                    "WHEN 'metrics_source' THEN (SELECT ms.integration_instance_id FROM metrics_sources ms WHERE ms.id = job_executions.provider_instance_id) "
                    "WHEN 'alert_source' THEN (SELECT am.integration_instance_id FROM alertmanager_instances am WHERE am.id = job_executions.provider_instance_id) "
                    "WHEN 'object_storage' THEN (SELECT mi.integration_instance_id FROM minio_instances mi WHERE mi.id = job_executions.provider_instance_id) "
                    'ELSE NULL END '
                    'WHERE provider_instance_id IS NOT NULL'
                )
            )
            with op.batch_alter_table('job_executions') as batch:
                batch.drop_column('provider_instance_id')
        with op.batch_alter_table('job_executions') as batch:
            batch.create_foreign_key(
                'fk_job_executions_integration_instance',
                'integration_instances',
                ['integration_instance_id'],
                ['id'],
                ondelete='SET NULL',
            )

    _rewrite_identity_metadata()


def downgrade() -> None:
    tables = _tables()

    if 'job_executions' in tables and 'integration_type' in _columns('job_executions'):
        with op.batch_alter_table('job_executions') as batch:
            if 'provider_instance_id' not in _columns('job_executions'):
                batch.add_column(sa.Column('provider_instance_id', sa.Integer(), nullable=True))
        op.execute(
            sa.text(
                'UPDATE job_executions SET provider_instance_id = CASE integration_type '
                "WHEN 'container_orchestrator' THEN (SELECT kc.id FROM kubernetes_connections kc WHERE kc.integration_instance_id = job_executions.integration_instance_id) "
                "WHEN 'metrics_source' THEN (SELECT ms.id FROM metrics_sources ms WHERE ms.integration_instance_id = job_executions.integration_instance_id) "
                "WHEN 'alert_source' THEN (SELECT am.id FROM alertmanager_instances am WHERE am.integration_instance_id = job_executions.integration_instance_id) "
                "WHEN 'object_storage' THEN (SELECT mi.id FROM minio_instances mi WHERE mi.integration_instance_id = job_executions.integration_instance_id) "
                'ELSE NULL END '
                'WHERE integration_instance_id IS NOT NULL'
            )
        )
        op.execute(
            sa.text(
                'UPDATE job_executions SET integration_type = CASE integration_type '
                "WHEN 'container_orchestrator' THEN 'kubernetes' "
                "WHEN 'alert_source' THEN 'alertmanager' "
                "WHEN 'object_storage' THEN 'minio' ELSE integration_type END"
            )
        )
        with op.batch_alter_table('job_executions') as batch:
            batch.drop_constraint('fk_job_executions_integration_instance', type_='foreignkey')
            batch.drop_column('integration_instance_id')
            batch.alter_column(
                'integration_type',
                new_column_name='provider_type',
                existing_type=sa.String(length=80),
                existing_nullable=True,
            )

    if 'integration_runtime_observations' in tables:
        runtime_indexes = _indexes('integration_runtime_observations')
        if 'ix_integration_runtime_type_instance' in runtime_indexes:
            op.drop_index('ix_integration_runtime_type_instance', table_name='integration_runtime_observations')
        if 'ix_integration_runtime_health' in runtime_indexes:
            op.drop_index('ix_integration_runtime_health', table_name='integration_runtime_observations')
        op.execute(
            sa.text(
                'UPDATE integration_runtime_observations SET integration_type = CASE integration_type '
                "WHEN 'container_orchestrator' THEN 'kubernetes' "
                "WHEN 'alert_source' THEN 'alertmanager' "
                "WHEN 'object_storage' THEN 'minio' ELSE integration_type END"
            )
        )
        with op.batch_alter_table('integration_runtime_observations') as batch:
            if 'provider_key' in _columns('integration_runtime_observations'):
                batch.drop_column('provider_key')
            if 'adapter_key' in _columns('integration_runtime_observations'):
                batch.drop_column('adapter_key')
            batch.alter_column(
                'integration_type',
                new_column_name='provider',
                existing_type=sa.String(length=80),
                existing_nullable=False,
            )
        op.create_index(
            'ix_integration_runtime_provider_instance',
            'integration_runtime_observations',
            ['provider', 'instance_id', 'observed_at'],
        )
        op.create_index(
            'ix_integration_runtime_health',
            'integration_runtime_observations',
            ['provider', 'health_status', 'observed_at'],
        )

    if 'metrics_sources' in tables:
        with op.batch_alter_table('metrics_sources') as batch:
            if 'provider_key' not in _columns('metrics_sources'):
                batch.add_column(sa.Column('provider_key', sa.String(length=80), nullable=True))
            if 'adapter_key' not in _columns('metrics_sources'):
                batch.add_column(sa.Column('adapter_key', sa.String(length=80), nullable=True))
        op.execute(
            sa.text(
                'UPDATE metrics_sources SET '
                'provider_key = (SELECT ii.provider_key FROM integration_instances ii '
                'WHERE ii.id = metrics_sources.integration_instance_id), '
                'adapter_key = (SELECT ii.adapter_key FROM integration_instances ii '
                'WHERE ii.id = metrics_sources.integration_instance_id)'
            )
        )
        with op.batch_alter_table('metrics_sources') as batch:
            batch.alter_column('provider_key', existing_type=sa.String(length=80), nullable=False)
            batch.alter_column('adapter_key', existing_type=sa.String(length=80), nullable=False)

    indexes = _indexes('integration_instances')
    if 'ix_integration_instances_type_enabled' in indexes:
        op.drop_index('ix_integration_instances_type_enabled', table_name='integration_instances')
    if 'ix_integration_instances_readiness' in indexes:
        op.drop_index('ix_integration_instances_readiness', table_name='integration_instances')
    constraints = _unique_constraints('integration_instances')
    if 'uq_integration_instance_type_name' in constraints:
        with op.batch_alter_table('integration_instances') as batch:
            batch.drop_constraint('uq_integration_instance_type_name', type_='unique')

    op.execute(
        sa.text(
            'UPDATE integration_instances SET integration_type = CASE integration_type '
            "WHEN 'container_orchestrator' THEN 'kubernetes' "
            "WHEN 'alert_source' THEN 'alertmanager' "
            "WHEN 'object_storage' THEN 'minio' ELSE integration_type END"
        )
    )
    with op.batch_alter_table('integration_instances') as batch:
        batch.drop_column('provider_key')
        batch.drop_column('adapter_key')
        batch.alter_column(
            'integration_type',
            new_column_name='provider_type',
            existing_type=sa.String(length=80),
            existing_nullable=False,
        )
    op.create_index(
        'ix_integration_instances_provider_enabled',
        'integration_instances',
        ['provider_type', 'enabled'],
    )
    op.create_index(
        'ix_integration_instances_readiness',
        'integration_instances',
        ['provider_type', 'readiness_status'],
    )
    with op.batch_alter_table('integration_instances') as batch:
        batch.create_unique_constraint('uq_integration_instance_provider_name', ['provider_type', 'name'])
