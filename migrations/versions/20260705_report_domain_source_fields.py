"""add report domain and source fields

Revision ID: 20260705_report_domain
Revises: 20260705_report_schedules
Create Date: 2026-07-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '20260705_report_domain'
down_revision = '20260705_report_schedules'
branch_labels = None
depends_on = None


TABLES = ('reports', 'report_templates', 'report_schedules')


def upgrade() -> None:
    for table_name in TABLES:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'report_domain',
                    sa.String(length=50),
                    nullable=False,
                    server_default='kubereport',
                )
            )
            batch_op.add_column(
                sa.Column(
                    'source_kind',
                    sa.String(length=50),
                    nullable=False,
                    server_default='kubernetes',
                )
            )
            batch_op.create_index(f'ix_{table_name}_report_domain', ['report_domain'], unique=False)
            batch_op.create_index(f'ix_{table_name}_source_kind', ['source_kind'], unique=False)


def downgrade() -> None:
    for table_name in TABLES:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_index(f'ix_{table_name}_source_kind')
            batch_op.drop_index(f'ix_{table_name}_report_domain')
            batch_op.drop_column('source_kind')
            batch_op.drop_column('report_domain')
