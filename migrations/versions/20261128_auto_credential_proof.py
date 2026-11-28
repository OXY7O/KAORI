"""Bind credential proof to canonical Access revision (#5184)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261128_auto_credential_proof'
down_revision = '20261128_openbao_mount_scope'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('access_scope_policy_revisions') as batch:
        batch.add_column(sa.Column('credential_evidence_ref', sa.String(64), nullable=True))
        batch.create_check_constraint(
            'ck_access_scope_revision_credential_proof',
            "credential_evidence_ref IS NULL OR (lifecycle_status = 'active'"
            ' AND length(credential_evidence_ref) = 64)',
        )


def downgrade() -> None:
    count = op.get_bind().execute(
        sa.text('SELECT COUNT(*) FROM access_scope_policy_revisions WHERE credential_evidence_ref IS NOT NULL')
    ).scalar_one()
    if count:
        raise RuntimeError('Approved credential evidence history must be retained before downgrade.')
    with op.batch_alter_table('access_scope_policy_revisions') as batch:
        batch.drop_constraint('ck_access_scope_revision_credential_proof', type_='check')
        batch.drop_column('credential_evidence_ref')
