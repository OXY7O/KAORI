"""add report templates

Revision ID: 20260705_report_templates
Revises: 20260704_report_owner_snap
Create Date: 2026-07-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '20260705_report_templates'
down_revision = '20260704_report_owner_snap'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'report_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('output_format', sa.String(length=50), nullable=False),
        sa.Column('sections', sa.JSON(), nullable=False),
        sa.Column('source_template_key', sa.String(length=150), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_by_username_snapshot', sa.String(length=100), nullable=True),
        sa.Column('created_by_display_name_snapshot', sa.String(length=150), nullable=True),
        sa.Column('created_by_auth_source_snapshot', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.create_index('ix_report_templates_name', ['name'], unique=False)
        batch_op.create_index('ix_report_templates_report_type', ['report_type'], unique=False)
        batch_op.create_index('ix_report_templates_status', ['status'], unique=False)
        batch_op.create_index('ix_report_templates_source_template_key', ['source_template_key'], unique=False)
        batch_op.create_index('ix_report_templates_created_by_id', ['created_by_id'], unique=False)
        batch_op.create_index('ix_report_templates_created_at', ['created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.drop_index('ix_report_templates_created_at')
        batch_op.drop_index('ix_report_templates_created_by_id')
        batch_op.drop_index('ix_report_templates_source_template_key')
        batch_op.drop_index('ix_report_templates_status')
        batch_op.drop_index('ix_report_templates_report_type')
        batch_op.drop_index('ix_report_templates_name')
    op.drop_table('report_templates')
