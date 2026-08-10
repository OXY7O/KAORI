"""generalize scheduled jobs and add job control permissions

Revision ID: 20260724_job_orchestration
Revises: 20260724_inventory_sync
Create Date: 2026-07-24 17:00:00
"""

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa

revision = '20260724_job_orchestration'
down_revision = '20260724_inventory_sync'
branch_labels = None
depends_on = None

PERMISSIONS = (
    (
        'jobs.execute',
        'operations',
        'execute_jobs',
        'Run supported KAORI jobs manually within the permissions of their owning domain.',
    ),
    (
        'jobs.configure',
        'operations',
        'configure_jobs',
        'Configure automatic schedules and execution policies for registered KAORI jobs.',
    ),
)


def _assign_permission(bind, role_permissions, role_id: int, permission_id: int, now: datetime) -> None:
    exists = bind.execute(
        sa.select(role_permissions.c.role_id).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission_id,
        )
    ).scalar()
    if exists is None:
        bind.execute(
            role_permissions.insert().values(
                role_id=role_id,
                permission_id=permission_id,
                created_at=now,
            )
        )


def upgrade() -> None:
    op.create_table(
        'job_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_key', sa.String(length=120), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('trigger_type', sa.String(length=30), nullable=False, server_default='interval'),
        sa.Column('interval_minutes', sa.Integer(), nullable=True),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'),
        sa.Column('scope_type', sa.String(length=80), nullable=False, server_default='global'),
        sa.Column('scope_key', sa.String(length=255), nullable=False, server_default='all'),
        sa.Column('configuration_json', sa.JSON(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_dispatch_status', sa.String(length=40), nullable=True),
        sa.Column('last_dispatch_message', sa.String(length=255), nullable=True),
        sa.Column('last_job_execution_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "trigger_type = 'interval'",
            name='ck_job_policy_trigger_type',
        ),
        sa.CheckConstraint(
            'interval_minutes IS NULL OR (interval_minutes >= 5 AND interval_minutes <= 1440)',
            name='ck_job_policy_interval',
        ),
        sa.ForeignKeyConstraint(['last_job_execution_id'], ['job_executions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_key', 'scope_type', 'scope_key', name='uq_job_policy_scope'),
    )
    op.create_index('ix_job_policies_due', 'job_policies', ['enabled', 'next_run_at'], unique=False)
    op.create_index('ix_job_policies_job_key', 'job_policies', ['job_key'], unique=False)
    op.create_index('ix_job_policies_last_job_execution_id', 'job_policies', ['last_job_execution_id'], unique=False)
    op.create_index('ix_job_policies_next_run_at', 'job_policies', ['next_run_at'], unique=False)
    op.create_index('ix_job_policies_updated_by_user_id', 'job_policies', ['updated_by_user_id'], unique=False)

    op.execute(
        'INSERT INTO job_policies '
        '(job_key, enabled, trigger_type, interval_minutes, timezone, scope_type, scope_key, '
        ' next_run_at, last_dispatched_at, updated_by_user_id, created_at, updated_at) '
        "SELECT 'kubernetes.inventory.sync', enabled, 'interval', interval_minutes, 'UTC', "
        "       'kubernetes_fleet', 'all', next_run_at, last_dispatched_at, updated_by_user_id, "
        '       updated_at, updated_at '
        'FROM inventory_sync_policies'
    )
    op.drop_table('inventory_sync_policies')

    bind = op.get_bind()
    now = datetime.now(UTC)
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
        permission_id = bind.execute(sa.select(permissions.c.id).where(permissions.c.key == key)).scalar()
        if permission_id is None:
            bind.execute(
                permissions.insert().values(
                    key=key,
                    module=module,
                    action=action,
                    description=description,
                    created_at=now,
                )
            )

    permission_ids = {
        row.key: row.id
        for row in bind.execute(
            sa.select(permissions.c.id, permissions.c.key).where(
                permissions.c.key.in_([item[0] for item in PERMISSIONS])
            )
        )
    }
    roles = sa.table('roles', sa.column('id', sa.Integer), sa.column('name', sa.String))
    role_permissions = sa.table(
        'role_permissions',
        sa.column('role_id', sa.Integer),
        sa.column('permission_id', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    default_assignments = {
        'operator': ('jobs.execute',),
        'editor': ('jobs.execute', 'jobs.configure'),
        'admin': ('jobs.execute', 'jobs.configure'),
    }
    for role_name, keys in default_assignments.items():
        role_id = bind.execute(sa.select(roles.c.id).where(roles.c.name == role_name)).scalar()
        if role_id is None:
            continue
        for key in keys:
            permission_id = permission_ids.get(key)
            if permission_id is not None:
                _assign_permission(bind, role_permissions, role_id, permission_id, now)

    legacy_permission_ids = {
        row.key: row.id
        for row in bind.execute(
            sa.select(permissions.c.id, permissions.c.key).where(
                permissions.c.key.in_(('clusters.sync', 'settings.manage_integrations'))
            )
        )
    }
    mappings = {
        'clusters.sync': ('jobs.execute',),
        'settings.manage_integrations': ('jobs.configure',),
    }
    for legacy_key, target_keys in mappings.items():
        legacy_id = legacy_permission_ids.get(legacy_key)
        if legacy_id is None:
            continue
        role_ids = [
            row.role_id
            for row in bind.execute(
                sa.select(role_permissions.c.role_id).where(role_permissions.c.permission_id == legacy_id)
            )
        ]
        for role_id in role_ids:
            for target_key in target_keys:
                target_id = permission_ids.get(target_key)
                if target_id is not None:
                    _assign_permission(bind, role_permissions, role_id, target_id, now)


def downgrade() -> None:
    op.create_table(
        'inventory_sync_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('interval_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('id = 1', name='ck_inventory_sync_policy_singleton'),
        sa.CheckConstraint(
            'interval_minutes >= 5 AND interval_minutes <= 1440',
            name='ck_inventory_sync_policy_interval',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute(
        'INSERT INTO inventory_sync_policies '
        '(id, enabled, interval_minutes, next_run_at, last_dispatched_at, updated_by_user_id, updated_at) '
        'SELECT 1, enabled, COALESCE(interval_minutes, 60), next_run_at, last_dispatched_at, '
        '       updated_by_user_id, updated_at '
        "FROM job_policies WHERE job_key = 'kubernetes.inventory.sync' "
        'ORDER BY id LIMIT 1'
    )

    op.drop_index('ix_job_policies_updated_by_user_id', table_name='job_policies')
    op.drop_index('ix_job_policies_next_run_at', table_name='job_policies')
    op.drop_index('ix_job_policies_last_job_execution_id', table_name='job_policies')
    op.drop_index('ix_job_policies_job_key', table_name='job_policies')
    op.drop_index('ix_job_policies_due', table_name='job_policies')
    op.drop_table('job_policies')

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
