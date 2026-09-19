"""add multi-domain data lifecycle policies

Revision ID: 20260721_data_lifecycle
Revises: 20260720_job_execution
Create Date: 2026-07-21 05:30:00
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = '20260721_data_lifecycle'
down_revision = '20260720_job_execution'
branch_labels = None
depends_on = None


PERMISSIONS = (
    (
        'settings.view_data_lifecycle',
        'settings',
        'view_data_lifecycle',
        'View retention policies, archive storage posture, and lifecycle execution history.',
    ),
    (
        'settings.export_data_lifecycle',
        'settings',
        'export_data_lifecycle',
        'Download verified data lifecycle archives and manifests.',
    ),
    (
        'settings.manage_data_lifecycle',
        'settings',
        'manage_data_lifecycle',
        'Configure policies and run, verify, or maintain lifecycle archives across data domains.',
    ),
)


def upgrade() -> None:
    op.create_table(
        'data_lifecycle_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=80), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('hot_retention_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('archive_retention_days', sa.Integer(), nullable=False, server_default='365'),
        sa.Column('batch_size', sa.Integer(), nullable=False, server_default='5000'),
        sa.Column('operation_mode', sa.String(length=32), nullable=False, server_default='archive_and_cleanup'),
        sa.Column('schedule_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('schedule_hour', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('schedule_minute', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('protect_unreviewed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('protected_max_days', sa.Integer(), nullable=True),
        sa.Column('settings_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain'),
    )
    op.create_index('ix_data_lifecycle_policies_domain', 'data_lifecycle_policies', ['domain'])
    op.create_index('ix_data_lifecycle_policies_enabled_domain', 'data_lifecycle_policies', ['enabled', 'domain'])
    op.create_index(
        'ix_job_executions_retention_boundary',
        'job_executions',
        ['status', 'workload_class', 'completed_at'],
    )

    now = datetime.now(UTC)
    policy_table = sa.table(
        'data_lifecycle_policies',
        sa.column('domain', sa.String),
        sa.column('enabled', sa.Boolean),
        sa.column('hot_retention_days', sa.Integer),
        sa.column('archive_retention_days', sa.Integer),
        sa.column('batch_size', sa.Integer),
        sa.column('operation_mode', sa.String),
        sa.column('schedule_enabled', sa.Boolean),
        sa.column('schedule_hour', sa.Integer),
        sa.column('schedule_minute', sa.Integer),
        sa.column('protect_unreviewed', sa.Boolean),
        sa.column('protected_max_days', sa.Integer),
        sa.column('settings_json', sa.JSON),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        policy_table,
        [
            {
                'domain': 'operational_activity',
                'enabled': True,
                'hot_retention_days': 90,
                'archive_retention_days': 365,
                'batch_size': 5000,
                'operation_mode': 'archive_and_cleanup',
                'schedule_enabled': True,
                'schedule_hour': 2,
                'schedule_minute': 15,
                'protect_unreviewed': False,
                'protected_max_days': 180,
                'settings_json': {},
                'created_at': now,
                'updated_at': now,
            },
            {
                'domain': 'job_execution',
                'enabled': True,
                'hot_retention_days': 90,
                'archive_retention_days': 365,
                'batch_size': 2500,
                'operation_mode': 'archive_and_cleanup',
                'schedule_enabled': True,
                'schedule_hour': 3,
                'schedule_minute': 0,
                'protect_unreviewed': False,
                'protected_max_days': None,
                'settings_json': {
                    'workload_retention_days': {
                        'runtime': 30,
                        'validation': 30,
                        'analytics': 90,
                        'forecasting': 180,
                        'standard': 90,
                    },
                    'failed_retention_days': 90,
                    'preserve_result_references': True,
                },
                'created_at': now,
                'updated_at': now,
            },
        ],
    )

    bind = op.get_bind()
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.Integer),
        sa.column('key', sa.String),
        sa.column('module', sa.String),
        sa.column('action', sa.String),
        sa.column('description', sa.Text),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    for key, module, action, description in PERMISSIONS:
        exists = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == key)).scalar()
        if exists is None:
            bind.execute(
                permissions.insert().values(
                    key=key, module=module, action=action, description=description, created_at=now
                )
            )

    roles = sa.table('roles', sa.column('id', sa.Integer), sa.column('name', sa.String))
    role_permissions = sa.table(
        'role_permissions',
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    permission_ids = {
        row.key: row.id
        for row in bind.execute(
            sa.select(permissions.c.id, permissions.c.key).where(
                permissions.c.key.in_([item[0] for item in PERMISSIONS])
            )
        )
    }
    for role_name in ('admin',):
        role_id = bind.execute(sa.select(roles.c.id).where(roles.c.name == role_name)).scalar()
        if role_id:
            for permission_id in permission_ids.values():
                exists = bind.execute(
                    sa.select(role_permissions.c.role_id).where(
                        role_permissions.c.role_id == role_id,
                        role_permissions.c.permission_id == permission_id,
                    )
                ).scalar()
                if exists is None:
                    bind.execute(
                        role_permissions.insert().values(role_id=role_id, permission_id=permission_id, created_at=now)
                    )
    # Preserve access for custom roles that already owned the legacy Activity Audit
    # retention permissions. Data Lifecycle is broader, but these mappings keep
    # the existing least-privilege intent while operators review custom roles.
    legacy_permission_mappings = {
        'settings.view_operational_activity': ('settings.view_data_lifecycle',),
        'settings.export_operational_activity': (
            'settings.view_data_lifecycle',
            'settings.export_data_lifecycle',
        ),
        'settings.manage_operational_activity_retention': (
            'settings.view_data_lifecycle',
            'settings.manage_data_lifecycle',
        ),
    }
    lifecycle_keys = {key for values in legacy_permission_mappings.values() for key in values}
    all_permission_rows = {
        row.key: row.id
        for row in bind.execute(
            sa.select(permissions.c.id, permissions.c.key).where(
                permissions.c.key.in_(list(legacy_permission_mappings) + list(lifecycle_keys))
            )
        )
    }
    for legacy_key, mapped_keys in legacy_permission_mappings.items():
        legacy_id = all_permission_rows.get(legacy_key)
        if not legacy_id:
            continue
        role_ids = [
            row.role_id
            for row in bind.execute(
                sa.select(role_permissions.c.role_id).where(role_permissions.c.permission_id == legacy_id)
            )
        ]
        for lifecycle_key in mapped_keys:
            lifecycle_id = all_permission_rows.get(lifecycle_key)
            if not lifecycle_id:
                continue
            for role_id in role_ids:
                exists = bind.execute(
                    sa.select(role_permissions.c.role_id).where(
                        role_permissions.c.role_id == role_id,
                        role_permissions.c.permission_id == lifecycle_id,
                    )
                ).scalar()
                if exists is None:
                    bind.execute(
                        role_permissions.insert().values(role_id=role_id, permission_id=lifecycle_id, created_at=now)
                    )

    auditor_id = bind.execute(sa.select(roles.c.id).where(roles.c.name == 'auditor')).scalar()
    if auditor_id:
        for key in ('settings.view_data_lifecycle', 'settings.export_data_lifecycle'):
            permission_id = permission_ids.get(key)
            if permission_id:
                exists = bind.execute(
                    sa.select(role_permissions.c.role_id).where(
                        role_permissions.c.role_id == auditor_id,
                        role_permissions.c.permission_id == permission_id,
                    )
                ).scalar()
                if exists is None:
                    bind.execute(
                        role_permissions.insert().values(
                            role_id=auditor_id, permission_id=permission_id, created_at=now
                        )
                    )


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.Integer), sa.column('key', sa.String))
    permission_ids = [
        row.id
        for row in bind.execute(
            sa.select(permissions.c.id).where(permissions.c.key.in_([item[0] for item in PERMISSIONS]))
        )
    ]
    if permission_ids:
        role_permissions = sa.table('role_permissions', sa.column('permission_id', sa.Integer))
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
        bind.execute(permissions.delete().where(permissions.c.id.in_(permission_ids)))
    op.drop_index('ix_job_executions_retention_boundary', table_name='job_executions')
    op.drop_index('ix_data_lifecycle_policies_enabled_domain', table_name='data_lifecycle_policies')
    op.drop_index('ix_data_lifecycle_policies_domain', table_name='data_lifecycle_policies')
    op.drop_table('data_lifecycle_policies')
