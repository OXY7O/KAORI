"""decision candidate review and promotion workflow

Revision ID: 20260723_candidate_review
Revises: 20260723_alert_runbook_matching
"""

from alembic import op
import sqlalchemy as sa

revision = '20260723_candidate_review'
down_revision = '20260723_alert_runbook_matching'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'intelligence_decision_candidates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(length=64), nullable=False, unique=True),
        sa.Column('binding_id', sa.Integer(), nullable=False),
        sa.Column('runbook_revision_id', sa.Integer(), nullable=False),
        sa.Column('deduplication_key', sa.String(length=64), nullable=False),
        sa.Column('rule_key', sa.String(length=255), nullable=True),
        sa.Column('alert_fingerprint', sa.String(length=255), nullable=True),
        sa.Column('cluster_id', sa.String(length=255), nullable=True),
        sa.Column('namespace', sa.String(length=255), nullable=True),
        sa.Column('severity', sa.String(length=30), nullable=False, server_default='info'),
        sa.Column('evidence_json', sa.JSON(), nullable=False),
        sa.Column('evidence_hash', sa.String(length=64), nullable=False),
        sa.Column('candidate_json', sa.JSON(), nullable=False),
        sa.Column('review_status', sa.String(length=30), nullable=False, server_default='pending'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('review_reason', sa.String(length=1000), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('promoted_decision_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "review_status IN ('pending', 'promoted', 'dismissed', 'expired')",
            name='ck_intelligence_candidate_review_status',
        ),
        sa.ForeignKeyConstraint(['binding_id'], ['knowledge_runbook_alert_bindings.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['runbook_revision_id'], ['knowledge_runbook_revisions.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['promoted_decision_id'], ['intelligence_decisions.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('deduplication_key', name='uq_intelligence_candidate_deduplication'),
        sa.UniqueConstraint('promoted_decision_id'),
    )
    op.create_index(
        'ix_intelligence_candidates_status_expires', 'intelligence_decision_candidates', ['review_status', 'expires_at']
    )
    op.create_index(
        'ix_intelligence_candidates_alert_created',
        'intelligence_decision_candidates',
        ['alert_fingerprint', 'created_at'],
    )
    for column in (
        'binding_id',
        'runbook_revision_id',
        'rule_key',
        'alert_fingerprint',
        'cluster_id',
        'namespace',
        'evidence_hash',
        'review_status',
        'expires_at',
    ):
        op.create_index(f'ix_intelligence_decision_candidates_{column}', 'intelligence_decision_candidates', [column])


def downgrade() -> None:
    op.drop_table('intelligence_decision_candidates')
