from __future__ import annotations

from typing import Any

from flask import url_for

from app.models.alertmanager import AlertmanagerInstance
from app.notifications.service import record_operational_activity


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
    queue_feedback: bool = True,
) -> dict[str, Any]:
    action_url = (
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
        action_url=action_url,
        action_label='Open Alertmanager integration',
        action_icon='siren',
        metadata=payload,
        queue_feedback=queue_feedback,
    )
