from __future__ import annotations

from celery import shared_task

from app.extensions.db import db
from app.integrations.runtime.notifications import (
    dispatch_integration_health_event,
    is_health_degradation,
)
from app.models.integration import IntegrationInstance
from app.models.runtime import IntegrationRuntimeObservation

from app.integrations.runtime.monitoring import dispatch_integration_runtime_refresh


@shared_task(
    bind=True,
    name='app.integrations.runtime.tasks.refresh_integration_runtime',
    acks_late=True,
    reject_on_worker_lost=True,
)
def refresh_integration_runtime(self) -> dict[str, object]:
    """Celery entrypoint for the canonical integration runtime dispatcher."""
    return dispatch_integration_runtime_refresh()


@shared_task(
    name='app.integrations.runtime.tasks.dispatch_integration_health_notification',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_integration_health_notification(observation_id: int) -> dict[str, object]:
    """Deliver only the latest committed transition for an active canonical instance."""
    observation = db.session.get(IntegrationRuntimeObservation, int(observation_id))
    if observation is None or observation.integration_instance_id is None:
        return {'status': 'skipped', 'reason': 'missing_canonical_observation'}
    instance = db.session.get(IntegrationInstance, observation.integration_instance_id)
    if (
        instance is None
        or not instance.enabled
        or instance.lifecycle_status != 'active'
        or instance.integration_type != observation.integration_type
    ):
        return {'status': 'skipped', 'reason': 'integration_not_active'}
    prior_query = IntegrationRuntimeObservation.query.filter_by(
        integration_instance_id=observation.integration_instance_id
    )
    latest = prior_query.order_by(IntegrationRuntimeObservation.id.desc()).first()
    if latest is None or latest.id != observation.id:
        return {'status': 'skipped', 'reason': 'stale_transition'}
    previous = prior_query.filter(
        IntegrationRuntimeObservation.id < observation.id
    ).order_by(IntegrationRuntimeObservation.id.desc()).first()
    if not is_health_degradation(previous, observation):
        return {'status': 'skipped', 'reason': 'not_healthy_to_degraded'}
    return {'status': 'completed', **dispatch_integration_health_event(observation)}
