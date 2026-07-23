"""Add versioned knowledge runbook foundation.

Revision ID: 20260723_knowledge_runbooks
Revises: 20260723_resolver_orchestration
Create Date: 2026-07-23 19:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260723_knowledge_runbooks'
down_revision = '20260723_resolver_orchestration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'knowledge_runbooks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(64), nullable=False, unique=True),
        sa.Column('runbook_key', sa.String(255), nullable=False, unique=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('lifecycle_status', sa.String(30), nullable=False, server_default='active'),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("lifecycle_status IN ('active', 'deprecated', 'archived')", name='ck_knowledge_runbook_lifecycle'),
    )
    op.create_index('ix_knowledge_runbooks_runbook_key', 'knowledge_runbooks', ['runbook_key'])
    op.create_index('ix_knowledge_runbooks_status_updated', 'knowledge_runbooks', ['lifecycle_status', 'updated_at'])

    op.create_table(
        'knowledge_runbook_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(64), nullable=False, unique=True),
        sa.Column('runbook_id', sa.Integer(), sa.ForeignKey('knowledge_runbooks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.String(80), nullable=False),
        sa.Column('publication_status', sa.String(30), nullable=False, server_default='draft'),
        sa.Column('action_key', sa.String(255), nullable=False),
        sa.Column('resolver_key', sa.String(255), nullable=False),
        sa.Column('approval_policy', sa.String(30), nullable=False, server_default='needs_approval'),
        sa.Column('required_evidence_json', sa.JSON(), nullable=False),
        sa.Column('parameter_schema_json', sa.JSON(), nullable=False),
        sa.Column('steps_json', sa.JSON(), nullable=False),
        sa.Column('rollback_json', sa.JSON(), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('published_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("publication_status IN ('draft', 'published', 'withdrawn')", name='ck_runbook_revision_publication'),
        sa.CheckConstraint("approval_policy IN ('allowed', 'needs_approval', 'blocked')", name='ck_runbook_revision_approval_policy'),
        sa.UniqueConstraint('runbook_id', 'version', name='uq_runbook_revision_version'),
        sa.UniqueConstraint('content_hash', name='uq_runbook_revision_content_hash'),
    )
    op.create_index('ix_runbook_revisions_runbook_status', 'knowledge_runbook_revisions', ['runbook_id', 'publication_status'])
    op.create_index('ix_runbook_revisions_action_status', 'knowledge_runbook_revisions', ['action_key', 'publication_status'])

    with op.batch_alter_table('intelligence_decisions') as batch:
        batch.add_column(sa.Column('runbook_revision_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('runbook_key', sa.String(255), nullable=True))
        batch.add_column(sa.Column('runbook_version', sa.String(80), nullable=True))
        batch.add_column(sa.Column('runbook_content_hash', sa.String(64), nullable=True))
        batch.create_foreign_key('fk_intelligence_decision_runbook_revision', 'knowledge_runbook_revisions', ['runbook_revision_id'], ['id'], ondelete='RESTRICT')
        batch.create_index('ix_intelligence_decisions_runbook_revision_id', ['runbook_revision_id'])
        batch.create_index('ix_intelligence_decisions_runbook_key', ['runbook_key'])
        batch.create_index('ix_intelligence_decisions_runbook_content_hash', ['runbook_content_hash'])


def downgrade() -> None:
    with op.batch_alter_table('intelligence_decisions') as batch:
        batch.drop_index('ix_intelligence_decisions_runbook_content_hash')
        batch.drop_index('ix_intelligence_decisions_runbook_key')
        batch.drop_index('ix_intelligence_decisions_runbook_revision_id')
        batch.drop_constraint('fk_intelligence_decision_runbook_revision', type_='foreignkey')
        batch.drop_column('runbook_content_hash')
        batch.drop_column('runbook_version')
        batch.drop_column('runbook_key')
        batch.drop_column('runbook_revision_id')
    op.drop_index('ix_runbook_revisions_action_status', table_name='knowledge_runbook_revisions')
    op.drop_index('ix_runbook_revisions_runbook_status', table_name='knowledge_runbook_revisions')
    op.drop_table('knowledge_runbook_revisions')
    op.drop_index('ix_knowledge_runbooks_status_updated', table_name='knowledge_runbooks')
    op.drop_index('ix_knowledge_runbooks_runbook_key', table_name='knowledge_runbooks')
    op.drop_table('knowledge_runbooks')
