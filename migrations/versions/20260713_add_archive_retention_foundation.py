"""add reusable archive retention foundation

Revision ID: 20260713_archive_retention
Revises: 20260712_node_system_uuid
Create Date: 2026-07-13 10:00:00

"""
from alembic import op
import sqlalchemy as sa


revision: str = '20260713_archive_retention'
down_revision: str | None = '20260712_node_system_uuid'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'archive_artifacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('domain', sa.String(length=80), nullable=False),
        sa.Column('source_model', sa.String(length=120), nullable=False),
        sa.Column('trigger_type', sa.String(length=24), nullable=False),
        sa.Column('operation_mode', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('archive_format', sa.String(length=24), nullable=False),
        sa.Column('compression', sa.String(length=24), nullable=False),
        sa.Column('cutoff_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('range_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('range_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('boundary_record_id', sa.BigInteger(), nullable=True),
        sa.Column('record_count', sa.BigInteger(), nullable=False),
        sa.Column('cleanup_deleted_count', sa.BigInteger(), nullable=False),
        sa.Column('storage_backend', sa.String(length=24), nullable=True),
        sa.Column('data_object_key', sa.String(length=1024), nullable=True),
        sa.Column('manifest_object_key', sa.String(length=1024), nullable=True),
        sa.Column('data_uri', sa.String(length=1100), nullable=True),
        sa.Column('manifest_uri', sa.String(length=1100), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('manifest_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('manifest_checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cleanup_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('purged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_archive_artifacts_domain', 'archive_artifacts', ['domain'], unique=False)
    op.create_index('ix_archive_artifacts_status', 'archive_artifacts', ['status'], unique=False)
    op.create_index('ix_archive_artifacts_trigger_type', 'archive_artifacts', ['trigger_type'], unique=False)
    op.create_index('ix_archive_artifacts_storage_backend', 'archive_artifacts', ['storage_backend'], unique=False)
    op.create_index('ix_archive_artifacts_triggered_by_user_id', 'archive_artifacts', ['triggered_by_user_id'], unique=False)
    op.create_index('ix_archive_artifacts_celery_task_id', 'archive_artifacts', ['celery_task_id'], unique=False)
    op.create_index('ix_archive_artifacts_cutoff_at', 'archive_artifacts', ['cutoff_at'], unique=False)
    op.create_index('ix_archive_artifacts_completed_at', 'archive_artifacts', ['completed_at'], unique=False)
    op.create_index('ix_archive_artifacts_created_at', 'archive_artifacts', ['created_at'], unique=False)
    op.create_index('ix_archive_artifacts_checksum_sha256', 'archive_artifacts', ['checksum_sha256'], unique=False)
    op.create_index(
        'ix_archive_artifacts_domain_status_created',
        'archive_artifacts',
        ['domain', 'status', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_archive_artifacts_domain_completed',
        'archive_artifacts',
        ['domain', 'completed_at'],
        unique=False,
    )

    op.create_index('ix_notifications_created_id', 'notifications', ['created_at', 'id'], unique=False)
    op.create_index('ix_notifications_status_created', 'notifications', ['status', 'created_at'], unique=False)
    op.create_index('ix_notifications_user_created', 'notifications', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_notifications_event_created', 'notifications', ['event_type', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_notifications_event_created', table_name='notifications')
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_index('ix_notifications_status_created', table_name='notifications')
    op.drop_index('ix_notifications_created_id', table_name='notifications')

    op.drop_index('ix_archive_artifacts_domain_completed', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_domain_status_created', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_checksum_sha256', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_created_at', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_completed_at', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_cutoff_at', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_celery_task_id', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_triggered_by_user_id', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_storage_backend', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_trigger_type', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_status', table_name='archive_artifacts')
    op.drop_index('ix_archive_artifacts_domain', table_name='archive_artifacts')
    op.drop_table('archive_artifacts')
