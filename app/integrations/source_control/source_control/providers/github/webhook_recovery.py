"""Bounded committed-webhook inbox recovery via canonical KAORI jobs (#2742).

Internal maintenance sweeper, not an external ingress route or provider
source. The webhook-only ID hint can request fresh GitHub observations, but
cannot mutate inventory directly. Unknown dispatch outcomes never retry.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.webhook_completion import (
    reconcile_delivery_completion,
)
from app.integrations.source_control.source_control.providers.github.webhook_handoff import (
    dispatch_committed_delivery,
    flag_abandoned_dispatch,
)
from app.models.job import JobExecution
from app.models.source_control import SourceWebhookDelivery
from app.platform_operations.jobs.constants import TERMINAL_JOB_STATUSES




def _record_preclaim_failure(session: Session, delivery_id: int, now: datetime) -> None:
    """Back off validation failures that occurred before any dispatch claim.

    Once dispatching, webhook_handoff owns retry/uncertainty; do not override
    that independent state when a worker or database transaction fails.
    """
    row = session.execute(
        select(SourceWebhookDelivery)
        .where(SourceWebhookDelivery.id == delivery_id)
        .with_for_update(),
    ).scalar_one_or_none()
    if row is None or row.processing_state not in {'received', 'retry_pending'}:
        return
    row.attempt_count += 1
    row.last_attempt_at = now
    row.processing_state = 'requires_review' if row.attempt_count >= 3 else 'retry_pending'
    session.commit()

def recover_webhook_inbox(session: Session, *, limit: int = 25) -> dict[str, int | str]:
    """Sweep at most 25 transport envelopes; no unbounded provider lookups.

    This function is invoked by an opt-in maintenance task only. The
    per-delivery lock in the handoff/completion services owns row-level
    contention; status rereads prevent duplicate delivery dispatch.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 25:
        raise ValueError('Source Control webhook recovery batch must be between 1 and 25.')
    if not provider_kind('source_control', 'github').available:
        return {
            'status': 'not_admitted', 'examined': 0, 'queued': 0,
            'reconciled': 0, 'uncertain': 0, 'failed': 0,
        }

    now = datetime.now(UTC)
    ids = list(session.scalars(
        select(SourceWebhookDelivery.id)
        .outerjoin(
            JobExecution,
            SourceWebhookDelivery.dispatched_job_execution_id == JobExecution.id,
        )
        .where(or_(
            SourceWebhookDelivery.processing_state == 'received',
            and_(
                SourceWebhookDelivery.processing_state == 'retry_pending',
                or_(
                    SourceWebhookDelivery.last_attempt_at.is_(None),
                    SourceWebhookDelivery.last_attempt_at <= now - timedelta(minutes=5),
                ),
            ),
            and_(
                SourceWebhookDelivery.processing_state == 'dispatching',
                SourceWebhookDelivery.last_attempt_at <= now - timedelta(minutes=20),
            ),
            and_(
                SourceWebhookDelivery.processing_state == 'queued',
                or_(
                    JobExecution.id.is_(None),
                    JobExecution.status.in_(TERMINAL_JOB_STATUSES),
                ),
            ),
        ))
        .order_by(SourceWebhookDelivery.received_at, SourceWebhookDelivery.id)
        .limit(limit),
    ))
    queued = 0
    reconciled = 0
    uncertain = 0
    failed = 0
    for delivery_id in ids:
        try:
            row = session.get(SourceWebhookDelivery, delivery_id)
            if row is None:
                continue
            if row.processing_state == 'queued':
                state = reconcile_delivery_completion(session, delivery_record_id=delivery_id)
                reconciled += int(state.startswith('reconciled_'))
            elif row.processing_state == 'dispatching':
                uncertain += int(
                    flag_abandoned_dispatch(session, delivery_record_id=delivery_id)
                )
            elif row.processing_state in {'received', 'retry_pending'}:
                outcome = dispatch_committed_delivery(session, delivery_record_id=delivery_id)
                queued += int(outcome.state == 'queued')
        except Exception:
            # Do not log raw provider/broker exceptions: some may contain
            # installation tokens, endpoint URLs or webhook credentials.
            session.rollback()
            try:
                _record_preclaim_failure(session, delivery_id, now)
            except Exception:
                session.rollback()
            failed += 1
    return {
        'status': 'processed', 'examined': len(ids),
        'queued': queued, 'reconciled': reconciled,
        'uncertain': uncertain, 'failed': failed,
    }
