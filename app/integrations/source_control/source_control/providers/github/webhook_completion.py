"""Commit signed webhook handoff completion from canonical JobExecution (#2742).

Webhook bytes are transport evidence only. The authoritative worker result
is JobExecution; its terminal state must agree with the installation-scoped
job identity before a transport envelope may be marked reconciled.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import JobExecution
from app.models.source_control import SourceInstallation, SourceWebhookDelivery
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES

_TERMINAL_MAP = {
    'succeeded': 'reconciled_success',
    'partially_succeeded': 'reconciled_partial',
    'failed': 'reconciled_failure',
    'canceled': 'reconciled_canceled',
}
_RECONCILED_STATES = frozenset(_TERMINAL_MAP.values())
_EXPECTED_JOB_TYPE = 'source_control_repository_inventory'
_EXPECTED_OPERATION = 'sync_source_control_repositories'


def reconcile_delivery_completion(
    session: Session, *,
    delivery_record_id: int,
    now: datetime | None = None,
) -> str:
    """Persist terminal evidence only if the linked job has matching authority.

    Does not dispatch jobs or read GitHub. Missing/mis-scoped/expired execution
    remains an explicit requires_review, never successful or silently retried.
    """
    if (
        isinstance(delivery_record_id, bool)
        or not isinstance(delivery_record_id, int)
        or delivery_record_id <= 0
    ):
        raise ValueError('A committed Source Control delivery ID is required.')
    delivery = session.execute(
        select(SourceWebhookDelivery)
        .where(SourceWebhookDelivery.id == delivery_record_id)
        .with_for_update(),
    ).scalar_one_or_none()
    if delivery is None:
        raise ValueError('The Source Control delivery is unavailable.')
    if delivery.processing_state in _RECONCILED_STATES or delivery.processing_state == 'requires_review':
        return delivery.processing_state
    if delivery.processing_state != 'queued':
        return delivery.processing_state

    installation = session.get(SourceInstallation, delivery.installation_id)
    job = (
        session.get(JobExecution, delivery.dispatched_job_execution_id)
        if delivery.dispatched_job_execution_id is not None else None
    )
    if (
        installation is None or job is None
        or job.job_type != _EXPECTED_JOB_TYPE
        or job.operation != _EXPECTED_OPERATION
        or job.integration_type != 'source_control'
        or job.scope_type != 'source_control_installation'
        or job.scope_key != f'installation:{delivery.installation_id}'
    ):
        delivery.processing_state = 'requires_review'
    elif job.status in ACTIVE_JOB_STATUSES:
        return delivery.processing_state
    elif job.status in _TERMINAL_MAP:
        delivery.processing_state = _TERMINAL_MAP[job.status]
        delivery.completed_at = now or datetime.now(UTC)
    else:
        delivery.processing_state = 'requires_review'

    session.commit()
    return delivery.processing_state


def reconcile_queued_deliveries(
    session: Session, *, limit: int = 25, now: datetime | None = None,
) -> dict[str, int]:
    """Bounded, DB-only completion refresh; independent of public ingress."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 25:
        raise ValueError('Source Control completion batch exceeds its bounded limit.')
    ids = list(session.scalars(
        select(SourceWebhookDelivery.id)
        .where(SourceWebhookDelivery.processing_state == 'queued')
        .order_by(SourceWebhookDelivery.received_at, SourceWebhookDelivery.id)
        .limit(limit),
    ))
    changed = 0
    review = 0
    for delivery_id in ids:
        state = reconcile_delivery_completion(session, delivery_record_id=delivery_id, now=now)
        changed += int(state in _RECONCILED_STATES)
        review += int(state == 'requires_review')
    return {'examined': len(ids), 'reconciled': changed, 'requires_review': review}
