"""Add source-qualified GitHub webhook delivery replay ledger (SC-02 #2741).

Revision ID: 20261023_sc_webhook_delivery
Revises: 20261023_sc_app_credential

This table stores only authenticated delivery identity and digest, not raw
webhooks, credentials, source facts, or workflow history. It is inert until a
bounded authenticated ingress route and after-commit refresh dispatcher exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20261023_sc_webhook_delivery'
down_revision = '20261023_sc_app_credential'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'source_control_webhook_deliveries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('installation_id', sa.Integer(),
                  sa.ForeignKey('source_control_installations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('delivery_id', sa.String(36), nullable=False),
        sa.Column('payload_sha256', sa.String(64), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('action', sa.String(80), nullable=False),
        sa.Column('repository_native_id_hint', sa.String(80), nullable=True),
        sa.Column('processing_state', sa.String(30), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.UniqueConstraint('installation_id', 'delivery_id',
                            name='uq_sc_webhook_installation_delivery'),
    )
    op.create_index(
        'ix_sc_webhook_processing', 'source_control_webhook_deliveries',
        ['processing_state', 'received_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_sc_webhook_processing', table_name='source_control_webhook_deliveries')
    op.drop_table('source_control_webhook_deliveries')
