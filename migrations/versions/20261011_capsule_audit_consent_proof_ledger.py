"""Add write-once Capsule audit replay and per-object consent proof tables.

Revision ID: 20261011_capsule_proof
Revises: 20261011_capsule_ledger
Create Date: 2026-10-11

This migration is authored for independent review; DO NOT EXECUTE while
provider and CI/CD gates remain HOLD. A migration file is NOT a storage
attestation, key registry, trusted audit collector or consent writer.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261011_capsule_proof'
down_revision = '20261011_capsule_ledger'
branch_labels = None
depends_on = None

_BATCH = 'capsule_handoff_audit_batches'
_CONSENT = 'capsule_handoff_resource_consent_records'
_PG_DENY = 'kaori_capsule_proof_deny_change'


def _dialect() -> str:
    name = op.get_bind().dialect.name
    if name not in ('postgresql', 'sqlite'):
        raise RuntimeError('Capsule proof storage requires independently reviewed PostgreSQL/SQLite.')
    if name == 'sqlite':
        # The composite batch-consent FK must not silently be disabled.
        if op.get_bind().exec_driver_sql('PRAGMA foreign_keys').scalar() != 1:
            raise RuntimeError('SQLite foreign_keys must be ON before Capsule proof DDL.')
    return name


def _create_batch() -> None:
    op.create_table(
        _BATCH,
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('batch_id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('cluster_id', sa.String(36), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('plan_sha256', sa.String(64), nullable=False),
        sa.Column('worklist_sha256', sa.String(64), nullable=False),
        sa.Column('resource_review_sha256', sa.String(64), nullable=False),
        sa.Column('claims_sha256', sa.String(64), nullable=False),
        sa.Column('receipt_sha256', sa.String(64), nullable=False),
        sa.Column('collector_id', sa.String(120), nullable=False),
        sa.Column('key_id', sa.String(120), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('batch_id', name='uq_capsule_audit_batch_global_id'),
        sa.UniqueConstraint('tenant_id', name='uq_capsule_audit_batch_tenant_once'),
        sa.UniqueConstraint('tenant_id', 'plan_sha256', name='uq_capsule_audit_batch_plan_once'),
        sa.UniqueConstraint(
            'batch_id',
            'tenant_id',
            'plan_sha256',
            'worklist_sha256',
            'resource_review_sha256',
            name='uq_capsule_audit_batch_full_scope',
        ),
        sa.CheckConstraint('generation > 0', name='ck_capsule_audit_batch_generation'),
        sa.CheckConstraint(
            'length(batch_id) = 36 AND length(plan_sha256) = 64 '
            'AND length(worklist_sha256) = 64 '
            'AND length(resource_review_sha256) = 64 '
            'AND length(claims_sha256) = 64 '
            'AND length(receipt_sha256) = 64',
            name='ck_capsule_audit_batch_digest_shape',
        ),
    )
    op.create_index('ix_capsule_audit_batch_tenant', _BATCH, ['tenant_id'])


def _create_consent() -> None:
    op.create_table(
        _CONSENT,
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('batch_id', sa.String(36), nullable=False),
        sa.Column('plan_sha256', sa.String(64), nullable=False),
        sa.Column('worklist_sha256', sa.String(64), nullable=False),
        sa.Column('resource_review_sha256', sa.String(64), nullable=False),
        sa.Column('consent_manifest_sha256', sa.String(64), nullable=False),
        sa.Column('resource_scope_sha256', sa.String(64), nullable=False),
        sa.Column('target_count', sa.Integer(), nullable=False),
        sa.Column('requester_user_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_user_id', sa.Integer(), nullable=False),
        sa.Column('successor_user_id', sa.Integer(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['requester_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['successor_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(
            ['batch_id', 'tenant_id', 'plan_sha256', 'worklist_sha256', 'resource_review_sha256'],
            [
                f'{_BATCH}.batch_id',
                f'{_BATCH}.tenant_id',
                f'{_BATCH}.plan_sha256',
                f'{_BATCH}.worklist_sha256',
                f'{_BATCH}.resource_review_sha256',
            ],
            ondelete='RESTRICT',
            name='fk_capsule_resource_consent_exact_audit_batch',
        ),
        sa.UniqueConstraint('tenant_id', name='uq_capsule_resource_consent_tenant_once'),
        sa.UniqueConstraint('tenant_id', 'plan_sha256', name='uq_capsule_resource_consent_plan_once'),
        sa.UniqueConstraint(
            'tenant_id',
            'consent_manifest_sha256',
            name='uq_capsule_resource_consent_manifest',
        ),
        sa.CheckConstraint('target_count BETWEEN 1 AND 330', name='ck_capsule_resource_consent_target_count'),
        sa.CheckConstraint(
            'requester_user_id <> reviewer_user_id '
            'AND requester_user_id <> successor_user_id '
            'AND reviewer_user_id <> successor_user_id',
            name='ck_capsule_resource_consent_independent_actors',
        ),
        sa.CheckConstraint(
            'length(batch_id) = 36 AND length(plan_sha256) = 64 '
            'AND length(worklist_sha256) = 64 '
            'AND length(resource_review_sha256) = 64 '
            'AND length(consent_manifest_sha256) = 64 '
            'AND length(resource_scope_sha256) = 64',
            name='ck_capsule_resource_consent_digest_shape',
        ),
    )
    op.create_index('ix_capsule_resource_consent_tenant', _CONSENT, ['tenant_id'])


def _append_guards(dialect: str) -> None:
    if dialect == 'postgresql':
        op.execute(f"""
