"""Bind Protected Reveal approvals to Kubernetes Secret object identity.

Revision ID: 20261011_reveal_uid
Revises: 20261011_capsule_proof

Existing pending/approved requests have no approved UID and are intentionally
ineligible for reveal. They must be re-requested. No migration is executed
until the explicit KAORI schema admission gate.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261011_reveal_uid'
down_revision = '20261011_capsule_proof'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'secret_reveal_requests',
        sa.Column('secret_uid', sa.String(length=255), nullable=True),
    )
    # Legacy rows cannot attest what Kubernetes object the request approved.
    op.execute(
        "UPDATE secret_reveal_requests SET status = 'expired' "
        "WHERE status IN ('pending', 'approved') AND secret_uid IS NULL"
    )


def downgrade() -> None:
    # Downgrade never reopens expired approvals.
    op.drop_column('secret_reveal_requests', 'secret_uid')
