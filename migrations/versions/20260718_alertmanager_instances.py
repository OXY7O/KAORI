"""introduce reusable Alertmanager instances and asset bindings

Revision ID: 20260718_alertmanager_instances
Revises: 20260704_0910, 20260704_add_auth_login_events,
         20260707_tls_governance, 20260717_user_regional
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '20260718_alertmanager_instances'
down_revision = (
    '20260704_0910',
    '20260704_add_auth_login_events',
    '20260707_tls_governance',
    '20260717_user_regional',
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'alertmanager_instances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('deployment_type', sa.String(length=40), nullable=False),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('auth_type', sa.String(length=30), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('password', sa.Text(), nullable=True),
        sa.Column('bearer_token', sa.Text(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=False),
        sa.Column('verify_ssl', sa.Boolean(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('detected_version', sa.String(length=64), nullable=True),
        sa.Column('compatibility_status', sa.String(length=40), nullable=True),
        sa.Column('compatibility_profile', sa.String(length=100), nullable=True),
        sa.Column('capability_profile', sa.String(length=100), nullable=True),
        sa.Column('capabilities', sa.JSON(), nullable=True),
        sa.Column('readiness_status', sa.String(length=40), nullable=True),
        sa.Column('validation_message', sa.Text(), nullable=True),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(length=50), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(
        'ix_alertmanager_instances_readiness',
        'alertmanager_instances',
        ['readiness_status'],
        unique=False,
    )
    op.create_index(
        'ix_alertmanager_instances_status',
        'alertmanager_instances',
        ['last_status'],
        unique=False,
    )

    op.create_table(
        'alertmanager_bindings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alertmanager_instance_id', sa.Integer(), nullable=False),
        sa.Column('scope_type', sa.String(length=50), nullable=False),
        sa.Column('scope_key', sa.String(length=255), nullable=False),
        sa.Column('binding_role', sa.String(length=30), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['alertmanager_instance_id'],
            ['alertmanager_instances.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'alertmanager_instance_id',
            'scope_type',
            'scope_key',
            name='uq_alertmanager_binding_instance_scope',
        ),
    )
    op.create_index(
        'ix_alertmanager_bindings_scope',
        'alertmanager_bindings',
        ['scope_type', 'scope_key', 'enabled'],
        unique=False,
    )
    op.create_index(
        'ix_alertmanager_bindings_instance_role',
        'alertmanager_bindings',
        ['alertmanager_instance_id', 'binding_role'],
        unique=False,
    )

    _backfill_cluster_scoped_configs()


def downgrade() -> None:
    op.drop_index('ix_alertmanager_bindings_instance_role', table_name='alertmanager_bindings')
    op.drop_index('ix_alertmanager_bindings_scope', table_name='alertmanager_bindings')
    op.drop_table('alertmanager_bindings')
    op.drop_index('ix_alertmanager_instances_status', table_name='alertmanager_instances')
    op.drop_index('ix_alertmanager_instances_readiness', table_name='alertmanager_instances')
    op.drop_table('alertmanager_instances')


def _backfill_cluster_scoped_configs() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    legacy = sa.Table('alertmanager_configs', metadata, autoload_with=connection)
    clusters = sa.Table('clusters', metadata, autoload_with=connection)
    instances = sa.Table('alertmanager_instances', metadata, autoload_with=connection)
    bindings = sa.Table('alertmanager_bindings', metadata, autoload_with=connection)

    statement = (
        sa.select(legacy, clusters.c.name.label('cluster_name'))
        .select_from(legacy.join(clusters, legacy.c.cluster_id == clusters.c.id))
        .where(legacy.c.endpoint.is_not(None), legacy.c.endpoint != '')
        .order_by(clusters.c.name.asc())
    )
    now = datetime.now(UTC)
    for row in connection.execute(statement).mappings():
        capabilities = (
            ['status_v2', 'alerts_v2', 'silences_v2']
            if row.get('capability_profile') == 'alert-management-v1'
            else None
        )
        insert_result = connection.execute(
            instances.insert().values(
                name=f'{row["cluster_name"]} Alertmanager',
                description=(
                    f'Migrated from the legacy cluster-scoped Alertmanager configuration for {row["cluster_name"]}.'
                ),
                deployment_type='cluster_managed',
                endpoint=row['endpoint'],
                auth_type=row['auth_type'],
                username=row['username'],
                password=row['password'],
                bearer_token=row['bearer_token'],
                timeout=row['timeout'],
                verify_ssl=row['verify_ssl'],
                enabled=True,
                detected_version=row.get('detected_version'),
                compatibility_status=row.get('compatibility_status'),
                compatibility_profile=row.get('compatibility_profile'),
                capability_profile=row.get('capability_profile'),
                capabilities=capabilities,
                readiness_status=row.get('readiness_status'),
                validation_message=row.get('validation_message'),
                last_validated_at=row.get('last_validated_at'),
                last_status=row.get('last_status'),
                last_error=row.get('last_error'),
                last_response_time_ms=row.get('last_response_time_ms'),
                last_checked_at=row.get('last_checked_at'),
                created_at=row.get('created_at') or now,
                updated_at=row.get('updated_at') or now,
            )
        )
        instance_id = insert_result.inserted_primary_key[0]
        connection.execute(
            bindings.insert().values(
                alertmanager_instance_id=instance_id,
                scope_type='kubernetes_cluster',
                scope_key=row['cluster_id'],
                binding_role='primary',
                priority=100,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
