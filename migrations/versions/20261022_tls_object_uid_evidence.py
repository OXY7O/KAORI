"""Record Kubernetes TLS Secret object UID for lineage provenance (#2589).

Revision ID: 20261022_tls_object_uid
Revises: 20261022_vault_stored_certs

Existing TLS inventory rows intentionally remain NULL; namespace/name is
not an immutable source ID. Successful Kubernetes TLS collection populates
future object UID evidence without fetching or retaining any key material.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261022_tls_object_uid'
down_revision = '20261022_vault_stored_certs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tls_certificate_inventory',
        sa.Column('secret_uid', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('tls_certificate_inventory', 'secret_uid')
