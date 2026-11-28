"""Add disabled-by-default local account lockout persistence (#5324)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_account_lockout'
down_revision = '20261128_ldap_replacement_proof'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('authentication_security_policies') as batch:
        batch.add_column(sa.Column('lockout_mode', sa.String(24), nullable=False, server_default='disabled'))
        batch.add_column(sa.Column('lockout_revision', sa.BigInteger(), nullable=False, server_default=sa.text('1')))
        batch.create_check_constraint(
            'ck_auth_security_lockout_mode', "lockout_mode IN ('disabled', 'monitor_only', 'enforced')"
        )
        batch.create_check_constraint('ck_auth_security_lockout_revision', 'lockout_revision >= 1')
    op.create_table(
        'authentication_account_lockouts',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('policy_revision', sa.BigInteger(), nullable=False),
        sa.Column('failure_times', sa.JSON(), nullable=False),
        sa.Column('cooldown_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('policy_revision >= 1', name='ck_auth_lockout_policy_revision'),
        sa.CheckConstraint('json_array_length(failure_times) <= 10', name='ck_auth_lockout_failure_bound'),
        sa.CheckConstraint(
            'cooldown_until IS NULL OR locked_until IS NULL', name='ck_auth_lockout_exclusive_deadline'
        ),
    )


def downgrade() -> None:
    # Discard lockout observation only; preserve users, MFA and existing policies.
    op.drop_table('authentication_account_lockouts')
    with op.batch_alter_table('authentication_security_policies') as batch:
        batch.drop_constraint('ck_auth_security_lockout_revision', type_='check')
        batch.drop_constraint('ck_auth_security_lockout_mode', type_='check')
        batch.drop_column('lockout_revision')
        batch.drop_column('lockout_mode')
