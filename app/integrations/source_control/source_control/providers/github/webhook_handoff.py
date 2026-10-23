"""Transactional Source Control webhook outbox -> canonical Jobs handoff (#2742).

Called only by a future authenticated inbox consumer *after* the ingress
transaction has committed. This module does NOT expose a webhook endpoint,
create a Celery task or publish GitHub source facts from webhook payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github.reconciliation_intent import (
    resolve_reconciliation_intent,
)
from app.integrations.source_control.source_control.providers.github.webhook import GitHubWebhookError
from app.integrations.source_control.sync_jobs import enqueue_source_repository_sync
from app.models.source_control import SourceInstallation, SourceWebhookDelivery

_MAX_DISPATCH_ATTEMPTS = 3
_RETRY_DELAY = timedelta(minutes=5)
_UNCERTAIN_AFTER = timedelta(minutes=20)


@dataclass(frozen=True, slots=True)
class DeliveryHandoff:
    delivery_record_id: int
    installation_id: int
    state: str
    job_execution_id: int | None
    created_job: bool


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _lock_delivery(session: Session, record_id: int) -> SourceWebhookDelivery | None:
    return session.execute(
        select(SourceWebhookDelivery)
        .where(SourceWebhookDelivery.id == record_id)
        .with_for_update(),
    ).scalar_one_or_none()


def _mark_uncertain_or_retry(
    session: Session, delivery_id: int, *, attempt_count: int,
    unknown_dispatch: bool,
) -> None:
    row = _lock_delivery(session, delivery_id)
    if row is None or row.processing_state != 'dispatching' or row.attempt_count != attempt_count:
        return
    row.processing_state = (
        'dispatch_uncertain' if unknown_dispatch
        else 'requires_review' if row.attempt_count >= _MAX_DISPATCH_ATTEMPTS
        else 'retry_pending'
    )
    session.commit()


def dispatch_committed_delivery(
    session: Session, *, delivery_record_id: int,
    now: datetime | None = None,
) -> DeliveryHandoff:
    """Claim one persisted signed delivery, commit claim, then enqueue.

    Uncertain post-enqueue persistence is held for human reconciliation,
    **not** retried automatically: the task may already have completed.
    A retry_pending dispatch can be reattempted only after a bounded delay.
    """
    if isinstance(delivery_record_id, bool) or not isinstance(delivery_record_id, int) or delivery_record_id <= 0:
        raise GitHubWebhookError('Committed GitHub delivery identity is invalid.')
    at = now or datetime.now(UTC)
    row = _lock_delivery(session, delivery_record_id)
    if row is None:
        raise GitHubWebhookError('Committed GitHub delivery was not found.')
    if row.processing_state not in {'received', 'retry_pending'}:
        return DeliveryHandoff(
            row.id, row.installation_id, row.processing_state,
            row.dispatched_job_execution_id, False,
        )
    if (
        row.processing_state == 'retry_pending'
        and row.last_attempt_at is not None
        and _utc(row.last_attempt_at) + _RETRY_DELAY > at
    ):
        return DeliveryHandoff(row.id, row.installation_id, 'retry_pending', None, False)
    if row.attempt_count >= _MAX_DISPATCH_ATTEMPTS:
        row.processing_state = 'requires_review'
        session.commit()
        return DeliveryHandoff(row.id, row.installation_id, 'requires_review', None, False)

    installation = session.get(SourceInstallation, row.installation_id)
    if installation is None:
        raise GitHubWebhookError('Source Control installation no longer exists.')
    # Verify the canonical provider/install/account authority and current
    # grant against the *committed* inbox row before any queue action.
    resolve_reconciliation_intent(
        session=session, installation=installation, delivery_record_id=row.id,
    )
    row.processing_state = 'dispatching'
    row.last_attempt_at = at
    row.attempt_count += 1
    attempt = row.attempt_count
    installation_id = installation.id
    session.commit()  # The only safe boundary for any JobExecution dispatch.

    dispatched = False
    try:
        # Installation-wide refresh is a safe superset of a targeted intent.
        # GitHub is always re-read through the installation-authorized
        # exhaustive collector, never trusted from payload repository hints.
        job, created = enqueue_source_repository_sync(
            requested_by_user_id=None,
            trigger_type='on_demand',
            installation_record_id=installation_id,
        )
        dispatched = True
        job_id = int(job.id)
        current = _lock_delivery(session, delivery_record_id)
        if current is None or current.processing_state != 'dispatching' or current.attempt_count != attempt:
            raise GitHubWebhookError('Webhook dispatch claim changed while queueing.')
        current.dispatched_job_execution_id = job_id
        current.processing_state = 'queued'
        session.commit()
        return DeliveryHandoff(delivery_record_id, installation_id, 'queued', job_id, created)
    except Exception:
        session.rollback()
        # An exception AFTER creating/attaching a canonical job is ambiguous.
        # No optimistic retry, invented completion, or notification event.
        _mark_uncertain_or_retry(
            session, delivery_record_id, attempt_count=attempt, unknown_dispatch=dispatched,
        )
        raise


def flag_abandoned_dispatch(
    session: Session, *, delivery_record_id: int,
    now: datetime | None = None,
) -> bool:
    """Surface an unknown worker outcome without scheduling a duplicate job."""
    row = _lock_delivery(session, delivery_record_id)
    if row is None or row.processing_state != 'dispatching' or row.last_attempt_at is None:
        return False
    if _utc(row.last_attempt_at) + _UNCERTAIN_AFTER > (now or datetime.now(UTC)):
        return False
    row.processing_state = 'dispatch_uncertain'
    session.commit()
    return True
