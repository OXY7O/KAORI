"""Add guarded append-only Capsule handoff attempt ledger (source-only).

Revision ID: 20261011_capsule_ledger
Revises: 20261009_tenant_released
Create Date: 2026-10-11

No live migration, provider operation, or AuditEvent writer is admitted by
merging this file. Dialects other than PostgreSQL/SQLite fail closed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261011_capsule_ledger'
down_revision = '20261009_tenant_released'
branch_labels = None
depends_on = None

_TABLE = 'capsule_handoff_ledger_events'
_PG_GUARD = 'kaori_capsule_handoff_ledger_insert_guard'


def _dialect() -> str:
    name = op.get_bind().dialect.name
    if name not in ('postgresql', 'sqlite'):
        raise RuntimeError(
            'Capsule write-once ledger migration supports only PostgreSQL/SQLite; '
            'review the exact database engine before admission.'
        )
    return name


def _pg_guards() -> None:
    # The Tenant row lock serializes the three immutable event inserts across
    # concurrent sessions even if they target different attempt IDs.
    op.execute("""
CREATE FUNCTION kaori_capsule_handoff_ledger_insert_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE previous capsule_handoff_ledger_events%ROWTYPE;
BEGIN
    PERFORM 1 FROM tenants WHERE id = NEW.tenant_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Capsule ledger Tenant identity is unavailable';
    END IF;
    IF NEW.sequence = 1 THEN
        IF EXISTS (
            SELECT 1 FROM capsule_handoff_ledger_events
            WHERE tenant_id = NEW.tenant_id
        ) OR NEW.previous_event_sha256 IS NOT NULL THEN
            RAISE EXCEPTION 'Capsule ledger attempt already exists or START carries a predecessor';
        END IF;
    ELSE
        SELECT * INTO previous FROM capsule_handoff_ledger_events
        WHERE tenant_id = NEW.tenant_id AND sequence = NEW.sequence - 1;
        IF NOT FOUND OR previous.attempt_id <> NEW.attempt_id
            OR previous.plan_sha256 <> NEW.plan_sha256
            OR previous.cluster_id <> NEW.cluster_id
            OR previous.generation <> NEW.generation
            OR previous.handoff_fingerprint <> NEW.handoff_fingerprint
            OR previous.worklist_sha256 <> NEW.worklist_sha256
            OR previous.event_sha256 <> NEW.previous_event_sha256
            OR NEW.event_at <= previous.event_at
            OR (
                NEW.sequence = 2
                AND (previous.event_type <> 'started'
                    OR NEW.actor_user_id <> previous.actor_user_id)
            )
            OR (
                NEW.sequence = 3
                AND (previous.event_type NOT IN ('partial', 'readback_candidate')
                    OR NEW.actor_user_id = previous.actor_user_id)
            )
        THEN
            RAISE EXCEPTION 'Capsule ledger predecessor, actor or immutable scope mismatch';
        END IF;
    END IF;
    RETURN NEW;
END;
$$
""")
    op.execute("""
CREATE FUNCTION kaori_capsule_handoff_ledger_deny_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Capsule handoff ledger is write-once';
END;
$$
""")
    op.execute(f"""
CREATE TRIGGER tr_capsule_ledger_guard_insert
BEFORE INSERT ON {_TABLE}
FOR EACH ROW EXECUTE FUNCTION {_PG_GUARD}()
""")
    op.execute(f"""
CREATE TRIGGER tr_capsule_ledger_deny_update
BEFORE UPDATE ON {_TABLE}
FOR EACH ROW EXECUTE FUNCTION kaori_capsule_handoff_ledger_deny_change()
""")
    op.execute(f"""
CREATE TRIGGER tr_capsule_ledger_deny_delete
BEFORE DELETE ON {_TABLE}
FOR EACH ROW EXECUTE FUNCTION kaori_capsule_handoff_ledger_deny_change()
""")
    # TRUNCATE does not invoke PostgreSQL row-level DELETE triggers.
    op.execute(f"""
CREATE TRIGGER tr_capsule_ledger_deny_truncate
BEFORE TRUNCATE ON {_TABLE}
FOR EACH STATEMENT EXECUTE FUNCTION kaori_capsule_handoff_ledger_deny_change()
""")


def _sqlite_guards() -> None:
    # SQLite allows a single active database writer; these predicates enforce
    # the predecessor chain inside that write transaction.
    op.execute(f"""
