from __future__ import annotations

from typing import Any

from flask import current_app

from app.integrations.delivery.notification_channels.contracts import NotificationEvent, NotificationMessage
from app.integrations.delivery.notification_channels.service import dispatch_matching_notification_event
from app.models.runtime import IntegrationRuntimeObservation

HEALTH_DEGRADED_EVENT = 'integrations.health_degraded'


def is_health_degradation(previous: IntegrationRuntimeObservation | None, current: IntegrationRuntimeObservation) -> bool:
    """Only an observed healthy-to-unhealthy transition is a new outbound event."""
    return bool(
        previous is not None
        and previous.health_status == 'healthy'
        and current.health_status in {'degraded', 'unhealthy'}
    )


def build_integration_health_event(observation: IntegrationRuntimeObservation) -> NotificationEvent:
    """Normalize a committed observation, never send diagnostics or provider secrets."""
    if observation.id is None or observation.integration_instance_id is None:
        raise ValueError('Integration notification requires persisted canonical identity.')
    if observation.health_status not in {'degraded', 'unhealthy'}:
        raise ValueError('Only degraded/unhealthy source observations can be notified.')

    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '').strip().rstrip('/')
    action_path = '/integrations'
    severity = 'critical' if observation.health_status == 'unhealthy' else 'warning'
    message = NotificationMessage(
        title=f'Integration Health Degraded · {observation.integration_type}',
        body='\n'.join(
            (
                'A committed KAORI provider runtime observation changed from healthy.',
                f'Integration: {observation.integration_type}',
                f'Provider: {observation.provider_key}',
                f'Instance: {observation.instance_name}',
                f'Health: {observation.health_status}',
                'Review source evidence in Integrations; this event is not a provider outage assertion.',
            )
        ),
        severity=severity,
        action_url=f'{base_url}{action_path}' if base_url else action_path,
        action_label='Review Integration',
    )
    return NotificationEvent(
        domain='integrations',
        event_type=HEALTH_DEGRADED_EVENT,
        asset_type='integration_instance',
        asset_key=str(observation.integration_instance_id),
        severity=severity,
        event_key=f'{HEALTH_DEGRADED_EVENT}:{observation.id}',
        message=message,
        payload={
            'observation_id': observation.id,
            'integration_instance_id': observation.integration_instance_id,
            'integration_type': observation.integration_type,
            'provider_key': observation.provider_key,
            'health_status': observation.health_status,
        },
    )


def dispatch_integration_health_event(observation: IntegrationRuntimeObservation) -> dict[str, Any]:
    return dispatch_matching_notification_event(event=build_integration_health_event(observation))
