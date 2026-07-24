"""introduce standalone Prometheus runtimes and Kubernetes bindings

Revision ID: 20260718_prom_instances
Revises: 20260718_prom_runtime
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '20260718_prom_instances'
down_revision = '20260718_prom_runtime'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'prometheus_instances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(160), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('endpoint', sa.String(500), nullable=False),
        sa.Column('auth_type', sa.String(30), nullable=False, server_default='none'),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('password', sa.Text(), nullable=True),
        sa.Column('bearer_token', sa.Text(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('verify_ssl', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('version_detection_mode', sa.String(20), nullable=False, server_default='automatic'),
        sa.Column('endpoint_product', sa.String(32), nullable=True),
        sa.Column('source_prometheus_major', sa.String(8), nullable=True),
        sa.Column('detected_version', sa.String(64), nullable=True),
        sa.Column('compatibility_status', sa.String(40), nullable=True),
        sa.Column('compatibility_profile', sa.String(100), nullable=True),
        sa.Column('readiness_status', sa.String(40), nullable=True),
        sa.Column('validation_message', sa.Text(), nullable=True),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('query_profile', sa.String(100), nullable=True),
        sa.Column('query_validation_status', sa.String(40), nullable=True),
        sa.Column('query_validation_summary', sa.JSON(), nullable=True),
        sa.Column('retention_validation_summary', sa.JSON(), nullable=True),
        sa.Column('capability_profile', sa.String(100), nullable=True),
        sa.Column('capabilities', sa.JSON(), nullable=True),
        sa.Column('module_readiness', sa.JSON(), nullable=True),
        sa.Column('last_status', sa.String(40), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'prometheus_bindings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'prometheus_instance_id',
            sa.Integer(),
            sa.ForeignKey('prometheus_instances.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('scope_type', sa.String(50), nullable=False),
        sa.Column('scope_key', sa.String(255), nullable=False),
        sa.Column('binding_role', sa.String(30), nullable=False, server_default='primary'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            'prometheus_instance_id', 'scope_type', 'scope_key', name='uq_prometheus_binding_instance_scope'
        ),
    )
    op.create_index('ix_prometheus_bindings_scope', 'prometheus_bindings', ['scope_type', 'scope_key', 'enabled'])

    connection = op.get_bind()
    rows = (
        connection.execute(
            sa.text(
                """
            SELECT pc.*, c.name AS cluster_name
            FROM prometheus_configs pc
            JOIN clusters c ON c.id = pc.cluster_id
            ORDER BY pc.id
            """
            )
        )
        .mappings()
        .all()
    )
    now = datetime.now(UTC)

    prometheus_instances = sa.table(
        'prometheus_instances',
        sa.column('name', sa.String()),
        sa.column('endpoint', sa.String()),
        sa.column('auth_type', sa.String()),
        sa.column('username', sa.String()),
        sa.column('password', sa.Text()),
        sa.column('bearer_token', sa.Text()),
        sa.column('timeout', sa.Integer()),
        sa.column('verify_ssl', sa.Boolean()),
        sa.column('enabled', sa.Boolean()),
        sa.column('version_detection_mode', sa.String()),
        sa.column('endpoint_product', sa.String()),
        sa.column('source_prometheus_major', sa.String()),
        sa.column('detected_version', sa.String()),
        sa.column('compatibility_status', sa.String()),
        sa.column('compatibility_profile', sa.String()),
        sa.column('readiness_status', sa.String()),
        sa.column('validation_message', sa.Text()),
        sa.column('last_validated_at', sa.DateTime(timezone=True)),
        sa.column('query_profile', sa.String()),
        sa.column('query_validation_status', sa.String()),
        sa.column('query_validation_summary', sa.JSON()),
        sa.column('retention_validation_summary', sa.JSON()),
        sa.column('capability_profile', sa.String()),
        sa.column('capabilities', sa.JSON()),
        sa.column('module_readiness', sa.JSON()),
        sa.column('last_status', sa.String()),
        sa.column('last_error', sa.Text()),
        sa.column('last_response_time_ms', sa.Integer()),
        sa.column('last_checked_at', sa.DateTime(timezone=True)),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    prometheus_bindings = sa.table(
        'prometheus_bindings',
        sa.column('prometheus_instance_id', sa.Integer()),
        sa.column('scope_type', sa.String()),
        sa.column('scope_key', sa.String()),
        sa.column('binding_role', sa.String()),
        sa.column('priority', sa.Integer()),
        sa.column('enabled', sa.Boolean()),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )

    for row in rows:
        instance_name = f'{row["cluster_name"]} Prometheus [{row["cluster_id"]}]'
        values = {
            'name': instance_name,
            'endpoint': row['endpoint'],
            'auth_type': row.get('auth_type') or 'none',
            'username': row.get('username'),
            'password': row.get('password'),
            'bearer_token': row.get('bearer_token'),
            'timeout': row.get('timeout') or 5,
            'verify_ssl': bool(row.get('verify_ssl', True)),
            'enabled': True,
            'version_detection_mode': row.get('version_detection_mode') or 'automatic',
            'endpoint_product': row.get('endpoint_product'),
            'source_prometheus_major': row.get('source_prometheus_major'),
            'detected_version': row.get('detected_version'),
            'compatibility_status': row.get('compatibility_status'),
            'compatibility_profile': row.get('compatibility_profile'),
            'readiness_status': row.get('readiness_status'),
            'validation_message': row.get('validation_message'),
            'last_validated_at': row.get('last_validated_at'),
            'query_profile': row.get('query_profile'),
            'query_validation_status': row.get('query_validation_status'),
            'query_validation_summary': row.get('query_validation_summary'),
            'retention_validation_summary': row.get('retention_validation_summary'),
            'capability_profile': row.get('capability_profile'),
            'capabilities': row.get('capabilities'),
            'module_readiness': row.get('module_readiness'),
            'last_status': row.get('last_status'),
            'last_error': row.get('last_error'),
            'last_response_time_ms': row.get('last_response_time_ms'),
            'last_checked_at': row.get('last_checked_at'),
            'created_at': row.get('created_at') or now,
            'updated_at': row.get('updated_at') or now,
        }
        instance_id = connection.execute(
            prometheus_instances.insert().values(**values).returning(sa.column('id', sa.Integer()))
        ).scalar_one()
        connection.execute(
            prometheus_bindings.insert().values(
                prometheus_instance_id=instance_id,
                scope_type='kubernetes_cluster',
                scope_key=str(row['cluster_id']),
                binding_role='primary',
                priority=100,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_index('ix_prometheus_bindings_scope', table_name='prometheus_bindings')
    op.drop_table('prometheus_bindings')
    op.drop_table('prometheus_instances')
