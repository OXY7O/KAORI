"""add provider-neutral scope selectors and binding validation evidence

Revision ID: 20260720_binding_selectors
Revises: 20260719_cutover_p2
Create Date: 2026-07-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260720_binding_selectors'
down_revision = '20260719_cutover_p2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('integration_bindings', sa.Column('selector_json', sa.JSON(), nullable=True))
    op.add_column('integration_bindings', sa.Column('validation_status', sa.String(length=40), nullable=True))
    op.add_column('integration_bindings', sa.Column('validation_message', sa.Text(), nullable=True))
    op.add_column('integration_bindings', sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        'ix_integration_bindings_validation',
        'integration_bindings',
        ['asset_type', 'validation_status'],
        unique=False,
    )
    op.execute(
        """
        UPDATE integration_bindings
        SET validation_status = 'legacy_unscoped',
            validation_message = 'Existing binding retained without a scope selector. Add a selector before sharing one source across multiple assets.'
        WHERE validation_status IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index('ix_integration_bindings_validation', table_name='integration_bindings')
    op.drop_column('integration_bindings', 'last_validated_at')
    op.drop_column('integration_bindings', 'validation_message')
    op.drop_column('integration_bindings', 'validation_status')
    op.drop_column('integration_bindings', 'selector_json')
