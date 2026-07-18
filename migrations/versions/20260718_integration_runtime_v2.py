"""canonical integration instances, bindings, and Kubernetes connections

Revision ID: 20260718_runtime_v2
Revises: 20260718_prom_instances
"""
from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '20260718_runtime_v2'
down_revision = '20260718_prom_instances'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'integration_instances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_type', sa.String(80), nullable=False),
        sa.Column('name', sa.String(180), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('environment', sa.String(40), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('lifecycle_status', sa.String(30), nullable=False, server_default='active'),
        sa.Column('readiness_status', sa.String(40), nullable=True),
        sa.Column('health_status', sa.String(40), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('provider_type', 'name', name='uq_integration_instance_provider_name'),
    )
    op.create_index('ix_integration_instances_provider_enabled', 'integration_instances', ['provider_type', 'enabled'])
    op.create_index('ix_integration_instances_readiness', 'integration_instances', ['provider_type', 'readiness_status'])

    op.create_table(
        'integration_bindings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('integration_instance_id', sa.Integer(), sa.ForeignKey('integration_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('asset_type', sa.String(80), nullable=False),
        sa.Column('asset_key', sa.String(255), nullable=False),
        sa.Column('binding_role', sa.String(30), nullable=False, server_default='primary'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('capability_scope', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('integration_instance_id', 'asset_type', 'asset_key', 'binding_role', name='uq_integration_binding_instance_asset_role'),
    )
    op.create_index('ix_integration_bindings_asset', 'integration_bindings', ['asset_type', 'asset_key', 'enabled'])
    op.create_index('ix_integration_bindings_provider_role', 'integration_bindings', ['integration_instance_id', 'binding_role'])

    op.create_table(
        'kubernetes_connections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('integration_instance_id', sa.Integer(), sa.ForeignKey('integration_instances.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('cluster_id', sa.String(36), sa.ForeignKey('clusters.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('kubeconfig', sa.Text(), nullable=False),
        sa.Column('verify_ssl', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('allow_weak_tls', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('server', sa.String(500), nullable=True),
        sa.Column('compatibility_profile', sa.String(100), nullable=True),
        sa.Column('readiness_status', sa.String(40), nullable=True),
        sa.Column('validation_message', sa.Text(), nullable=True),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('discovery_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table('prometheus_instances') as batch:
        batch.add_column(sa.Column('integration_instance_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_prometheus_instances_integration_instance', 'integration_instances', ['integration_instance_id'], ['id'], ondelete='CASCADE')
        batch.create_unique_constraint('uq_prometheus_instances_integration_instance', ['integration_instance_id'])
    with op.batch_alter_table('alertmanager_instances') as batch:
        batch.add_column(sa.Column('integration_instance_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_alertmanager_instances_integration_instance', 'integration_instances', ['integration_instance_id'], ['id'], ondelete='CASCADE')
        batch.create_unique_constraint('uq_alertmanager_instances_integration_instance', ['integration_instance_id'])
    with op.batch_alter_table('integration_runtime_observations') as batch:
        batch.add_column(sa.Column('integration_instance_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_runtime_observation_integration_instance', 'integration_instances', ['integration_instance_id'], ['id'], ondelete='SET NULL')
        batch.create_index('ix_integration_runtime_canonical_instance', ['integration_instance_id', 'observed_at'])

    conn = op.get_bind()
    now = datetime.now(UTC)

    clusters = conn.execute(sa.text('SELECT * FROM clusters ORDER BY created_at, id')).mappings().all()
    for row in clusters:
        canonical_id = conn.execute(sa.text('''
            INSERT INTO integration_instances (
                provider_type, name, description, environment, enabled, lifecycle_status,
                readiness_status, health_status, last_error, last_checked_at, metadata_json,
                created_at, updated_at
            ) VALUES (
                'kubernetes', :name, :description, :environment, true, 'active',
                :readiness_status, :health_status, NULL, :last_checked_at, :metadata_json,
                :created_at, :updated_at
            ) RETURNING id
        '''), {
            'name': f"{row['name']} Kubernetes API",
            'description': row.get('description'),
            'environment': row.get('environment'),
            'readiness_status': row.get('kubernetes_readiness_status'),
            'health_status': row.get('status'),
            'last_checked_at': row.get('last_check'),
            'metadata_json': {'asset_type': 'kubernetes_cluster', 'asset_key': str(row['id'])},
            'created_at': row.get('created_at') or now,
            'updated_at': row.get('updated_at') or now,
        }).scalar_one()
        conn.execute(sa.text('''
            INSERT INTO kubernetes_connections (
                integration_instance_id, cluster_id, kubeconfig, verify_ssl, allow_weak_tls,
                server, compatibility_profile, readiness_status, validation_message,
                last_validated_at, discovery_summary, created_at, updated_at
            ) VALUES (
                :integration_instance_id, :cluster_id, :kubeconfig, :verify_ssl, :allow_weak_tls,
                :server, :compatibility_profile, :readiness_status, :validation_message,
                :last_validated_at, :discovery_summary, :created_at, :updated_at
            )
        '''), {
            'integration_instance_id': canonical_id,
            'cluster_id': str(row['id']),
            'kubeconfig': row.get('kubeconfig') or '',
            'verify_ssl': bool(row.get('kube_verify_ssl', True)),
            'allow_weak_tls': bool(row.get('kube_allow_weak_tls', False)),
            'server': row.get('server'),
            'compatibility_profile': row.get('kubernetes_compatibility_profile'),
            'readiness_status': row.get('kubernetes_readiness_status'),
            'validation_message': row.get('kubernetes_validation_message'),
            'last_validated_at': row.get('kubernetes_last_validated_at'),
            'discovery_summary': row.get('kubernetes_api_discovery_summary'),
            'created_at': row.get('created_at') or now,
            'updated_at': row.get('updated_at') or now,
        })
        conn.execute(sa.text('''
            INSERT INTO integration_bindings (
                integration_instance_id, asset_type, asset_key, binding_role, priority,
                enabled, capability_scope, created_at, updated_at
            ) VALUES (
                :instance_id, 'kubernetes_cluster', :asset_key, 'primary', 100,
                true, :capability_scope, :created_at, :updated_at
            )
        '''), {
            'instance_id': canonical_id,
            'asset_key': str(row['id']),
            'capability_scope': ['inventory', 'operations', 'governance', 'discovery'],
            'created_at': now,
            'updated_at': now,
        })

    providers = (
        ('prometheus', 'prometheus_instances', 'prometheus_bindings', 'prometheus_instance_id', ['metrics', 'capacity', 'utilization', 'storage', 'workload', 'forecast', 'top_consumers', 'alert_metrics']),
        ('alertmanager', 'alertmanager_instances', 'alertmanager_bindings', 'alertmanager_instance_id', ['alerts', 'silences', 'routing', 'receivers']),
    )
    for provider, instance_table, binding_table, fk_name, default_scope in providers:
        rows = conn.execute(sa.text(f'SELECT * FROM {instance_table} ORDER BY id')).mappings().all()
        for row in rows:
            canonical_id = conn.execute(sa.text('''
                INSERT INTO integration_instances (
                    provider_type, name, description, environment, enabled, lifecycle_status,
                    readiness_status, health_status, last_error, last_checked_at, metadata_json,
                    created_at, updated_at
                ) VALUES (
                    :provider_type, :name, :description, NULL, :enabled, 'active',
                    :readiness_status, :health_status, :last_error, :last_checked_at, :metadata_json,
                    :created_at, :updated_at
                ) RETURNING id
            '''), {
                'provider_type': provider,
                'name': row['name'],
                'description': row.get('description'),
                'enabled': bool(row.get('enabled', True)),
                'readiness_status': row.get('readiness_status'),
                'health_status': row.get('last_status'),
                'last_error': row.get('last_error'),
                'last_checked_at': row.get('last_checked_at'),
                'metadata_json': {'provider_record_id': row['id']},
                'created_at': row.get('created_at') or now,
                'updated_at': row.get('updated_at') or now,
            }).scalar_one()
            conn.execute(sa.text(f'UPDATE {instance_table} SET integration_instance_id = :canonical_id WHERE id = :id'), {'canonical_id': canonical_id, 'id': row['id']})
            bindings = conn.execute(sa.text(f'SELECT * FROM {binding_table} WHERE {fk_name} = :id ORDER BY priority, id'), {'id': row['id']}).mappings().all()
            for binding in bindings:
                conn.execute(sa.text('''
                    INSERT INTO integration_bindings (
                        integration_instance_id, asset_type, asset_key, binding_role, priority,
                        enabled, capability_scope, created_at, updated_at
                    ) VALUES (
                        :instance_id, :asset_type, :asset_key, :binding_role, :priority,
                        :enabled, :capability_scope, :created_at, :updated_at
                    ) ON CONFLICT DO NOTHING
                '''), {
                    'instance_id': canonical_id,
                    'asset_type': binding['scope_type'],
                    'asset_key': str(binding['scope_key']),
                    'binding_role': binding.get('binding_role') or 'primary',
                    'priority': binding.get('priority') or 100,
                    'enabled': bool(binding.get('enabled', True)),
                    'capability_scope': default_scope,
                    'created_at': binding.get('created_at') or now,
                    'updated_at': binding.get('updated_at') or now,
                })

    conn.execute(sa.text('''
        UPDATE integration_runtime_observations o
        SET integration_instance_id = p.integration_instance_id
        FROM prometheus_instances p
        WHERE o.provider = 'prometheus' AND o.instance_id = CAST(p.id AS VARCHAR)
    '''))
    conn.execute(sa.text('''
        UPDATE integration_runtime_observations o
        SET integration_instance_id = a.integration_instance_id
        FROM alertmanager_instances a
        WHERE o.provider = 'alertmanager' AND o.instance_id = CAST(a.id AS VARCHAR)
    '''))
    conn.execute(sa.text('''
        UPDATE integration_runtime_observations o
        SET integration_instance_id = k.integration_instance_id
        FROM kubernetes_connections k
        WHERE o.provider = 'kubernetes' AND o.instance_id = k.cluster_id
    '''))

    with op.batch_alter_table('prometheus_instances') as batch:
        batch.alter_column('integration_instance_id', nullable=False)
    with op.batch_alter_table('alertmanager_instances') as batch:
        batch.alter_column('integration_instance_id', nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('integration_runtime_observations') as batch:
        batch.drop_index('ix_integration_runtime_canonical_instance')
        batch.drop_constraint('fk_runtime_observation_integration_instance', type_='foreignkey')
        batch.drop_column('integration_instance_id')
    with op.batch_alter_table('alertmanager_instances') as batch:
        batch.drop_constraint('uq_alertmanager_instances_integration_instance', type_='unique')
        batch.drop_constraint('fk_alertmanager_instances_integration_instance', type_='foreignkey')
        batch.drop_column('integration_instance_id')
    with op.batch_alter_table('prometheus_instances') as batch:
        batch.drop_constraint('uq_prometheus_instances_integration_instance', type_='unique')
        batch.drop_constraint('fk_prometheus_instances_integration_instance', type_='foreignkey')
        batch.drop_column('integration_instance_id')
    op.drop_table('kubernetes_connections')
    op.drop_index('ix_integration_bindings_provider_role', table_name='integration_bindings')
    op.drop_index('ix_integration_bindings_asset', table_name='integration_bindings')
    op.drop_table('integration_bindings')
    op.drop_index('ix_integration_instances_readiness', table_name='integration_instances')
    op.drop_index('ix_integration_instances_provider_enabled', table_name='integration_instances')
    op.drop_table('integration_instances')
