from __future__ import annotations

from typing import Any, TypedDict, Unpack

from flask import url_for

from app.models.alertmanager import AlertmanagerInstance
from app.platform_operations.notifications.service import record_operational_activity


class _ActivityOptions(TypedDict, total=False):
    action_url: str | None
    action_label: str
    action_icon: str
    queue_feedback: bool


def record_instance_activity(
    *,
    user_id: int,
    instance: AlertmanagerInstance | None,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str,
    metadata: dict[str, Any] | None = None,
    **options: Unpack[_ActivityOptions],
) -> dict[str, Any]:
    action_url = options.get('action_url')
    action_label = options.get('action_label', 'Open Alertmanager Integration')
    action_icon = options.get('action_icon', 'siren')
    queue_feedback = options.get('queue_feedback', True)
    resolved_action_url = action_url or (
        url_for('alertmanager.instance_detail', instance_id=instance.id)
        if instance is not None and instance.id is not None
        else url_for('integrations.alertmanager')
    )
    payload = {
        'module': 'alertmanager',
        'instance_id': instance.id if instance is not None else None,
        'instance_name': instance.name if instance is not None else None,
        'deployment_type': instance.deployment_type if instance is not None else None,
    }
    payload.update(metadata or {})
    return record_operational_activity(
        user_id=user_id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=resolved_action_url,
        action_label=action_label,
        action_icon=action_icon,
        metadata=payload,
        queue_feedback=queue_feedback,
    )
