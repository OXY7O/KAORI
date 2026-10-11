"""Protect Capsule successor handback START from replay/deletion (#1231).

Revision ID: 20261012_capsule_handback_guard
Revises: 20261011_reveal_uid

Source-only migration. NOT executed or installed by merge. Production
handback is denied until the PostgreSQL triggers, unique START index,
non-owner DB privileges and WAL durability are independently verified.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261012_capsule_handback_guard'
down_revision = '20261011_reveal_uid'
branch_labels = None
depends_on = None

_TARGET = 'kubernetes_tenant_verified_capsule_successor_handback'
_START = 'tenant.release.capsule_successor_handback_started'
_INDEX = 'uq_capsule_handback_start_tenant_once'
_FUNCTION = 'kaori_capsule_handback_audit_deny_change'


def _dialect() -> str:
    dialect = op.get_bind().dialect.name
    if dialect not in ('postgresql', 'sqlite'):
        raise RuntimeError('Capsule handback START guard supports PostgreSQL/SQLite only.')
    return dialect


def upgrade() -> None:
    dialect = _dialect()
    # A restart cannot silently issue a second START for the same predecessor.
    op.create_index(
        _INDEX, 'audit_events', ['target_id'], unique=True,
        postgresql_where=sa.text(
            f"target_type = '{_TARGET}' AND action = '{_START}'"
        ),
        sqlite_where=sa.text(
            f"target_type = '{_TARGET}' AND action = '{_START}'"
        ),
    )
    if dialect == 'postgresql':
        op.execute(f"""
CREATE FUNCTION {_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'TRUNCATE' THEN
        RAISE EXCEPTION 'Capsule successor START cannot be truncated';
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.target_type = '{_TARGET}' THEN
            RAISE EXCEPTION 'Capsule successor handback audit is write-once';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.target_type = '{_TARGET}' OR NEW.target_type = '{_TARGET}' THEN
        RAISE EXCEPTION 'Capsule successor handback audit is write-once';
    END IF;
    RETURN NEW;
END;
$$
""")
        for operation in ('UPDATE', 'DELETE', 'TRUNCATE'):
            op.execute(f"""
CREATE TRIGGER tr_capsule_handback_audit_deny_{operation.lower()}
BEFORE {operation} ON audit_events
FOR EACH {'STATEMENT' if operation == 'TRUNCATE' else 'ROW'}
EXECUTE FUNCTION {_FUNCTION}()
""")
    else:
        for operation in ('UPDATE', 'DELETE'):
            predicate = (
                f"OLD.target_type = '{_TARGET}' OR NEW.target_type = '{_TARGET}'"
                if operation == 'UPDATE'
                else f"OLD.target_type = '{_TARGET}'"
            )
            op.execute(f"""
CREATE TRIGGER tr_capsule_handback_audit_deny_{operation.lower()}
BEFORE {operation} ON audit_events
WHEN {predicate}
BEGIN
    SELECT RAISE(ABORT, 'Capsule successor handback audit is write-once');
END
""")


def downgrade() -> None:
    dialect = _dialect()
    if op.get_bind().execute(
        sa.text('SELECT 1 FROM audit_events WHERE target_type = :target LIMIT 1'),
        {'target': _TARGET},
    ).first():
        raise RuntimeError('Cannot remove Capsule handback guards with recorded attempt evidence.')
    names = ['tr_capsule_handback_audit_deny_update',
             'tr_capsule_handback_audit_deny_delete']
    if dialect == 'postgresql':
        names.append('tr_capsule_handback_audit_deny_truncate')
    for name in names:
        op.execute(
            f'DROP TRIGGER {name} ON audit_events'
            if dialect == 'postgresql' else f'DROP TRIGGER {name}'
        )
    if dialect == 'postgresql':
        op.execute(f'DROP FUNCTION {_FUNCTION}()')
    op.drop_index(_INDEX, table_name='audit_events')
