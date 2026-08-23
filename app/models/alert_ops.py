from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions.db import db

if TYPE_CHECKING:
    from app.models.user import User


ALERT_CASE_OPEN_STATES = {'open', 'acknowledged', 'mitigating', 'verification_pending'}
ALERT_CASE_WORKFLOW_STATES = ALERT_CASE_OPEN_STATES | {'closed'}
ALERT_SOURCE_STATES = {'firing', 'resolved', 'unknown'}
ALERT_ROUTING_STATES = {'enabled', 'suppressed'}
ALERT_CLOSURE_REASONS = {'resolved', 'manual_withdrawal', 'source_decommissioned', 'false_positive', 'accepted_risk', 'superseded'}
ALERT_SOURCE_TYPES = {'provider_alert', 'recommendation'}
POSTMORTEM_STATES = {'not_required', 'required', 'draft', 'complete'}
RECOMMENDATION_ALERT_MODES = {'manual', 'automatic'}
RECOMMENDATION_ALERT_GROUPING_MODES = {'finding', 'rule_asset_scope', 'rule_asset'}
RULE_EXCEPTION_SCOPE_MODES = {'rule_asset', 'finding_keys'}


class AlertCase(db.Model):
    """Durable operator-owned lifecycle record for one alert occurrence."""

    __tablename__ = 'alert_cases'
    __table_args__ = (
        CheckConstraint(
            "source_state IN ('firing', 'resolved', 'unknown')",
            name='ck_alert_cases_source_state',
        ),
        CheckConstraint(
            "source_type IN ('provider_alert', 'recommendation')",
            name='ck_alert_cases_source_type',
        ),
        CheckConstraint(
            "routing_state IN ('enabled', 'suppressed')",
            name='ck_alert_cases_routing_state',
        ),
        CheckConstraint(
            "closure_reason IS NULL OR closure_reason IN ('resolved', 'manual_withdrawal', 'source_decommissioned', 'false_positive', 'accepted_risk', 'superseded')",
            name='ck_alert_cases_closure_reason',
        ),
        CheckConstraint(
            "workflow_state IN ('open', 'acknowledged', 'mitigating', 'verification_pending', 'closed')",
            name='ck_alert_cases_workflow_state',
        ),
        CheckConstraint(
            "postmortem_status IN ('not_required', 'required', 'draft', 'complete')",
            name='ck_alert_cases_postmortem_status',
        ),
        Index('ix_alert_cases_active_scope', 'domain', 'asset_key', 'workflow_state'),
        Index('ix_alert_cases_source_reference', 'source_type', 'source_ref'),
        Index('ix_alert_cases_rule_state', 'rule_key', 'workflow_state'),
        Index('ix_alert_cases_identity_state', 'case_key', 'workflow_state'),
        Index('ix_alert_cases_history', 'closed_at', 'severity'),
        Index('ix_alert_cases_source_changed', 'source_state', 'source_state_changed_at'),
        Index('ix_alert_cases_routing_state', 'routing_state', 'routing_override_reason'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(db.String(64), nullable=False, unique=True, default=lambda: str(uuid4()))
    case_key: Mapped[str] = mapped_column(db.String(96), nullable=False, index=True)
    fingerprint: Mapped[str | None] = mapped_column(db.String(160), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(db.String(32), nullable=False, default='recommendation', index=True)
    source_ref: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    rule_key: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    domain: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(db.String(80), nullable=False)
    asset_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    asset_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    alert_name: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(db.String(20), nullable=False, default='info', index=True)
    previous_severity: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    severity_changed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    source_state: Mapped[str] = mapped_column(db.String(24), nullable=False, default='firing', index=True)
    source_state_reason: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    source_state_changed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    routing_state: Mapped[str] = mapped_column(db.String(24), nullable=False, default='enabled', index=True)
    routing_override_reason: Mapped[str | None] = mapped_column(db.String(64), nullable=True, index=True)
    routing_override_note: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    routing_override_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    routing_override_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    workflow_state: Mapped[str] = mapped_column(db.String(32), nullable=False, default='open', index=True)
    closure_reason: Mapped[str | None] = mapped_column(db.String(40), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    target: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    namespace: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    receiver: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    labels_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)

    owner_user_id: Mapped[int | None] = mapped_column(db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    closed_by_user_id: Mapped[int | None] = mapped_column(db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    source_resolved_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    acknowledgement_expires_at: Mapped[datetime | None] = mapped_column(
        db.DateTime(timezone=True), nullable=True, index=True
    )
    mitigating_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    verification_started_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    last_firing_notified_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    last_resolved_notified_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)

    resolution_summary: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    remediation_steps_json: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    verification_evidence: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    change_reference: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    ticket_reference: Mapped[str | None] = mapped_column(db.String(255), nullable=True)

    postmortem_required: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    postmortem_status: Mapped[str] = mapped_column(db.String(24), nullable=False, default='not_required')
    postmortem_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)
    archive_artifact_id: Mapped[str | None] = mapped_column(db.String(36), nullable=True, index=True)
    archive_compacted_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    owner: Mapped[User | None] = relationship('User', foreign_keys=[owner_user_id])
    acknowledged_by: Mapped[User | None] = relationship('User', foreign_keys=[acknowledged_by_user_id])
    closed_by: Mapped[User | None] = relationship('User', foreign_keys=[closed_by_user_id])
    routing_override_by: Mapped[User | None] = relationship('User', foreign_keys=[routing_override_by_user_id])
    events: Mapped[list[AlertCaseEvent]] = relationship(
        'AlertCaseEvent', back_populates='case', cascade='all, delete-orphan', passive_deletes=True
    )
    silences: Mapped[list[AlertSilence]] = relationship(
        'AlertSilence', back_populates='case', cascade='all, delete-orphan', passive_deletes=True
    )


class AlertCaseEvent(db.Model):
    __tablename__ = 'alert_case_events'
    __table_args__ = (Index('ix_alert_case_events_case_created', 'case_id', 'created_at'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        db.ForeignKey('alert_cases.id', ondelete='CASCADE'), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    summary: Mapped[str] = mapped_column(db.String(500), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(db.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    case: Mapped[AlertCase] = relationship('AlertCase', back_populates='events')
    actor: Mapped[User | None] = relationship('User', foreign_keys=[actor_user_id])


class AlertSilence(db.Model):
    """KAORI delivery silence; intentionally separate from Alertmanager silences."""

    __tablename__ = 'alert_silences'
    __table_args__ = (Index('ix_alert_silences_case_active', 'case_id', 'ends_at', 'revoked_at'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        db.ForeignKey('alert_cases.id', ondelete='CASCADE'), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    ends_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(db.String(500), nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    case: Mapped[AlertCase] = relationship('AlertCase', back_populates='silences')
    created_by: Mapped[User | None] = relationship('User', foreign_keys=[created_by_user_id])
    revoked_by: Mapped[User | None] = relationship('User', foreign_keys=[revoked_by_user_id])


class AlertRoutingPolicy(db.Model):
    __tablename__ = 'alert_routing_policies'
    __table_args__ = (Index('ix_alert_routing_policies_enabled', 'enabled', 'name'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(160), nullable=False)
    enabled: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    domains_json: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    severities_json: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    source_types_json: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=lambda: ['recommendation'])
    matchers_json: Mapped[dict[str, str]] = mapped_column(db.JSON, nullable=False, default=dict)
    channel_ids_json: Mapped[list[int]] = mapped_column(db.JSON, nullable=False, default=list)
    repeat_interval_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=60)
    acknowledgement_timeout_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=60)
    send_resolved: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class AlertNotificationTemplate(db.Model):
    __tablename__ = 'alert_notification_templates'
    __table_args__ = (
        CheckConstraint("event_state IN ('firing', 'resolved')", name='ck_alert_notification_templates_state'),
        CheckConstraint(
            "content_format IN ('plain_text', 'markdown', 'html')",
            name='ck_alert_notification_templates_content_format',
        ),
        Index('ix_alert_notification_templates_provider_state', 'provider_key', 'event_state', 'enabled'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(160), nullable=False)
    provider_key: Mapped[str] = mapped_column(db.String(40), nullable=False)
    event_state: Mapped[str] = mapped_column(db.String(20), nullable=False)
    subject_template: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    body_template: Mapped[str] = mapped_column(db.Text, nullable=False)
    content_format: Mapped[str] = mapped_column(db.String(24), nullable=False, default='plain_text')
    enabled: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    built_in_override: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RecommendationAlertPolicy(db.Model):
    """Governed recommendation-to-alert escalation override for one catalog rule."""

    __tablename__ = 'recommendation_alert_policies'
    __table_args__ = (
        CheckConstraint(
            "mode IN ('manual', 'automatic')",
            name='ck_recommendation_alert_policies_mode',
        ),
        CheckConstraint(
            "grouping_mode IN ('finding', 'rule_asset_scope', 'rule_asset')",
            name='ck_recommendation_alert_policies_grouping',
        ),
        Index('ix_recommendation_alert_policies_enabled', 'eligible', 'mode'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_key: Mapped[str] = mapped_column(db.String(255), nullable=False, unique=True, index=True)
    eligible: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    mode: Mapped[str] = mapped_column(db.String(24), nullable=False, default='manual')
    stability_window_minutes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=10)
    minimum_occurrences: Mapped[int] = mapped_column(db.Integer, nullable=False, default=2)
    grouping_mode: Mapped[str] = mapped_column(db.String(32), nullable=False, default='finding')
    updated_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    updated_by: Mapped[User | None] = relationship('User', foreign_keys=[updated_by_user_id])


class RuleException(db.Model):
    """Time-bounded accepted-risk exception for one canonical Intelligence rule and asset."""

    __tablename__ = 'rule_exceptions'
    __table_args__ = (
        CheckConstraint(
            "scope_mode IN ('rule_asset', 'finding_keys')",
            name='ck_rule_exceptions_scope_mode',
        ),
        Index('ix_rule_exceptions_rule_asset', 'rule_key', 'asset_key'),
        Index('ix_rule_exceptions_expiry', 'expires_at', 'revoked_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(db.String(64), nullable=False, unique=True, default=lambda: str(uuid4()))
    rule_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    asset_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    scope_mode: Mapped[str] = mapped_column(db.String(32), nullable=False, default='finding_keys')
    finding_keys_json: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    reason: Mapped[str] = mapped_column(db.Text, nullable=False)
    risk_reference: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    starts_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    revocation_reason: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    owner: Mapped[User | None] = relationship('User', foreign_keys=[owner_user_id])
    created_by: Mapped[User | None] = relationship('User', foreign_keys=[created_by_user_id])
    revoked_by: Mapped[User | None] = relationship('User', foreign_keys=[revoked_by_user_id])


class RecommendationAlertState(db.Model):
    """Worker-owned observation state used for stability, recurrence, and clear detection."""

    __tablename__ = 'recommendation_alert_states'
    __table_args__ = (
        Index('ix_recommendation_alert_states_active_rule', 'active', 'rule_key'),
        Index('ix_recommendation_alert_states_case_active', 'alert_case_id', 'active'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_key: Mapped[str] = mapped_column(db.String(255), nullable=False, unique=True, index=True)
    rule_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(db.String(80), nullable=False, index=True)
    asset_key: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    namespace: Mapped[str | None] = mapped_column(db.String(255), nullable=True, index=True)
    grouping_fingerprint: Mapped[str] = mapped_column(db.String(160), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True, index=True)
    occurrence_count: Mapped[int] = mapped_column(db.Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    cleared_at: Mapped[datetime | None] = mapped_column(db.DateTime(timezone=True), nullable=True, index=True)
    evidence_hash: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    promotion_suppressed_until_clear: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    promotion_suppression_reason: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    rule_exception_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('rule_exceptions.id', ondelete='SET NULL'), nullable=True, index=True
    )
    alert_case_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('alert_cases.id', ondelete='SET NULL'), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    alert_case: Mapped[AlertCase | None] = relationship('AlertCase', foreign_keys=[alert_case_id])
    rule_exception: Mapped[RuleException | None] = relationship('RuleException', foreign_keys=[rule_exception_id])
