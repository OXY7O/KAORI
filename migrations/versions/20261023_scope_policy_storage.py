"""Add inactive scoped-authorization policy/revision storage (#2723).

Revision ID: 20261023_scope_policy_storage
Revises: 20261022_tls_controller_owner

No grants, roles or evaluator are seeded; new sensitive reads remain denied.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_scope_policy_storage'
down_revision = '20261022_tls_controller_owner'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'access_scope_policies',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column(
            'principal_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'permission_key',
            sa.String(length=120),
            sa.ForeignKey('permissions.key', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'integration_instance_id',
            sa.Integer(),
            sa.ForeignKey('integration_instances.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('scope_level', sa.String(length=24), nullable=False),
        sa.Column('provider_namespace', sa.String(length=255), nullable=True),
        sa.Column('mount', sa.String(length=160), nullable=True),
        sa.Column('current_revision', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("scope_level IN ('instance', 'vault_mount')", name='ck_access_scope_policy_level'),
        sa.CheckConstraint(
            "(scope_level = 'instance' AND provider_namespace IS NULL AND mount IS NULL)"
            " OR (scope_level = 'vault_mount' AND provider_namespace IS NOT NULL"
            " AND mount IS NOT NULL AND mount <> '' AND mount NOT LIKE '%*%')",
            name='ck_access_scope_policy_exact_target',
        ),
        sa.CheckConstraint('current_revision > 0', name='ck_access_scope_policy_revision'),
    )
    op.create_index(
        'ix_access_scope_policy_principal_target',
        'access_scope_policies',
        ['principal_user_id', 'permission_key', 'integration_instance_id', 'scope_level'],
    )
    op.create_table(
        'access_scope_policy_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'policy_id',
            sa.String(length=36),
            sa.ForeignKey('access_scope_policies.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('lifecycle_status', sa.String(length=24), nullable=False),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'requested_by_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'approved_by_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='RESTRICT'),
            nullable=True,
        ),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('change_reason', sa.String(length=160), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('policy_id', 'revision_number', name='uq_access_scope_policy_revision'),
        sa.CheckConstraint(
            "lifecycle_status IN ('draft', 'active', 'suspended', 'revoked', 'expired', 'withdrawn')",
            name='ck_access_scope_revision_state',
        ),
        sa.CheckConstraint('revision_number > 0', name='ck_access_scope_revision_number'),
        sa.CheckConstraint('effective_until > effective_from', name='ck_access_scope_revision_window'),
        sa.CheckConstraint(
            "lifecycle_status <> 'active' OR"
            ' (approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL'
            ' AND approved_by_user_id <> requested_by_user_id)',
            name='ck_access_scope_revision_approved',
        ),
    )
    op.create_index(
        'ix_access_scope_policy_revisions_policy_id',
        'access_scope_policy_revisions',
        ['policy_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_access_scope_policy_revisions_policy_id', table_name='access_scope_policy_revisions')
    op.drop_table('access_scope_policy_revisions')
    op.drop_index('ix_access_scope_policy_principal_target', table_name='access_scope_policies')
    op.drop_table('access_scope_policies')