CREATE TRIGGER tr_capsule_ledger_guard_insert
BEFORE INSERT ON {_TABLE}
BEGIN
    SELECT CASE WHEN
        (NEW.sequence = 1 AND (
            NEW.previous_event_sha256 IS NOT NULL OR EXISTS (
                SELECT 1 FROM {_TABLE} WHERE tenant_id = NEW.tenant_id
            )
        ))
        OR (NEW.sequence > 1 AND NOT EXISTS (
            SELECT 1 FROM {_TABLE} AS prior
            WHERE prior.tenant_id = NEW.tenant_id
              AND prior.sequence = NEW.sequence - 1
              AND prior.attempt_id = NEW.attempt_id
              AND prior.cluster_id = NEW.cluster_id
              AND prior.generation = NEW.generation
              AND prior.plan_sha256 = NEW.plan_sha256
              AND prior.handoff_fingerprint = NEW.handoff_fingerprint
              AND prior.worklist_sha256 = NEW.worklist_sha256
              AND prior.event_sha256 = NEW.previous_event_sha256
              AND julianday(NEW.event_at) > julianday(prior.event_at)
              AND (
                (NEW.sequence = 2 AND prior.event_type = 'started'
                 AND NEW.actor_user_id = prior.actor_user_id)
                OR (NEW.sequence = 3
                 AND prior.event_type IN ('partial', 'readback_candidate')
                 AND NEW.actor_user_id <> prior.actor_user_id)
              )
        ))
    THEN RAISE(ABORT, 'Capsule ledger predecessor or immutable scope mismatch')
    END;
END
""")
    for action in ('UPDATE', 'DELETE'):
        op.execute(f"""
CREATE TRIGGER tr_capsule_ledger_deny_{action.lower()}
BEFORE {action} ON {_TABLE}
BEGIN
    SELECT RAISE(ABORT, 'Capsule handoff ledger is write-once');
END
""")


def upgrade() -> None:
    dialect = _dialect()  # refuse unsupported dialect before any DDL
    op.create_table(
        _TABLE,
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        sa.Column('cluster_id', sa.String(36), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('plan_sha256', sa.String(64), nullable=False),
        sa.Column('handoff_fingerprint', sa.String(64), nullable=False),
        sa.Column('worklist_sha256', sa.String(64), nullable=False),
        sa.Column('attempt_id', sa.String(36), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(32), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=False),
        sa.Column('event_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('previous_event_sha256', sa.String(64), nullable=True),
        sa.Column('event_sha256', sa.String(64), nullable=False),
        sa.Column('event_json', sa.JSON(), nullable=False),
        sa.Column(
            'recorded_at', sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('tenant_id', 'sequence', name='uq_capsule_ledger_tenant_sequence'),
        sa.UniqueConstraint(
            'tenant_id', 'attempt_id', 'sequence',
            name='uq_capsule_ledger_attempt_sequence',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'event_sha256', name='uq_capsule_ledger_tenant_digest',
        ),
        sa.CheckConstraint('generation > 0', name='ck_capsule_ledger_generation'),
        sa.CheckConstraint('sequence BETWEEN 1 AND 3', name='ck_capsule_ledger_sequence'),
        sa.CheckConstraint(
            "(sequence = 1 AND event_type = 'started') OR "
            "(sequence = 2 AND event_type IN ('partial', 'readback_candidate')) OR "
            "(sequence = 3 AND event_type = 'recovery_reviewed')",
            name='ck_capsule_ledger_event_progression',
        ),
    )
    op.create_index('ix_capsule_handoff_ledger_events_tenant_id', _TABLE, ['tenant_id'])
    if dialect == 'postgresql':
        _pg_guards()
    else:
        _sqlite_guards()


def downgrade() -> None:
    dialect = _dialect()
    # A downgrade must never silently erase committed recovery evidence.
    if op.get_bind().exec_driver_sql(
        f'SELECT 1 FROM {_TABLE} LIMIT 1'
    ).first():
        raise RuntimeError('Cannot drop a Capsule handoff ledger containing evidence.')
    names = [
        'tr_capsule_ledger_guard_insert',
        'tr_capsule_ledger_deny_update',
        'tr_capsule_ledger_deny_delete',
    ]
    if dialect == 'postgresql':
        names.append('tr_capsule_ledger_deny_truncate')
    for name in names:
        op.execute(f'DROP TRIGGER {name} ON {_TABLE}' if dialect == 'postgresql'
                   else f'DROP TRIGGER {name}')
    if dialect == 'postgresql':
        op.execute(f'DROP FUNCTION {_PG_GUARD}()')
        op.execute('DROP FUNCTION kaori_capsule_handoff_ledger_deny_change()')
    op.drop_index('ix_capsule_handoff_ledger_events_tenant_id', table_name=_TABLE)
    op.drop_table(_TABLE)
