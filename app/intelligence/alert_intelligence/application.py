from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.delivery.notification_channels.contracts import NotificationMessage
from app.integrations.delivery.notification_channels.service import send_channel_preview_message
from app.intelligence.alert_intelligence.lifecycle import get_case
from app.intelligence.alert_intelligence.routing import RoutingPolicyConfig, upsert_routing_policy
from app.intelligence.alert_intelligence.templates import (
    render_template_preview,
    reset_template_override,
    upsert_template_override,
)
from app.models.alert_ops import (
    AlertCase,
    AlertNotificationTemplate,
    AlertRoutingPolicy,
)
from app.models.audit import AuditEvent
from app.models.notification_channel import NotificationChannel


def apply_case_mutation(
    public_id: str,
    *,
    operation: Callable[[AlertCase], object],
) -> AlertCase | None:
    case = get_case(public_id)
    if case is None:
        return None
    try:
        operation(case)
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return case


def save_routing_policy_command(
    *,
    policy_id: int | None,
    config: RoutingPolicyConfig,
    actor_user_id: int | None,
) -> AlertRoutingPolicy:
    try:
        row = upsert_routing_policy(
            policy_id=policy_id,
            config=config,
            actor_user_id=actor_user_id,
        )
        db.session.add(row)
        db.session.flush()
        _audit_governance(
            actor_user_id=actor_user_id,
            action='alert_routing_policy_updated',
            target_id=str(row.id),
            summary='Alert routing policy saved.',
            metadata={
                'name': row.name,
                'source_types': list(row.source_types_json or []),
                'domains': list(row.domains_json or []),
                'severities': list(row.severities_json or []),
                'channel_ids': list(row.channel_ids_json or []),
                'repeat_interval_minutes': row.repeat_interval_minutes,
                'acknowledgement_timeout_minutes': row.acknowledgement_timeout_minutes,
                'send_resolved': row.send_resolved,
            },
        )
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return row


def save_template_override_command(
    *,
    provider_key: str,
    event_state: str,
    name: str,
    subject_template: str | None,
    body_template: str,
    content_format: str,
    actor_user_id: int | None,
) -> AlertNotificationTemplate:
    try:
        row = upsert_template_override(
            provider_key=provider_key,
            event_state=event_state,
            name=name,
            subject_template=subject_template,
            body_template=body_template,
            content_format=content_format,
            actor_user_id=actor_user_id,
        )
        db.session.add(row)
        _audit_governance(
            actor_user_id=actor_user_id,
            action='alert_notification_template_updated',
            target_id=f'{row.provider_key}:{row.event_state}',
            summary='Alert notification template override saved.',
            metadata={'content_format': row.content_format},
        )
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return row


def reset_template_override_command(*, provider_key: str, event_state: str, actor_user_id: int | None) -> bool:
    try:
        changed = reset_template_override(provider_key=provider_key, event_state=event_state)
        if changed:
            _audit_governance(
                actor_user_id=actor_user_id,
                action='alert_notification_template_reset',
                target_id=f'{provider_key}:{event_state}',
                summary='Alert notification template reset to the immutable KAORI system template.',
            )
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return changed


def test_render_template_command(
    *,
    provider_key: str,
    event_state: str,
    subject_template: str | None,
    body_template: str,
    content_format: str,
) -> tuple[str, str]:
    """Validate and render the operator-edited template against canonical KAORI sample evidence."""
    return render_template_preview(
        provider_key=provider_key,
        event_state=event_state,
        subject_template=subject_template,
        body_template=body_template,
        content_format=content_format,
    )


def send_template_test_command(
    *,
    channel_id: int,
    provider_key: str,
    event_state: str,
    subject_template: str | None,
    body_template: str,
    content_format: str,
    actor_user_id: int | None,
) -> str:
    """Render and send a non-persistent template preview through one validated provider channel."""
    channel = NotificationChannel.query.filter_by(id=channel_id).first()
    if channel is None:
        raise ValueError('Select an available Notification Channel for Send Test.')
    if channel.provider_key != provider_key:
        raise ValueError('The selected Notification Channel does not match this template provider.')
    subject, body = render_template_preview(
        provider_key=provider_key,
        event_state=event_state,
        subject_template=subject_template,
        body_template=body_template,
        content_format=content_format,
    )
    result = send_channel_preview_message(
        channel,
        NotificationMessage(
            title=subject,
            body=body,
            severity='critical' if event_state == 'firing' else 'info',
            content_format=content_format,
        ),
    )
    try:
        _audit_governance(
            actor_user_id=actor_user_id,
            action='alert_notification_template_test_sent',
            target_id=f'{provider_key}:{event_state}',
            summary='Alert notification template test delivery requested.',
            metadata={
                'channel_id': channel.id,
                'channel_name': channel.name,
                'content_format': content_format,
                'success': result.success,
            },
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    if not result.success:
        raise ValueError(result.message)
    return result.message


def _audit_governance(
    *,
    actor_user_id: int | None,
    action: str,
    target_id: str,
    summary: str,
    metadata: dict[str, object] | None = None,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'alert_intelligence'
    event.target_id = target_id
    event.action = action
    event.summary = summary
    event.metadata_json = {'module': 'Alert Intelligence', **(metadata or {})}
    db.session.add(event)
