from __future__ import annotations

from celery import shared_task
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.automation_control.candidates import materialize_active_alert_candidates
from app.automation_control.notifications import (
    DECISION_NOTIFICATION_EVENTS,
    dispatch_decision_notification,
)
from app.extensions.db import db
from app.intelligence.workflow import expire_stale_decisions
from app.knowledge.candidate_review import expire_stale_candidates
from app.models.intelligence import IntelligenceDecision
from app.notification_channels.config import notification_delivery_max_attempts
from app.resolver.orchestration import expire_stale_execution_authorizations


@shared_task(
    bind=True,
    name='app.automation_control.tasks.dispatch_automation_decision_notification',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_automation_decision_notification(self, decision_id: int, event_type: str) -> dict[str, object]:
    """Deliver a persisted Automation Control decision event through matching platform channels."""
    if event_type not in DECISION_NOTIFICATION_EVENTS:
        return {'status': 'skipped', 'reason': 'unsupported_event_type', 'event_type': event_type}
    decision = db.session.get(IntelligenceDecision, decision_id)
    if decision is None:
        return {'status': 'skipped', 'reason': 'decision_not_found', 'decision_id': decision_id}

    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '').strip()
    max_attempts = notification_delivery_max_attempts()
    try:
        stats = dispatch_decision_notification(decision, event_type=event_type, base_url=base_url)
    except (SQLAlchemyError, RuntimeError, OSError, ValueError) as exc:
        if self.request.retries < max_attempts - 1:
            countdown = min(30 * (self.request.retries + 1), 120)
            raise self.retry(exc=exc, countdown=countdown, max_retries=max_attempts - 1) from exc
        raise
    if int(stats.get('failed', 0)) > 0 and self.request.retries < max_attempts - 1:
        countdown = min(30 * (self.request.retries + 1), 120)
        raise self.retry(countdown=countdown, max_retries=max_attempts - 1)
    return {'status': 'completed', 'event_type': event_type, **stats}


@shared_task(
    name='app.automation_control.tasks.materialize_automation_candidates',
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_automation_candidates() -> dict[str, int]:
    """Build non-executable review candidates from active alert evidence."""
    return materialize_active_alert_candidates()


@shared_task(
    name='app.automation_control.tasks.reconcile_automation_lifecycle',
    acks_late=True,
    reject_on_worker_lost=True,
)
def reconcile_automation_lifecycle() -> dict[str, int]:
    """Expire stale review and decision records so UI state matches TTL contracts."""
    return {
        'candidates_expired': expire_stale_candidates(),
        'decisions_expired': expire_stale_decisions(),
        'execution_authorizations_expired': expire_stale_execution_authorizations(),
    }
