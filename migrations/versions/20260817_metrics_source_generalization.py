"""Generalize metrics integrations behind the provider-neutral Metrics Source contract.

Revision ID: 20260817_metrics_source_v2
Revises: 20260817_metrics_routing
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '20260817_metrics_source_v2'
down_revision = '20260817_metrics_routing'
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _postgresql_constraint_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    names: set[str] = set()
    primary_key = inspector.get_pk_constraint(table_name) or {}
    if primary_key.get('name'):
        names.add(str(primary_key['name']))
    for item in inspector.get_unique_constraints(table_name):
        if item.get('name'):
            names.add(str(item['name']))
    for item in inspector.get_foreign_keys(table_name):
        if item.get('name'):
            names.add(str(item['name']))
    for item in inspector.get_check_constraints(table_name):
        if item.get('name'):
            names.add(str(item['name']))
    return names


def _rename_postgresql_constraint(table_name: str, old_name: str, new_name: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    names = _postgresql_constraint_names(table_name)
    if old_name not in names or new_name in names:
        return
    op.execute(sa.text(f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'))


def _rename_metrics_schema_objects(*, downgrade: bool = False) -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    if downgrade:
        constraint_names = (
            ('metrics_sources_pkey', 'prometheus_instances_pkey'),
            ('fk_metrics_sources_integration_instance', 'fk_prometheus_instances_integration_instance'),
            ('uq_metrics_sources_integration_instance', 'uq_prometheus_instances_integration_instance'),
        )
        sequence_old = 'metrics_sources_id_seq'
        sequence_new = 'prometheus_instances_id_seq'
    else:
        constraint_names = (
            ('prometheus_instances_pkey', 'metrics_sources_pkey'),
            ('fk_prometheus_instances_integration_instance', 'fk_metrics_sources_integration_instance'),
            ('uq_prometheus_instances_integration_instance', 'uq_metrics_sources_integration_instance'),
        )
        sequence_old = 'prometheus_instances_id_seq'
        sequence_new = 'metrics_sources_id_seq'

    for old_name, new_name in constraint_names:
        _rename_postgresql_constraint('metrics_sources', old_name, new_name)
    op.execute(sa.text(f'ALTER SEQUENCE IF EXISTS "{sequence_old}" RENAME TO "{sequence_new}"'))


def _rewrite_metrics_metadata(*, downgrade: bool = False) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            'SELECT ii.id, ii.metadata_json, ms.provider_key, ms.adapter_key, ms.query_language '
            'FROM integration_instances AS ii '
            'JOIN metrics_sources AS ms ON ms.integration_instance_id = ii.id'
        )
    ).mappings()
    for row in rows:
        metadata = row['metadata_json'] or {}
        if not isinstance(metadata, dict):
            continue
        updated = dict(metadata)
        if downgrade:
            updated['metrics_source_type'] = row['provider_key']
            updated.pop('metrics_provider_key', None)
            updated.pop('metrics_adapter_key', None)
            updated.pop('metrics_query_language', None)
        else:
            updated.pop('metrics_source_type', None)
            updated['metrics_provider_key'] = row['provider_key']
            updated['metrics_adapter_key'] = row['adapter_key']
            updated['metrics_query_language'] = row['query_language']
        bind.execute(
            sa.text('UPDATE integration_instances SET metadata_json = :metadata WHERE id = :id').bindparams(
                sa.bindparam('metadata', type_=sa.JSON())
            ),
            {'metadata': updated, 'id': row['id']},
        )


def upgrade() -> None:
    tables = _table_names()
    if 'prometheus_instances' in tables and 'metrics_sources' not in tables:
        op.rename_table('prometheus_instances', 'metrics_sources')
    _rename_metrics_schema_objects()

    columns = _column_names('metrics_sources')
    with op.batch_alter_table('metrics_sources') as batch:
        if 'source_type' in columns and 'provider_key' not in columns:
            batch.alter_column(
                'source_type',
                new_column_name='provider_key',
                existing_type=sa.String(length=20),
                type_=sa.String(length=80),
                existing_nullable=False,
            )
        if 'source_prometheus_major' in columns and 'compatibility_profile_override' not in columns:
            batch.alter_column(
                'source_prometheus_major',
                new_column_name='compatibility_profile_override',
                existing_type=sa.String(length=8),
                type_=sa.String(length=100),
                existing_nullable=True,
            )
        if 'adapter_key' not in columns:
            batch.add_column(
                sa.Column('adapter_key', sa.String(length=80), nullable=False, server_default='prometheus_http')
            )
        if 'query_language' not in columns:
            batch.add_column(sa.Column('query_language', sa.String(length=40), nullable=False, server_default='promql'))

    op.execute(
        sa.text(
            'UPDATE metrics_sources SET compatibility_profile_override = CASE '
            "WHEN compatibility_profile_override IN ('2', 'prometheus-v2-kubernetes-v1', 'prometheus-v2') "
            "THEN 'prometheus-http-v2' "
            "WHEN compatibility_profile_override IN ('3', 'prometheus-v3-kubernetes-v1', 'prometheus-v3') "
            "THEN 'prometheus-http-v3' "
            'ELSE compatibility_profile_override END'
        )
    )
    op.execute(
        sa.text(
            "UPDATE metrics_sources SET query_profile = 'prometheus-http-core-v1' "
            "WHERE query_profile = 'prometheus-core-v1'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE integration_instances SET provider_type = 'metrics_source' "
            'WHERE id IN (SELECT integration_instance_id FROM metrics_sources)'
        )
    )
    if 'integration_runtime_observations' in tables:
        op.execute(
            sa.text(
                "UPDATE integration_runtime_observations SET provider = 'metrics_source' WHERE provider = 'prometheus'"
            )
        )
    if 'job_executions' in tables:
        op.execute(
            sa.text("UPDATE job_executions SET provider_type = 'metrics_source' WHERE provider_type = 'prometheus'")
        )
    if 'notifications' in tables:
        op.execute(
            sa.text(
                "UPDATE notifications SET event_type = REPLACE(event_type, 'prometheus_', 'metrics_source_') "
                "WHERE event_type LIKE 'prometheus_%'"
            )
        )
    if 'notification_deliveries' in tables:
        op.execute(
            sa.text(
                "UPDATE notification_deliveries SET event_type = REPLACE(event_type, 'prometheus_', 'metrics_source_') "
                "WHERE event_type LIKE 'prometheus_%'"
            )
        )

    _rewrite_metrics_metadata()

    with op.batch_alter_table('metrics_sources') as batch:
        batch.alter_column('adapter_key', server_default=None)
        batch.alter_column('query_language', server_default=None)


def downgrade() -> None:
    tables = _table_names()
    if 'metrics_sources' not in tables:
        return

    _rewrite_metrics_metadata(downgrade=True)
    if 'integration_runtime_observations' in tables:
        op.execute(
            sa.text(
                "UPDATE integration_runtime_observations SET provider = 'prometheus' WHERE provider = 'metrics_source'"
            )
        )
    if 'job_executions' in tables:
        op.execute(
            sa.text("UPDATE job_executions SET provider_type = 'prometheus' WHERE provider_type = 'metrics_source'")
        )
    if 'notifications' in tables:
        op.execute(
            sa.text(
                "UPDATE notifications SET event_type = REPLACE(event_type, 'metrics_source_', 'prometheus_') "
                "WHERE event_type LIKE 'metrics_source_%'"
            )
        )
    if 'notification_deliveries' in tables:
        op.execute(
            sa.text(
                "UPDATE notification_deliveries SET event_type = REPLACE(event_type, 'metrics_source_', 'prometheus_') "
                "WHERE event_type LIKE 'metrics_source_%'"
            )
        )
    op.execute(
        sa.text(
            "UPDATE integration_instances SET provider_type = 'prometheus' "
            'WHERE id IN (SELECT integration_instance_id FROM metrics_sources)'
        )
    )
    op.execute(
        sa.text(
            "UPDATE metrics_sources SET query_profile = 'prometheus-core-v1' "
            "WHERE query_profile = 'prometheus-http-core-v1'"
        )
    )
    op.execute(
        sa.text(
            'UPDATE metrics_sources SET compatibility_profile_override = CASE '
            "WHEN compatibility_profile_override = 'prometheus-http-v2' THEN '2' "
            "WHEN compatibility_profile_override = 'prometheus-http-v3' THEN '3' "
            'ELSE compatibility_profile_override END'
        )
    )

    columns = _column_names('metrics_sources')
    with op.batch_alter_table('metrics_sources') as batch:
        if 'query_language' in columns:
            batch.drop_column('query_language')
        if 'adapter_key' in columns:
            batch.drop_column('adapter_key')
        if 'compatibility_profile_override' in columns:
            batch.alter_column(
                'compatibility_profile_override',
                new_column_name='source_prometheus_major',
                existing_type=sa.String(length=100),
                type_=sa.String(length=8),
                existing_nullable=True,
            )
        if 'provider_key' in columns:
            batch.alter_column(
                'provider_key',
                new_column_name='source_type',
                existing_type=sa.String(length=80),
                type_=sa.String(length=20),
                existing_nullable=False,
            )

    _rename_metrics_schema_objects(downgrade=True)
    op.rename_table('metrics_sources', 'prometheus_instances')
