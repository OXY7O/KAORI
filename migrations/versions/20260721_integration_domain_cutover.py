"""complete canonical integration domain cutover

Revision ID: 20260721_integration_cutover
Revises: 20260721_job_operations_rbac
Create Date: 2026-07-21 15:30:00

This migration is intentionally destructive after verifying that every legacy
record has a canonical replacement. Take a database backup before applying it.
"""
from __future__ import annotations

import base64
import hashlib
import os

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

revision = '20260721_integration_cutover'
down_revision = '20260721_job_operations_rbac'
branch_labels = None
depends_on = None


_CREDENTIAL_PREFIX = 'enc:v1:'


def _migration_fernet() -> Fernet:
    configured = (os.getenv('INTEGRATION_CREDENTIAL_KEY') or '').strip()
    if not configured:
        raise RuntimeError(
            'Canonical integration cutover requires INTEGRATION_CREDENTIAL_KEY before credential encryption.'
        )
    secret = configured.encode('utf-8')
    try:
        decoded = base64.urlsafe_b64decode(secret)
    except Exception:
        decoded = b''
    key = secret if len(decoded) == 32 else base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def _encrypt_credential(value: str) -> str:
    if value.startswith(_CREDENTIAL_PREFIX):
        return value
    token = _migration_fernet().encrypt(value.encode('utf-8')).decode('ascii')
    return f'{_CREDENTIAL_PREFIX}{token}'


_PROVIDER_BINDING_BACKFILL = {
    'prometheus': {
        'instance_table': 'prometheus_instances',
        'binding_table': 'prometheus_bindings',
        'provider_fk': 'prometheus_instance_id',
        'capabilities': [
            'metrics', 'capacity', 'utilization', 'storage', 'workload',
            'forecast', 'top_consumers', 'alert_metrics',
        ],
    },
    'alertmanager': {
        'instance_table': 'alertmanager_instances',
        'binding_table': 'alertmanager_bindings',
        'provider_fk': 'alertmanager_instance_id',
        'capabilities': [
            'alerts', 'alerts_v2', 'silences', 'silences_v2',
            'routing', 'receivers', 'status_v2',
        ],
    },
}


def _scalar(bind, statement: str, **params: object) -> int:
    return int(bind.execute(sa.text(statement), params).scalar() or 0)


def _assert_cutover_ready(bind) -> None:
    missing_connections = _scalar(
        bind,
        """
        SELECT COUNT(*)
        FROM clusters AS cluster
        LEFT JOIN kubernetes_connections AS connection
          ON connection.cluster_id = cluster.id
        WHERE connection.id IS NULL
           OR connection.integration_instance_id IS NULL
           OR NULLIF(connection.kubeconfig, '') IS NULL
        """,
    )
    if missing_connections:
        raise RuntimeError(
            f'Canonical integration cutover blocked: {missing_connections} cluster(s) '
            'do not have a complete KubernetesConnection.'
        )

    for provider, settings in _PROVIDER_BINDING_BACKFILL.items():
        missing_identity = _scalar(
            bind,
            f"""
            SELECT COUNT(*)
            FROM {settings['instance_table']}
            WHERE integration_instance_id IS NULL
            """,
        )
        if missing_identity:
            raise RuntimeError(
                f'Canonical integration cutover blocked: {missing_identity} {provider} '
                'instance(s) do not have an IntegrationInstance identity.'
            )


