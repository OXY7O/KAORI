"""lock KAORI alert management lifecycle foundation

Revision ID: 20260822_alert_mgmt_foundation
Revises: 20260822_reco_alert_escalation
Create Date: 2026-08-22
"""

import sqlalchemy as sa
from alembic import op

revision = '20260822_alert_mgmt_foundation'
down_revision = '20260822_reco_alert_escalation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('alert_cases', sa.Column('previous_severity', sa.String(20), nullable=True))
    op.add_column('alert_cases', sa.Column('severity_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alert_cases', sa.Column('acknowledgement_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_alert_cases_severity_changed_at', 'alert_cases', ['severity_changed_at'])
    op.create_index('ix_alert_cases_acknowledgement_expires_at', 'alert_cases', ['acknowledgement_expires_at'])
    op.alter_column(
        'alert_cases',
        'source_type',
        existing_type=sa.String(32),
        existing_nullable=False,
        server_default='recommendation',
    )

    op.add_column(
        'alert_routing_policies',
        sa.Column('acknowledgement_timeout_minutes', sa.Integer(), nullable=False, server_default='60'),
    )
    op.alter_column(
        'alert_routing_policies',
        'source_types_json',
        existing_type=sa.JSON(),
        existing_nullable=False,
        server_default=sa.text('\'["recommendation"]\''),
    )
    routing = sa.table(
        'alert_routing_policies',
        sa.column('source_types_json', sa.JSON()),
    )
    op.execute(routing.update().values(source_types_json=['recommendation']))

    op.add_column(
        'alert_notification_templates',
        sa.Column('content_format', sa.String(24), nullable=False, server_default='plain_text'),
    )
    op.create_check_constraint(
        'ck_alert_notification_templates_content_format',
        'alert_notification_templates',
        "content_format IN ('plain_text', 'markdown', 'html')",
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_alert_notification_templates_content_format',
        'alert_notification_templates',
        type_='check',
    )
    op.drop_column('alert_notification_templates', 'content_format')

    op.alter_column(
        'alert_routing_policies',
        'source_types_json',
        existing_type=sa.JSON(),
        existing_nullable=False,
        server_default=sa.text('\'["provider_alert"]\''),
    )
    op.drop_column('alert_routing_policies', 'acknowledgement_timeout_minutes')

    op.alter_column(
        'alert_cases',
        'source_type',
        existing_type=sa.String(32),
        existing_nullable=False,
        server_default='provider_alert',
    )
    op.drop_index('ix_alert_cases_acknowledgement_expires_at', table_name='alert_cases')
    op.drop_index('ix_alert_cases_severity_changed_at', table_name='alert_cases')
    op.drop_column('alert_cases', 'acknowledgement_expires_at')
    op.drop_column('alert_cases', 'severity_changed_at')
    op.drop_column('alert_cases', 'previous_severity')
