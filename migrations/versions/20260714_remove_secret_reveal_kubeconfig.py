"""remove dedicated secret reveal kubeconfig

Revision ID: 20260714_single_kubeconfig
Revises: 20260714_secret_reveal
Create Date: 2026-07-14 16:00:00
"""

from alembic import op
import sqlalchemy as sa

revision: str = '20260714_single_kubeconfig'
down_revision: str | None = '20260714_secret_reveal'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('clusters', 'secret_reveal_kubeconfig')


def downgrade() -> None:
    op.add_column('clusters', sa.Column('secret_reveal_kubeconfig', sa.Text(), nullable=True))
