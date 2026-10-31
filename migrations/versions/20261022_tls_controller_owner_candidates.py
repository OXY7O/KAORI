"""Observe typed controller owner UID candidates on Kubernetes TLS Secrets.

Revision ID: 20261022_tls_controller_owner
Revises: 20261022_tls_object_uid

Source-owned Kubernetes ownerReferences only. NULL for legacy rows and
malformed observations; no name/annotation backfill and no Vault delivery claim.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261022_tls_controller_owner'
down_revision = '20261022_tls_object_uid'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tls_certificate_inventory',
        sa.Column('controller_owner_refs', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('tls_certificate_inventory', 'controller_owner_refs')
