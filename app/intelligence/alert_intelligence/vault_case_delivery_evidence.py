"""Bounded redacted projection of the canonical scoped delivery journal.

Called only within an audited exact-instance case read. Never expose channel
names, destination, provider response, encrypted replay envelope or actor IDs.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.integrations.delivery.notification_channels.config import notification_delivery_max_attempts
from app.intelligence.alert_intelligence.vault_delivery_journal import (
    REJECTION_KEY,
    audited_claim,
    audited_outcome,
    claim_exists,
    firing_journal,
)
from app.intelligence.alert_signals.vault_source import _persisted_utc
from app.models.alert_ops import AlertCase
from app.models.notification_channel import NotificationDelivery

_DIGEST = re.compile(r'[a-f0-9]{64}')


def _unavailable(*, state: str = 'unavailable') -> dict[str, Any]:
    return {
        'provider_delivery_qualified': False,
        'provider_delivery_state': state,
        'provider_retry_due': False,
        'deliveries': [],
        'deliveries_recent': [],
        'deliveries_older': [],
    }


def read_case_delivery_evidence(case: AlertCase) -> dict[str, Any]:
    rows = firing_journal(case)
    if not rows:
        return _unavailable(state='unavailable' if claim_exists(case) else 'no_claim')
    if len(rows) != 1:
        return _unavailable()
    row = rows[0]
    claim = audited_claim(case, row)
    if not _qualified(case, row, claim):
        return _unavailable()
    outcome = audited_outcome(case, row)
    status = _qualified_delivery_status(row, outcome)
    if status is None:
        return _unavailable()
    due = _persisted_utc(row.next_retry_at) if status == 'failed' else None
    projected = {
        'channel': 'Approved scoped destination',
        'provider': 'Governed channel',
        'event_label': 'Firing',
        'status': status,
        'attempt_count': row.attempt_count,
        'created_at': row.created_at,
        'sent_at': row.sent_at,
    }
    return {
        'provider_delivery_qualified': True,
        'provider_delivery_state': {
            'sent': 'sent', 'failed': 'rejected', 'review required': 'review_required',
        }[status],
        'provider_retry_due': bool(
            due is not None and due <= datetime.now(UTC)
            and row.attempt_count < notification_delivery_max_attempts()
        ),
        'deliveries': [projected],
        'deliveries_recent': [projected],
        'deliveries_older': [],
    }


def _qualified_delivery_status(row: NotificationDelivery, outcome: str | None) -> str | None:
    """An unconfirmed durable claim is never presented as queued/confirmed delivery.

    The canonical journal and committed outcome audit must agree. Failed
    or skipped claims without a matching outcome require manual review:
    the provider may have accepted an attempt before a crash.
    """
    payload = row.payload_json
    if not isinstance(payload, dict):
        return None
    rejected = payload.get(REJECTION_KEY)
    if outcome == 'sent':
        return 'sent' if row.status == 'sent' and rejected is False else None
    if outcome == 'rejected':
        return 'failed' if row.status in ('failed', 'skipped') and rejected is True else None
    if outcome == 'unconfirmed':
        return 'review required' if row.status == 'failed' and rejected is False else None
    if outcome is None and row.status in ('queued', 'failed', 'skipped'):
        return 'review required'
    return None


def _qualified(case: AlertCase, row: NotificationDelivery, claim: object) -> bool:
    if (
        not isinstance(claim, dict)
        or set(claim) != {'case_id', 'binding_id', 'policy_id', 'channel_id', 'receipt_ref', 'maker_id'}
        or row.domain != 'secrets_pki'
        or row.asset_type != 'vault_instance'
        or row.asset_key != case.asset_key
        or row.event_key != f'alert-case:{case.public_id}:firing:scoped-v1'
        or row.status not in ('queued', 'sent', 'failed', 'skipped')
        or type(row.attempt_count) is not int
        or row.attempt_count < 1
        or _persisted_utc(row.created_at) is None
        or (row.status == 'sent') != (row.sent_at is not None)
    ):
        return False
    return bool(
        claim['case_id'] == case.public_id
        and claim['binding_id'] == case.evidence_json['source_binding_id']
        and claim['channel_id'] == row.channel_id
        and all(type(claim[key]) is int and claim[key] > 0 for key in ('binding_id', 'policy_id', 'channel_id', 'maker_id'))
        and isinstance(claim['receipt_ref'], str)
        and _DIGEST.fullmatch(claim['receipt_ref'])
    )
