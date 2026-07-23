"""Add persisted intelligence decision and execution workflow.

Revision ID: 20260723_decision_workflow
Revises: 20260722_foundation_cleanup
Create Date: 2026-07-23 15:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260723_decision_workflow'
down_revision = '20260722_foundation_cleanup'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'intelligence_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=64), nullable=False),
        sa.Column('recommendation_key', sa.String(length=255), nullable=False),
        sa.Column('rule_key', sa.String(length=255), nullable=False),
        sa.Column('rule_version', sa.String(length=80), nullable=False),
        sa.Column('knowledge_version', sa.String(length=120), nullable=True),
        sa.Column('action_key', sa.String(length=255), nullable=False),
        sa.Column('cluster_id', sa.String(length=80), nullable=True),
        sa.Column('namespace', sa.String(length=255), nullable=True),
        sa.Column('severity', sa.String(length=30), nullable=False),
        sa.Column('evidence_json', sa.JSON(), nullable=False),
        sa.Column('evidence_hash', sa.String(length=64), nullable=False),
        sa.Column('inventory_generation', sa.String(length=80), nullable=True),
        sa.Column('alert_fingerprint', sa.String(length=255), nullable=True),
        sa.Column('policy_outcome', sa.String(length=30), nullable=False),
        sa.Column('policy_reason', sa.String(length=500), nullable=False),
        sa.Column('approval_required', sa.Boolean(), nullable=False),
        sa.Column('workflow_status', sa.String(length=30), nullable=False),
        sa.Column('snapshot_json', sa.JSON(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "policy_outcome IN ('allowed', 'needs_approval', 'blocked')",
            name='ck_intelligence_decisions_policy_outcome',
        ),
        sa.CheckConstraint(
            "workflow_status IN ('ready', 'pending_approval', 'approved', 'rejected', 'expired', 'dispatched')",
            name='ck_intelligence_decisions_workflow_status',
        ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
    )
    op.create_index('ix_intelligence_decisions_recommendation_key', 'intelligence_decisions', ['recommendation_key'])
    op.create_index('ix_intelligence_decisions_rule_key', 'intelligence_decisions', ['rule_key'])
    op.create_index('ix_intelligence_decisions_action_key', 'intelligence_decisions', ['action_key'])
    op.create_index('ix_intelligence_decisions_cluster_id', 'intelligence_decisions', ['cluster_id'])
    op.create_index('ix_intelligence_decisions_namespace', 'intelligence_decisions', ['namespace'])
    op.create_index('ix_intelligence_decisions_severity', 'intelligence_decisions', ['severity'])
    op.create_index('ix_intelligence_decisions_evidence_hash', 'intelligence_decisions', ['evidence_hash'])
    op.create_index('ix_intelligence_decisions_alert_fingerprint', 'intelligence_decisions', ['alert_fingerprint'])
    op.create_index('ix_intelligence_decisions_policy_outcome', 'intelligence_decisions', ['policy_outcome'])
    op.create_index('ix_intelligence_decisions_workflow_status', 'intelligence_decisions', ['workflow_status'])
    op.create_index('ix_intelligence_decisions_created_by_user_id', 'intelligence_decisions', ['created_by_user_id'])
    op.create_index('ix_intelligence_decisions_expires_at', 'intelligence_decisions', ['expires_at'])
    op.create_index('ix_intelligence_decisions_status_created', 'intelligence_decisions', ['workflow_status', 'created_at'])
    op.create_index('ix_intelligence_decisions_cluster_status', 'intelligence_decisions', ['cluster_id', 'workflow_status'])

    op.create_table(
        'intelligence_decision_approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.Integer(), nullable=False),
        sa.Column('outcome', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.String(length=1000), nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('evidence_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("outcome IN ('approved', 'rejected')", name='ck_decision_approval_outcome'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['decision_id'], ['intelligence_decisions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('decision_id', name='uq_active_decision_approval'),
    )
    op.create_index('ix_intelligence_decision_approvals_decision_id', 'intelligence_decision_approvals', ['decision_id'])
    op.create_index('ix_intelligence_decision_approvals_actor_user_id', 'intelligence_decision_approvals', ['actor_user_id'])
    op.create_index('ix_decision_approvals_actor_created', 'intelligence_decision_approvals', ['actor_user_id', 'created_at'])

    op.create_table(
        'intelligence_execution_journal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('public_id', sa.String(length=64), nullable=False),
        sa.Column('decision_id', sa.Integer(), nullable=False),
        sa.Column('token_nonce_hash', sa.String(length=64), nullable=False),
        sa.Column('action_key', sa.String(length=255), nullable=False),
        sa.Column('evidence_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
        sa.Column('resolver_job_id', sa.Integer(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result_json', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('authorized', 'dispatched', 'succeeded', 'failed', 'canceled')",
            name='ck_intelligence_execution_status',
        ),
        sa.ForeignKeyConstraint(['decision_id'], ['intelligence_decisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolver_job_id'], ['job_executions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
        sa.UniqueConstraint('token_nonce_hash', name='uq_intelligence_execution_nonce'),
    )
    op.create_index('ix_intelligence_execution_journal_decision_id', 'intelligence_execution_journal', ['decision_id'])
    op.create_index('ix_intelligence_execution_journal_status', 'intelligence_execution_journal', ['status'])
    op.create_index('ix_intelligence_execution_journal_requested_by_user_id', 'intelligence_execution_journal', ['requested_by_user_id'])
    op.create_index('ix_intelligence_execution_journal_resolver_job_id', 'intelligence_execution_journal', ['resolver_job_id'])
    op.create_index('ix_intelligence_execution_journal_expires_at', 'intelligence_execution_journal', ['expires_at'])
    op.create_index('ix_intelligence_execution_decision_status', 'intelligence_execution_journal', ['decision_id', 'status'])
    op.create_index('ix_intelligence_execution_created', 'intelligence_execution_journal', ['created_at'])


def downgrade() -> None:
    op.drop_table('intelligence_execution_journal')
    op.drop_table('intelligence_decision_approvals')
    op.drop_table('intelligence_decisions')
