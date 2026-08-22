from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.intelligence.alert_intelligence.lifecycle import get_case
from app.intelligence.alert_intelligence.routing import RoutingPolicyConfig, upsert_routing_policy
from app.intelligence.alert_intelligence.templates import upsert_template_override
from app.models.alert_ops import AlertCase, AlertNotificationTemplate, AlertRoutingPolicy
from app.models.audit import AuditEvent


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
    actor_user_id: int | None,
) -> AlertNotificationTemplate:
    try:
        row = upsert_template_override(
            provider_key=provider_key,
            event_state=event_state,
            name=name,
            subject_template=subject_template,
            body_template=body_template,
            actor_user_id=actor_user_id,
        )
        db.session.add(row)
        _audit_governance(
            actor_user_id=actor_user_id,
            action='alert_notification_template_updated',
            target_id=f'{row.provider_key}:{row.event_state}',
            summary='Alert notification template override saved.',
        )
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        raise
    return row


def _audit_governance(
    *,
    actor_user_id: int | None,
    action: str,
    target_id: str,
    summary: str,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'alert_intelligence'
    event.target_id = target_id
    event.action = action
    event.summary = summary
    event.metadata_json = {'module': 'Alert Intelligence'}
    db.session.add(event)
