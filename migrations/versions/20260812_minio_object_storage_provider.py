"""add provider-neutral object storage asset and MinIO provider connection

Revision ID: 20260812_minio_object_storage
Revises: 20260810_retire_welcome_view
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260812_minio_object_storage'
down_revision = '20260810_retire_welcome_view'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'object_storage_systems',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('environment', sa.String(length=40), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='unknown'),
        sa.Column('last_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_object_storage_system_name'),
    )
    op.create_table(
        'minio_instances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_instance_id', sa.Integer(), nullable=False),
        sa.Column('object_storage_system_id', sa.String(length=36), nullable=False),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('access_key', sa.String(length=255), nullable=False),
        sa.Column('secret_key', sa.Text(), nullable=False),
        sa.Column('region', sa.String(length=80), nullable=False, server_default='us-east-1'),
        sa.Column('addressing_style', sa.String(length=20), nullable=False, server_default='path'),
        sa.Column('timeout', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('verify_ssl', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('declared_release', sa.String(length=96), nullable=False),
        sa.Column('detected_product', sa.String(length=80), nullable=True),
        sa.Column('observed_server_header', sa.String(length=255), nullable=True),
        sa.Column('deployment_id', sa.String(length=255), nullable=True),
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
            name='fk_minio_instances_integration_instance',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['object_storage_system_id'],
            ['object_storage_systems.id'],
            name='fk_minio_instances_object_storage_system',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_instance_id', name='uq_minio_instance_integration_identity'),
        sa.UniqueConstraint('object_storage_system_id', name='uq_minio_instance_object_storage_system'),
    )


def downgrade() -> None:
    op.drop_table('minio_instances')
    op.drop_table('object_storage_systems')
