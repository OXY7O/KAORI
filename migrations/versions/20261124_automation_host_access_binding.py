"""Introduce reference-only host access binding (#5162).

Revision ID: 20261124_auto_host_access
Revises: 20261123_automation_hosts

No secret values, verified trust, provider access or execution grants.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261124_auto_host_access'
down_revision = '20261123_automation_hosts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'automation_host_access_bindings',
        sa.Column(
            'assignment_id',
            sa.Integer(),
            sa.ForeignKey('automation_inventory_assignments.id', ondelete='RESTRICT'),
            primary_key=True,
        ),
        sa.Column(
            'secret_representation_id',
            sa.Integer(),
            sa.ForeignKey('secrets_pki_secret_representations.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('secret_version', sa.Integer(), nullable=False),
        sa.Column('host_revision', sa.String(64), nullable=False),
        sa.Column('reference_fingerprint', sa.String(64), nullable=False),
        sa.Column('host_key_digest', sa.String(71), nullable=False),
        sa.Column(
            'recorded_by_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('secret_version > 0', name='ck_auto_host_access_version'),
        sa.CheckConstraint('length(host_revision) = 64', name='ck_auto_host_access_revision'),
        sa.CheckConstraint('length(reference_fingerprint) = 64', name='ck_auto_host_access_fingerprint'),
        sa.CheckConstraint('length(host_key_digest) = 71', name='ck_auto_host_access_key_digest'),
    )
    op.create_index(
        'ix_automation_host_access_bindings_secret_representation_id',
        'automation_host_access_bindings',
        ['secret_representation_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_automation_host_access_bindings_secret_representation_id', table_name='automation_host_access_bindings'
    )
    op.drop_table('automation_host_access_bindings')