CREATE FUNCTION {_PG_DENY}() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Capsule audit/consent evidence is write-once';
END;
$$
""")
        for table, prefix in ((_BATCH, 'batch'), (_CONSENT, 'consent')):
            for operation in ('UPDATE', 'DELETE', 'TRUNCATE'):
                op.execute(f"""
CREATE TRIGGER tr_capsule_{prefix}_deny_{operation.lower()}
BEFORE {operation} ON {table}
FOR EACH {'STATEMENT' if operation == 'TRUNCATE' else 'ROW'}
EXECUTE FUNCTION {_PG_DENY}()
""")
    else:
        for table, prefix in ((_BATCH, 'batch'), (_CONSENT, 'consent')):
            for operation in ('UPDATE', 'DELETE'):
                op.execute(f"""
CREATE TRIGGER tr_capsule_{prefix}_deny_{operation.lower()}
BEFORE {operation} ON {table}
BEGIN
    SELECT RAISE(ABORT, 'Capsule audit/consent evidence is write-once');
END
""")


def upgrade() -> None:
    dialect = _dialect()  # fail before creating even the first evidence table
    _create_batch()
    _create_consent()
    _append_guards(dialect)


def downgrade() -> None:
    dialect = _dialect()
    # Never silently destroy genuine controller/provenance consent history.
    for table in (_CONSENT, _BATCH):
        if op.get_bind().exec_driver_sql(f'SELECT 1 FROM {table} LIMIT 1').first():
            raise RuntimeError('Refusing to destroy committed Capsule audit/consent evidence.')
    for table, prefix in ((_CONSENT, 'consent'), (_BATCH, 'batch')):
        operations = ('update', 'delete', 'truncate') if dialect == 'postgresql' else ('update', 'delete')
        for operation in operations:
            name = f'tr_capsule_{prefix}_deny_{operation}'
            op.execute(f'DROP TRIGGER {name} ON {table}' if dialect == 'postgresql' else f'DROP TRIGGER {name}')
    if dialect == 'postgresql':
        op.execute(f'DROP FUNCTION {_PG_DENY}()')
    op.drop_index('ix_capsule_resource_consent_tenant', table_name=_CONSENT)
    op.drop_table(_CONSENT)
    op.drop_index('ix_capsule_audit_batch_tenant', table_name=_BATCH)
    op.drop_table(_BATCH)
