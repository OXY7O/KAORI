"""Add inactive independent SSH host trust revision evidence (#5185).

Revision ID: 20261124_auto_host_trust
Revises: 20261124_auto_cred_scope

No backfill, trust activation, credential access or SSH.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261124_auto_host_trust'
down_revision = '20261124_auto_cred_scope'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'automation_host_trust_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'assignment_id',
            sa.Integer(),
            sa.ForeignKey('automation_inventory_assignments.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('lifecycle_status', sa.String(20), nullable=False),
        sa.Column('host_revision', sa.String(64), nullable=False),
        sa.Column('reference_fingerprint', sa.String(64), nullable=False),
        sa.Column('address', sa.String(45), nullable=False),
        sa.Column('ssh_port', sa.Integer(), nullable=False),
        sa.Column('algorithm', sa.String(20), nullable=False),
        sa.Column('public_key', sa.String(128), nullable=False),
        sa.Column('host_key_digest', sa.String(71), nullable=False),
        sa.Column('source_kind', sa.String(40), nullable=False),
        sa.Column('evidence_ref', sa.String(160), nullable=False),
        sa.Column('requested_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('verified_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.UniqueConstraint('assignment_id', 'revision_number', name='uq_auto_host_trust_revision'),
        sa.CheckConstraint('revision_number > 0', name='ck_auto_host_trust_revision'),
        sa.CheckConstraint("lifecycle_status IN ('draft', 'active', 'revoked')", name='ck_auto_host_trust_state'),
        sa.CheckConstraint("algorithm = 'ssh-ed25519'", name='ck_auto_host_trust_algorithm'),
        sa.CheckConstraint('ssh_port BETWEEN 1 AND 65535', name='ck_auto_host_trust_port'),
        sa.CheckConstraint('length(host_revision) = 64', name='ck_auto_host_trust_host_revision'),
        sa.CheckConstraint('length(reference_fingerprint) = 64', name='ck_auto_host_trust_reference'),
        sa.CheckConstraint('length(host_key_digest) = 71', name='ck_auto_host_trust_key_digest'),
        sa.CheckConstraint(
            "lifecycle_status = 'revoked' OR effective_until > recorded_at", name='ck_auto_host_trust_window'
        ),
        sa.CheckConstraint("source_kind = 'independent_console'", name='ck_auto_host_trust_source'),
        sa.CheckConstraint("evidence_ref <> ''", name='ck_auto_host_trust_evidence'),
        sa.CheckConstraint(
            "lifecycle_status <> 'active' OR"
            ' (verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL'
            ' AND verified_by_user_id <> requested_by_user_id'
            ' AND verified_at <= recorded_at AND verified_at < effective_until)',
            name='ck_auto_host_trust_independent',
        ),
    )
    op.create_index(
        'ix_automation_host_trust_revisions_assignment_id', 'automation_host_trust_revisions', ['assignment_id']
    )


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.execute(sa.text('SELECT COUNT(*) FROM automation_host_trust_revisions')).scalar_one()
    if count:
        raise RuntimeError('Independent SSH trust revision evidence must be retained before downgrade.')
    op.drop_index('ix_automation_host_trust_revisions_assignment_id', table_name='automation_host_trust_revisions')
    op.drop_table('automation_host_trust_revisions')
