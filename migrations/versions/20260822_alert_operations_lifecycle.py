"""add alert operations lifecycle

Revision ID: 20260822_alert_operations
Revises: 20260820_obj_analytics_snapshot
Create Date: 2026-08-22
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '20260822_alert_operations'
down_revision = '20260820_obj_analytics_snapshot'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'alert_cases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('public_id', sa.String(64), nullable=False, unique=True),
        sa.Column('case_key', sa.String(96), nullable=False),
        sa.Column('fingerprint', sa.String(160)),
        sa.Column('domain', sa.String(80), nullable=False),
        sa.Column('asset_type', sa.String(80), nullable=False),
        sa.Column('asset_key', sa.String(255), nullable=False),
        sa.Column('asset_name', sa.String(255), nullable=False),
        sa.Column('alert_name', sa.String(255), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, server_default='info'),
        sa.Column('source_state', sa.String(24), nullable=False, server_default='firing'),
        sa.Column('workflow_state', sa.String(32), nullable=False, server_default='open'),
        sa.Column('summary', sa.Text()),
        sa.Column('target', sa.String(255)),
        sa.Column('namespace', sa.String(255)),
        sa.Column('receiver', sa.String(255)),
        sa.Column('labels_json', sa.JSON(), nullable=False),
        sa.Column('evidence_json', sa.JSON(), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('acknowledged_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('closed_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_resolved_at', sa.DateTime(timezone=True)),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True)),
        sa.Column('mitigating_at', sa.DateTime(timezone=True)),
        sa.Column('verification_started_at', sa.DateTime(timezone=True)),
        sa.Column('closed_at', sa.DateTime(timezone=True)),
        sa.Column('last_firing_notified_at', sa.DateTime(timezone=True)),
        sa.Column('last_resolved_notified_at', sa.DateTime(timezone=True)),
        sa.Column('resolution_summary', sa.Text()),
        sa.Column('remediation_steps_json', sa.JSON(), nullable=False),
        sa.Column('verification_evidence', sa.Text()),
        sa.Column('change_reference', sa.String(255)),
        sa.Column('ticket_reference', sa.String(255)),
        sa.Column('postmortem_required', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('postmortem_status', sa.String(24), nullable=False, server_default='not_required'),
        sa.Column('postmortem_json', sa.JSON(), nullable=False),
        sa.Column('archive_artifact_id', sa.String(36)),
        sa.Column('archive_compacted_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source_state IN ('firing', 'resolved')", name='ck_alert_cases_source_state'),
        sa.CheckConstraint(
            "workflow_state IN ('open', 'acknowledged', 'mitigating', 'verification_pending', 'closed')",
            name='ck_alert_cases_workflow_state',
        ),
        sa.CheckConstraint(
            "postmortem_status IN ('not_required', 'required', 'draft', 'complete')",
            name='ck_alert_cases_postmortem_status',
        ),
    )
    op.create_index('ix_alert_cases_active_scope', 'alert_cases', ['domain', 'asset_key', 'workflow_state'])
    op.create_index('ix_alert_cases_identity_state', 'alert_cases', ['case_key', 'workflow_state'])
    op.create_index('ix_alert_cases_history', 'alert_cases', ['closed_at', 'severity'])
    op.create_index('ix_alert_cases_fingerprint', 'alert_cases', ['fingerprint'])
    op.create_index('ix_alert_cases_alert_name', 'alert_cases', ['alert_name'])
    op.create_index('ix_alert_cases_first_seen_at', 'alert_cases', ['first_seen_at'])
    op.create_index('ix_alert_cases_last_seen_at', 'alert_cases', ['last_seen_at'])
    op.create_index('ix_alert_cases_source_resolved_at', 'alert_cases', ['source_resolved_at'])
    op.create_index('ix_alert_cases_closed_at', 'alert_cases', ['closed_at'])
    op.create_index('ix_alert_cases_archive_artifact_id', 'alert_cases', ['archive_artifact_id'])
    op.create_index('ix_alert_cases_archive_compacted_at', 'alert_cases', ['archive_compacted_at'])

    op.create_table(
        'alert_case_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('alert_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(80), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('summary', sa.String(500), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_alert_case_events_case_created', 'alert_case_events', ['case_id', 'created_at'])
    op.create_index('ix_alert_case_events_event_type', 'alert_case_events', ['event_type'])

    op.create_table(
        'alert_silences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('alert_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('revoked_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_alert_silences_case_active', 'alert_silences', ['case_id', 'ends_at', 'revoked_at'])

    op.create_table(
        'alert_routing_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('domains_json', sa.JSON(), nullable=False),
        sa.Column('severities_json', sa.JSON(), nullable=False),
        sa.Column('matchers_json', sa.JSON(), nullable=False),
        sa.Column('channel_ids_json', sa.JSON(), nullable=False),
        sa.Column('repeat_interval_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('send_resolved', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('updated_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_alert_routing_policies_enabled', 'alert_routing_policies', ['enabled', 'name'])

    op.create_table(
        'alert_notification_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('provider_key', sa.String(40), nullable=False),
        sa.Column('event_state', sa.String(20), nullable=False),
        sa.Column('subject_template', sa.String(500)),
        sa.Column('body_template', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('built_in_override', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_state IN ('firing', 'resolved')", name='ck_alert_notification_templates_state'),
    )
    op.create_index(
        'ix_alert_notification_templates_provider_state',
        'alert_notification_templates',
        ['provider_key', 'event_state', 'enabled'],
    )

    bind = op.get_bind()
    policies = sa.table(
        'data_lifecycle_policies',
        sa.column('domain', sa.String),
        sa.column('enabled', sa.Boolean),
        sa.column('hot_retention_days', sa.Integer),
        sa.column('archive_retention_days', sa.Integer),
        sa.column('batch_size', sa.Integer),
        sa.column('operation_mode', sa.String),
        sa.column('schedule_enabled', sa.Boolean),
        sa.column('schedule_hour', sa.Integer),
        sa.column('schedule_minute', sa.Integer),
        sa.column('protect_unreviewed', sa.Boolean),
        sa.column('protected_max_days', sa.Integer),
        sa.column('settings_json', sa.JSON),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    exists = bind.execute(sa.select(policies.c.domain).where(policies.c.domain == 'alert_incident')).scalar()
    if exists is None:
        now = datetime.now(UTC)
        bind.execute(
            policies.insert().values(
                domain='alert_incident',
                enabled=True,
                hot_retention_days=90,
                archive_retention_days=730,
                batch_size=1000,
                operation_mode='archive_and_cleanup',
                schedule_enabled=True,
                schedule_hour=4,
                schedule_minute=45,
                protect_unreviewed=False,
                protected_max_days=None,
                settings_json={
                    'closed_cases_only': True,
                    'preserve_searchable_case_index': True,
                    'archive_timeline': True,
                    'archive_notification_delivery': True,
                    'archive_postmortem': True,
                },
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_table('alert_notification_templates')
    op.drop_table('alert_routing_policies')
    op.drop_table('alert_silences')
    op.drop_table('alert_case_events')
    op.drop_table('alert_cases')
