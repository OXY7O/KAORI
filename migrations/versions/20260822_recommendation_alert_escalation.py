"""add recommendation alert escalation lifecycle

Revision ID: 20260822_reco_alert_escalation
Revises: 20260822_alert_operations
Create Date: 2026-08-22
"""

import sqlalchemy as sa
from alembic import op

revision = '20260822_reco_alert_escalation'
down_revision = '20260822_alert_operations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'alert_cases',
        sa.Column('source_type', sa.String(32), nullable=False, server_default='provider_alert'),
    )
    op.add_column('alert_cases', sa.Column('source_ref', sa.String(255), nullable=True))
    op.add_column('alert_cases', sa.Column('rule_key', sa.String(255), nullable=True))
    op.create_check_constraint(
        'ck_alert_cases_source_type',
        'alert_cases',
        "source_type IN ('provider_alert', 'recommendation')",
    )
    op.create_index('ix_alert_cases_source_type', 'alert_cases', ['source_type'])
    op.create_index('ix_alert_cases_source_ref', 'alert_cases', ['source_ref'])
    op.create_index('ix_alert_cases_rule_key', 'alert_cases', ['rule_key'])
    op.create_index('ix_alert_cases_source_reference', 'alert_cases', ['source_type', 'source_ref'])
    op.create_index('ix_alert_cases_rule_state', 'alert_cases', ['rule_key', 'workflow_state'])
    op.add_column(
        'alert_routing_policies',
        sa.Column(
            'source_types_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[\"provider_alert\"]'"),
        ),
    )

    op.create_table(
        'recommendation_alert_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rule_key', sa.String(255), nullable=False, unique=True),
        sa.Column('eligible', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('mode', sa.String(24), nullable=False, server_default='manual'),
        sa.Column('stability_window_minutes', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('minimum_occurrences', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('grouping_mode', sa.String(32), nullable=False, server_default='finding'),
        sa.Column('updated_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('manual', 'automatic')", name='ck_recommendation_alert_policies_mode'),
        sa.CheckConstraint(
            "grouping_mode IN ('finding', 'rule_asset_scope', 'rule_asset')",
            name='ck_recommendation_alert_policies_grouping',
        ),
    )
    op.create_index(
        'ix_recommendation_alert_policies_enabled',
        'recommendation_alert_policies',
        ['eligible', 'mode'],
    )
    op.create_index('ix_recommendation_alert_policies_rule_key', 'recommendation_alert_policies', ['rule_key'])

    op.create_table(
        'recommendation_alert_states',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('finding_key', sa.String(255), nullable=False, unique=True),
        sa.Column('rule_key', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(80), nullable=False),
        sa.Column('asset_key', sa.String(255), nullable=False),
        sa.Column('namespace', sa.String(255), nullable=True),
        sa.Column('grouping_fingerprint', sa.String(160), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cleared_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evidence_hash', sa.String(64), nullable=True),
        sa.Column('alert_case_id', sa.Integer(), sa.ForeignKey('alert_cases.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_recommendation_alert_states_active_rule',
        'recommendation_alert_states',
        ['active', 'rule_key'],
    )
    op.create_index(
        'ix_recommendation_alert_states_case_active',
        'recommendation_alert_states',
        ['alert_case_id', 'active'],
    )
    op.create_index('ix_recommendation_alert_states_finding_key', 'recommendation_alert_states', ['finding_key'])
    op.create_index('ix_recommendation_alert_states_rule_key', 'recommendation_alert_states', ['rule_key'])
    op.create_index('ix_recommendation_alert_states_domain', 'recommendation_alert_states', ['domain'])
    op.create_index('ix_recommendation_alert_states_asset_key', 'recommendation_alert_states', ['asset_key'])
    op.create_index('ix_recommendation_alert_states_namespace', 'recommendation_alert_states', ['namespace'])
    op.create_index(
        'ix_recommendation_alert_states_grouping_fingerprint',
        'recommendation_alert_states',
        ['grouping_fingerprint'],
    )
    op.create_index('ix_recommendation_alert_states_active', 'recommendation_alert_states', ['active'])
    op.create_index('ix_recommendation_alert_states_first_seen_at', 'recommendation_alert_states', ['first_seen_at'])
    op.create_index('ix_recommendation_alert_states_last_seen_at', 'recommendation_alert_states', ['last_seen_at'])
    op.create_index('ix_recommendation_alert_states_cleared_at', 'recommendation_alert_states', ['cleared_at'])
    op.create_index('ix_recommendation_alert_states_alert_case_id', 'recommendation_alert_states', ['alert_case_id'])


def downgrade() -> None:
    op.drop_table('recommendation_alert_states')
    op.drop_table('recommendation_alert_policies')
    op.drop_column('alert_routing_policies', 'source_types_json')
    op.drop_index('ix_alert_cases_rule_state', table_name='alert_cases')
    op.drop_index('ix_alert_cases_source_reference', table_name='alert_cases')
    op.drop_index('ix_alert_cases_rule_key', table_name='alert_cases')
    op.drop_index('ix_alert_cases_source_ref', table_name='alert_cases')
    op.drop_index('ix_alert_cases_source_type', table_name='alert_cases')
    op.drop_constraint('ck_alert_cases_source_type', 'alert_cases', type_='check')
    op.drop_column('alert_cases', 'rule_key')
    op.drop_column('alert_cases', 'source_ref')
    op.drop_column('alert_cases', 'source_type')
