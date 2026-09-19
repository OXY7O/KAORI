"""Remove internal compatibility storage and authority fields.

Revision ID: 20260722_foundation_cleanup
Revises: 20260722_provider_authority
Create Date: 2026-07-22 12:00:00

This migration completes the development foundation cutover. It removes the
legacy users.role authority, converts transitional binding states to the
canonical validation contract, normalizes Prometheus binding capability scope,
requires canonical report storage URIs, and normalizes retired report-domain
names.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import sqlalchemy as sa
from alembic import op

revision = '20260722_foundation_cleanup'
down_revision = '20260722_provider_authority'
branch_labels = None
depends_on = None

_PROMETHEUS_CAPABILITIES = [
    'metrics',
    'capacity',
    'utilization',
    'storage',
    'workload',
    'forecast',
    'top_consumers',
    'alert_metrics',
]

_REPORT_DOMAIN_VALUE_MAP = {
    'kubereport': 'kubernetes',
    'kubernetes': 'kubernetes',
    'serverreport': 'server',
    'server': 'server',
    'hcireport': 'hci',
    'hci': 'hci',
}

_ENVIRONMENT_VALUE_MAP = {
    'dev': 'development',
    'development': 'development',
    'stg': 'staging',
    'stage': 'staging',
    'staging': 'staging',
    'prd': 'production',
    'prod': 'production',
    'production': 'production',
    'qa': 'quality_assurance',
    'quality_assurance': 'quality_assurance',
    'uat': 'user_acceptance_testing',
    'user_acceptance_testing': 'user_acceptance_testing',
    'test': 'testing',
    'testing': 'testing',
    'preprod': 'pre_production',
    'pre_prod': 'pre_production',
    'pre_production': 'pre_production',
    'np': 'non_production',
    'nonprod': 'non_production',
    'non_prod': 'non_production',
    'non_production': 'non_production',
    'dr': 'disaster_recovery',
    'drc': 'disaster_recovery',
    'disaster_recovery': 'disaster_recovery',
    'lab': 'laboratory',
    'laboratory': 'laboratory',
    'poc': 'proof_of_concept',
    'proof_of_concept': 'proof_of_concept',
    'demo': 'demonstration',
    'demonstration': 'demonstration',
    'sandbox': 'sandbox',
}


def _table_columns(bind: sa.Connection, table_name: str) -> set[str]:
    return {str(column['name']) for column in sa.inspect(bind).get_columns(table_name)}


def _normalize_report_uri(raw_path: str) -> str:
    value = raw_path.strip()
    if not value:
        raise RuntimeError('Cannot normalize an empty report file path.')

    if ':' in value:
        scheme, object_key = value.split(':', 1)
        scheme = scheme.strip().lower()
        object_key = object_key.strip().lstrip('/\\')
        if scheme not in {'local', 's3'} or not object_key:
            raise RuntimeError(
                f'Unsupported report storage URI {raw_path!r}. '
                'Only local:<object_key> and s3:<object_key> are accepted.'
            )
        return f'{scheme}:{object_key}'

    normalized = value.replace('\\', '/').strip()
    if normalized.startswith('instance/reports/'):
        object_key = normalized.removeprefix('instance/')
    elif normalized.startswith('reports/'):
        object_key = normalized
    elif '/reports/' in normalized:
        object_key = 'reports/' + normalized.split('/reports/', 1)[1]
    else:
        raise RuntimeError(
            f'Cannot safely convert report file path {raw_path!r}. '
            'Move the artifact below the configured reports/ directory or reset '
            'the development database before running this migration.'
        )

    object_key = str(PurePosixPath(object_key)).lstrip('/')
    if not object_key or object_key == '.':
        raise RuntimeError(f'Cannot derive a report object key from {raw_path!r}.')
    return f'local:{object_key}'


def _backfill_user_roles(bind: sa.Connection) -> None:
    columns = _table_columns(bind, 'users')
    if 'role' not in columns:
        return

    users = sa.table(
        'users',
        sa.column('id', sa.Integer),
        sa.column('role', sa.String),
        sa.column('role_id', sa.Integer),
    )
    roles = sa.table(
        'roles',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
    )
    role_ids = {str(row.name).strip().lower(): int(row.id) for row in bind.execute(sa.select(roles.c.id, roles.c.name))}
    viewer_role_id = role_ids.get('viewer')

    for row in bind.execute(sa.select(users.c.id, users.c.role, users.c.role_id).where(users.c.role_id.is_(None))):
        role_name = str(row.role or '').strip().lower()
        target_role_id = role_ids.get(role_name) or viewer_role_id
        if target_role_id is not None:
            bind.execute(users.update().where(users.c.id == row.id).values(role_id=target_role_id))

    with op.batch_alter_table('users') as batch:
        batch.drop_column('role')


def _normalize_bindings(bind: sa.Connection) -> None:
    bindings = sa.table(
        'integration_bindings',
        sa.column('id', sa.Integer),
        sa.column('integration_instance_id', sa.Integer),
        sa.column('asset_type', sa.String),
        sa.column('capability_scope', sa.JSON),
        sa.column('selector_json', sa.JSON),
        sa.column('validation_status', sa.String),
        sa.column('validation_message', sa.Text),
    )
    instances = sa.table(
        'integration_instances',
        sa.column('id', sa.Integer),
        sa.column('provider_type', sa.String),
    )

    bind.execute(
        bindings.update()
        .where(
            sa.or_(
                bindings.c.validation_status == 'legacy_unscoped',
                bindings.c.validation_status.is_(None),
            )
        )
        .values(
            validation_status='validation_required',
            validation_message=('Binding requires canonical selector and runtime validation before operational use.'),
        )
    )

    prometheus_binding_ids = bind.execute(
        sa.select(bindings.c.id)
        .select_from(
            bindings.join(
                instances,
                bindings.c.integration_instance_id == instances.c.id,
            )
        )
        .where(
            instances.c.provider_type == 'prometheus',
            bindings.c.asset_type == 'kubernetes_cluster',
        )
    ).scalars()

    for binding_id in prometheus_binding_ids:
        bind.execute(
            bindings.update().where(bindings.c.id == binding_id).values(capability_scope=list(_PROMETHEUS_CAPABILITIES))
        )


def _normalize_environment_values(bind: sa.Connection, table_name: str) -> None:
    columns = _table_columns(bind, table_name)
    if 'id' not in columns or 'environment' not in columns:
        return

    table = sa.table(
        table_name,
        sa.column('id', sa.Integer),
        sa.column('environment', sa.String),
    )
    rows = bind.execute(sa.select(table.c.id, table.c.environment).where(table.c.environment.is_not(None)))
    for row in rows:
        raw_value = str(row.environment or '').strip()
        normalized = raw_value.lower().replace('-', '_').replace(' ', '_')
        canonical = _ENVIRONMENT_VALUE_MAP.get(normalized, normalized)
        if canonical and canonical != raw_value:
            bind.execute(table.update().where(table.c.id == row.id).values(environment=canonical))


def _normalize_report_domains(bind: sa.Connection, table_name: str) -> None:
    columns = _table_columns(bind, table_name)
    if 'id' not in columns or 'report_domain' not in columns:
        return

    table = sa.table(
        table_name,
        sa.column('id', sa.Integer),
        sa.column('report_domain', sa.String),
    )
    rows = bind.execute(
        sa.select(table.c.id, table.c.report_domain).where(
            table.c.report_domain.is_not(None),
        )
    )
    for row in rows:
        raw_value = str(row.report_domain or '').strip()
        normalized = raw_value.lower().replace('-', '_').replace(' ', '_')
        canonical = _REPORT_DOMAIN_VALUE_MAP.get(normalized)
        if canonical is None:
            raise RuntimeError(
                f'Unsupported report domain {raw_value!r} in {table_name}. '
                'Convert it to kubernetes, server, or hci before running this migration.'
            )
        if canonical != raw_value:
            bind.execute(table.update().where(table.c.id == row.id).values(report_domain=canonical))

    with op.batch_alter_table(table_name) as batch:
        batch.alter_column(
            'report_domain',
            existing_type=sa.String(length=50),
            existing_nullable=False,
            server_default='kubernetes',
        )


def _normalize_report_paths(bind: sa.Connection) -> None:
    reports = sa.table(
        'reports',
        sa.column('id', sa.Integer),
        sa.column('file_path', sa.String),
    )
    rows = bind.execute(
        sa.select(reports.c.id, reports.c.file_path).where(
            reports.c.file_path.is_not(None),
            reports.c.file_path != '',
        )
    )
    for row in rows:
        canonical_uri = _normalize_report_uri(str(row.file_path))
        if canonical_uri != row.file_path:
            bind.execute(reports.update().where(reports.c.id == row.id).values(file_path=canonical_uri))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if {'users', 'roles'}.issubset(tables):
        _backfill_user_roles(bind)
    if 'clusters' in tables:
        _normalize_environment_values(bind, 'clusters')
    if 'integration_instances' in tables:
        _normalize_environment_values(bind, 'integration_instances')
    if {'integration_bindings', 'integration_instances'}.issubset(tables):
        _normalize_bindings(bind)
    for table_name in ('reports', 'report_templates', 'report_schedules'):
        if table_name in tables:
            _normalize_report_domains(bind, table_name)
    if 'reports' in tables:
        _normalize_report_paths(bind)


def downgrade() -> None:
    raise RuntimeError(
        'This foundation compatibility cleanup is intentionally irreversible. '
        'Restore a database backup or reset the development database instead.'
    )
