"""Bounded committed-webhook inbox recovery via canonical KAORI jobs (#2742).

Internal maintenance sweeper, not an external ingress route or provider
source. The webhook-only ID hint can request fresh GitHub observations, but
cannot mutate inventory directly. Unknown dispatch outcomes never retry.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.webhook_completion import (
    reconcile_delivery_completion,
)
from app.integrations.source_control.source_control.providers.github.webhook_handoff import (
    dispatch_committed_delivery,
    flag_abandoned_dispatch,
)
from app.models.source_control import SourceWebhookDelivery

_REVISIT = ('queued', 'dispatching', 'received', 'retry_pending')


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

    ids = list(session.scalars(
        select(SourceWebhookDelivery.id)
        .where(SourceWebhookDelivery.processing_state.in_(_REVISIT))
        .order_by(SourceWebhookDelivery.received_at, SourceWebhookDelivery.id)
        .limit(limit),
    ))
    results = {
        'status': 'processed', 'examined': len(ids), 'queued': 0,
        'reconciled': 0, 'uncertain': 0, 'failed': 0,
    }
    for delivery_id in ids:
        try:
            row = session.get(SourceWebhookDelivery, delivery_id)
            if row is None:
                continue
            if row.processing_state == 'queued':
                state = reconcile_delivery_completion(session, delivery_record_id=delivery_id)
                results['reconciled'] += int(state.startswith('reconciled_'))
            elif row.processing_state == 'dispatching':
                results['uncertain'] += int(
                    flag_abandoned_dispatch(session, delivery_record_id=delivery_id)
                )
            elif row.processing_state in {'received', 'retry_pending'}:
                outcome = dispatch_committed_delivery(session, delivery_record_id=delivery_id)
                results['queued'] += int(outcome.state == 'queued')
        except Exception:
            # Do not log raw provider/broker exceptions: some may contain
            # installation tokens, endpoint URLs or webhook credentials.
            session.rollback()
            results['failed'] += 1
    return results
