"""add Harbor Registry provider connection

Revision ID: 20261003_registry_harbor
Revises: 20261001_tenant_cap_pod_storage
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = '20261003_registry_harbor'
down_revision = '20261001_tenant_cap_pod_storage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'harbor_instances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('auth_type', sa.String(length=30), nullable=False, server_default='basic'),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('password', sa.Text(), nullable=True),
        sa.Column('timeout', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('verify_ssl', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('detected_version', sa.String(length=64), nullable=True),
        sa.Column('compatibility_status', sa.String(length=40), nullable=True),
        sa.Column('compatibility_profile', sa.String(length=120), nullable=True),
        sa.Column('capability_profile', sa.String(length=120), nullable=True),
        sa.Column('capabilities', sa.JSON(), nullable=True),
        sa.Column('validation_summary', sa.JSON(), nullable=True),
        sa.Column('validation_message', sa.Text(), nullable=True),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['integration_instance_id'],
            ['integration_instances.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'integration_instance_id',
            name='uq_harbor_instances_integration_instance_id',
        ),
    )
    op.alter_column('harbor_instances', 'auth_type', server_default=None)
    op.alter_column('harbor_instances', 'timeout', server_default=None)
    op.alter_column('harbor_instances', 'verify_ssl', server_default=None)


def downgrade() -> None:
    op.drop_table('harbor_instances')
