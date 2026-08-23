"""add rule exceptions and accepted-risk alert disposition

Revision ID: 20260823_rule_exceptions
Revises: 20260823_alert_signal_eval
Create Date: 2026-08-23
"""

import sqlalchemy as sa
from alembic import op

revision = '20260823_rule_exceptions'
down_revision = '20260823_alert_signal_eval'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rule_exceptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=64), nullable=False),
        sa.Column('rule_key', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=80), nullable=False),
        sa.Column('asset_key', sa.String(length=255), nullable=False),
        sa.Column('scope_mode', sa.String(length=32), nullable=False, server_default='finding_keys'),
        sa.Column('finding_keys_json', sa.JSON(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('risk_reference', sa.String(length=255), nullable=True),
        sa.Column('owner_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('revoked_by_user_id', sa.Integer(), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_mode IN ('rule_asset', 'finding_keys')",
            name='ck_rule_exceptions_scope_mode',
        ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['revoked_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
    )
    op.create_index('ix_rule_exceptions_rule_key', 'rule_exceptions', ['rule_key'])
    op.create_index('ix_rule_exceptions_domain', 'rule_exceptions', ['domain'])
    op.create_index('ix_rule_exceptions_asset_key', 'rule_exceptions', ['asset_key'])
    op.create_index('ix_rule_exceptions_risk_reference', 'rule_exceptions', ['risk_reference'])
    op.create_index('ix_rule_exceptions_starts_at', 'rule_exceptions', ['starts_at'])
    op.create_index('ix_rule_exceptions_expires_at', 'rule_exceptions', ['expires_at'])
    op.create_index('ix_rule_exceptions_revoked_at', 'rule_exceptions', ['revoked_at'])
    op.create_index('ix_rule_exceptions_rule_asset', 'rule_exceptions', ['rule_key', 'asset_key'])
    op.create_index('ix_rule_exceptions_expiry', 'rule_exceptions', ['expires_at', 'revoked_at'])

    op.add_column(
        'recommendation_alert_states',
        sa.Column('rule_exception_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_recommendation_alert_states_rule_exception_id',
        'recommendation_alert_states',
        'rule_exceptions',
        ['rule_exception_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_recommendation_alert_states_rule_exception_id',
        'recommendation_alert_states',
        ['rule_exception_id'],
    )

    op.drop_constraint('ck_alert_cases_closure_reason', 'alert_cases', type_='check')
    op.create_check_constraint(
        'ck_alert_cases_closure_reason',
        'alert_cases',
        "closure_reason IS NULL OR closure_reason IN ('resolved', 'manual_withdrawal', "
        "'source_decommissioned', 'false_positive', 'accepted_risk', 'superseded')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE alert_cases SET closure_reason = 'manual_withdrawal' "
        "WHERE closure_reason IN ('accepted_risk', 'superseded')"
    )
    op.drop_constraint('ck_alert_cases_closure_reason', 'alert_cases', type_='check')
    op.create_check_constraint(
        'ck_alert_cases_closure_reason',
        'alert_cases',
        "closure_reason IS NULL OR closure_reason IN ('resolved', 'manual_withdrawal', "
        "'source_decommissioned', 'false_positive')",
    )

    op.drop_index('ix_recommendation_alert_states_rule_exception_id', table_name='recommendation_alert_states')
    op.drop_constraint(
        'fk_recommendation_alert_states_rule_exception_id',
        'recommendation_alert_states',
        type_='foreignkey',
    )
    op.drop_column('recommendation_alert_states', 'rule_exception_id')

    op.drop_index('ix_rule_exceptions_expiry', table_name='rule_exceptions')
    op.drop_index('ix_rule_exceptions_rule_asset', table_name='rule_exceptions')
    op.drop_index('ix_rule_exceptions_revoked_at', table_name='rule_exceptions')
    op.drop_index('ix_rule_exceptions_expires_at', table_name='rule_exceptions')
    op.drop_index('ix_rule_exceptions_starts_at', table_name='rule_exceptions')
    op.drop_index('ix_rule_exceptions_risk_reference', table_name='rule_exceptions')
    op.drop_index('ix_rule_exceptions_asset_key', table_name='rule_exceptions')
    op.drop_index('ix_rule_exceptions_domain', table_name='rule_exceptions')
    op.drop_index('ix_rule_exceptions_rule_key', table_name='rule_exceptions')
    op.drop_table('rule_exceptions')