def _backfill_remaining_legacy_bindings(bind) -> None:
    now_expression = 'CURRENT_TIMESTAMP'
    for settings in _PROVIDER_BINDING_BACKFILL.values():
        statement = sa.text(
            f"""
            INSERT INTO integration_bindings (
                integration_instance_id,
                asset_type,
                asset_key,
                binding_role,
                priority,
                enabled,
                capability_scope,
                selector_json,
                validation_status,
                validation_message,
                last_validated_at,
                created_at,
                updated_at
            )
            SELECT
                provider.integration_instance_id,
                legacy.scope_type,
                legacy.scope_key,
                COALESCE(legacy.binding_role, 'primary'),
                COALESCE(legacy.priority, 100),
                COALESCE(legacy.enabled, TRUE),
                CAST(:capabilities AS json),
                NULL,
                'validation_required',
                'Migrated from the retired provider-specific binding table.',
                NULL,
                COALESCE(legacy.created_at, {now_expression}),
                COALESCE(legacy.updated_at, {now_expression})
            FROM {settings['binding_table']} AS legacy
            JOIN {settings['instance_table']} AS provider
              ON provider.id = legacy.{settings['provider_fk']}
            ON CONFLICT (
                integration_instance_id,
                asset_type,
                asset_key,
                binding_role
            ) DO NOTHING
            """
        )
        import json
        bind.execute(statement, {'capabilities': json.dumps(settings['capabilities'])})


def _assert_legacy_bindings_materialized(bind) -> None:
    for provider, settings in _PROVIDER_BINDING_BACKFILL.items():
        missing = _scalar(
            bind,
            f"""
            SELECT COUNT(*)
            FROM {settings['binding_table']} AS legacy
            JOIN {settings['instance_table']} AS provider
              ON provider.id = legacy.{settings['provider_fk']}
            LEFT JOIN integration_bindings AS canonical
              ON canonical.integration_instance_id = provider.integration_instance_id
             AND canonical.asset_type = legacy.scope_type
             AND canonical.asset_key = legacy.scope_key
             AND canonical.binding_role = COALESCE(legacy.binding_role, 'primary')
            WHERE canonical.id IS NULL
            """,
        )
        if missing:
            raise RuntimeError(
                f'Canonical integration cutover blocked: {missing} legacy {provider} '
                'binding(s) could not be materialized.'
            )


def _encrypt_column(bind, table_name: str, column_name: str) -> None:
    rows = bind.execute(
        sa.text(
            f"SELECT id, {column_name} AS credential FROM {table_name} "
            f"WHERE {column_name} IS NOT NULL AND {column_name} <> ''"
        )
    ).mappings()
    for row in rows:
        encrypted = _encrypt_credential(str(row['credential']))
        bind.execute(
            sa.text(
                f'UPDATE {table_name} SET {column_name} = :credential WHERE id = :id'
            ),
            {'credential': encrypted, 'id': row['id']},
        )


def upgrade() -> None:
    bind = op.get_bind()
    _assert_cutover_ready(bind)
    _backfill_remaining_legacy_bindings(bind)
    _assert_legacy_bindings_materialized(bind)

    _encrypt_column(bind, 'kubernetes_connections', 'kubeconfig')
    for table_name in ('prometheus_instances', 'alertmanager_instances'):
        _encrypt_column(bind, table_name, 'password')
        _encrypt_column(bind, table_name, 'bearer_token')

    # Provider-specific binding/configuration persistence has been superseded by
    # IntegrationBinding and provider instance records. Bookmark compatibility
    # remains at the HTTP layer only.
    op.drop_table('prometheus_bindings')
    op.drop_table('alertmanager_bindings')
    op.drop_table('prometheus_configs')
    op.drop_table('alertmanager_configs')

    with op.batch_alter_table('clusters') as batch:
        batch.drop_column('kubeconfig')
        batch.drop_column('kube_verify_ssl')
        batch.drop_column('kube_allow_weak_tls')
        batch.drop_column('server')

    # Previous migrations copied role assignments to the canonical Data
    # Lifecycle permissions. Remove the two obsolete action permissions from
    # fresh and upgraded installations.
    bind.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE key IN (
                'settings.export_operational_activity',
                'settings.manage_operational_activity_retention'
            )
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        '20260721_integration_cutover is an irreversible canonical cutover. '
        'Restore the pre-migration database backup to roll back.'
    )
