"""add cascade delete to prometheus config cluster fk

Revision ID: ee130522a645
Revises: ba9442ef5585
Create Date: 2026-06-26 07:10:25.179824

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ee130522a645'
down_revision = 'ba9442ef5585'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
