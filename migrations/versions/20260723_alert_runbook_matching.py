"""alert to runbook matching foundation

Revision ID: 20260723_alert_runbook_matching
Revises: 20260723_runbook_validation
"""
from alembic import op
import sqlalchemy as sa

revision = '20260723_alert_runbook_matching'
down_revision = '20260723_runbook_validation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'knowledge_runbook_alert_bindings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(length=64), nullable=False, unique=True),
        sa.Column('binding_key', sa.String(length=255), nullable=False),
        sa.Column('runbook_revision_id', sa.Integer(), nullable=False),
        sa.Column('rule_key', sa.String(length=255), nullable=True),
        sa.Column('alertname', sa.String(length=255), nullable=True),
        sa.Column('cluster_id', sa.String(length=255), nullable=True),
        sa.Column('namespace', sa.String(length=255), nullable=True),
        sa.Column('required_labels_json', sa.JSON(), nullable=False),
        sa.Column('evidence_mapping_json', sa.JSON(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('lifecycle_status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("lifecycle_status IN ('active', 'disabled')", name='ck_runbook_alert_binding_lifecycle'),
        sa.ForeignKeyConstraint(['runbook_revision_id'], ['knowledge_runbook_revisions.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('binding_key', name='uq_runbook_alert_binding_key'),
    )
    op.create_index('ix_runbook_alert_binding_rule_active', 'knowledge_runbook_alert_bindings', ['rule_key', 'lifecycle_status'])
    op.create_index('ix_runbook_alert_binding_alert_active', 'knowledge_runbook_alert_bindings', ['alertname', 'lifecycle_status'])
    op.create_index('ix_knowledge_runbook_alert_bindings_revision', 'knowledge_runbook_alert_bindings', ['runbook_revision_id'])


def downgrade() -> None:
    op.drop_index('ix_knowledge_runbook_alert_bindings_revision', table_name='knowledge_runbook_alert_bindings')
    op.drop_index('ix_runbook_alert_binding_alert_active', table_name='knowledge_runbook_alert_bindings')
    op.drop_index('ix_runbook_alert_binding_rule_active', table_name='knowledge_runbook_alert_bindings')
    op.drop_table('knowledge_runbook_alert_bindings')
