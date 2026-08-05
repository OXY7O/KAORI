from __future__ import annotations

from typing import Any, NotRequired, TypedDict, Unpack

from flask import request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.notifications.feedback import OperationalDeliveryPolicy
from app.notifications.service import (
    create_transient_feedback,
    get_navigation_notification_context,
    record_operational_activity,
)


def notification_response_context(feedback: dict[str, Any]) -> dict[str, Any]:
    return {
        **feedback,
        'notification_context': get_navigation_notification_context(user_id=current_user.id),
    }


class SecretActivityOptions(TypedDict):
    detail: NotRequired[str | None]
    action_url: NotRequired[str | None]
    action_label: NotRequired[str]
    metadata: NotRequired[dict[str, Any] | None]
    queue_feedback: NotRequired[bool]
    delivery_policy: NotRequired[OperationalDeliveryPolicy | str]
    transient: NotRequired[bool]


_PERSISTENT_EVENT_SUFFIXES = (
    '_deleted',
    '_rotation',
    '_bulk_rotation',
    '_approval_required',
    '_requested',
    '_approved',
    '_denied',
    '_request_failed',
    '_decision_failed',
    '_duplicate_request_blocked',
    '_reauthentication_failed',
)


def _default_delivery_policy(event_type: str) -> OperationalDeliveryPolicy:
    if event_type.endswith(_PERSISTENT_EVENT_SUFFIXES):
        return OperationalDeliveryPolicy.PERSISTENT
    if event_type == 'kubernetes_secret_revealed':
        return OperationalDeliveryPolicy.AUDIT_ONLY
    return OperationalDeliveryPolicy.DECK_ON_FAILURE


def record_secret_activity(
    event_type: str,
    status: str,
    title: str,
    message: str,
    **options: Unpack[SecretActivityOptions],
) -> dict[str, Any]:
    metadata = options.get('metadata') or {}
    is_validation = (
        options.get('transient', False)
        or event_type.endswith('_validated')
        or 'validation' in event_type
        or metadata.get('operation') == 'validation'
    )
    action_url = options.get('action_url') or url_for('kubernetes_operations.secret_management')
    action_label = options.get('action_label', 'Open Secret Management')
    queue_feedback = options.get('queue_feedback', False)

    if is_validation:
        return create_transient_feedback(
            status=status,
            title=title,
            message=message,
            detail=options.get('detail'),
            action_url=action_url,
            action_label=action_label,
            action_icon='key',
            queue_feedback=queue_feedback,
        )

    delivery_policy = options.get('delivery_policy') or _default_delivery_policy(event_type)
    return record_operational_activity(
        user_id=current_user.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=options.get('detail'),
        action_url=action_url,
        action_label=action_label,
        action_icon='key',
        metadata={
            **metadata,
            'feedback_delivery': 'toast',
            'operation_domain': 'kubernetes_secrets',
        },
        queue_feedback=queue_feedback,
        delivery_policy=delivery_policy,
    )


def validate_secret_operation_csrf() -> None:
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError as exc:
        raise ValueError('The security token is missing or expired. Refresh the page and retry.') from exc
