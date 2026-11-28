"""Bounded redacted projection of the canonical scoped delivery journal.

Called only within an audited exact-instance case read. Never expose channel
names, destination, provider response, encrypted replay envelope or actor IDs.
"""

from __future__ import annotations

import re
from typing import Any

from app.intelligence.alert_intelligence.vault_delivery_journal import audited_claim, audited_outcome, firing_journal
from app.intelligence.alert_signals.vault_source import _persisted_utc
from app.models.alert_ops import AlertCase
from app.models.notification_channel import NotificationDelivery

_DIGEST = re.compile(r'[a-f0-9]{64}')


def _unavailable() -> dict[str, Any]:
    return {'provider_delivery_qualified': False, 'deliveries': [], 'deliveries_recent': [], 'deliveries_older': []}


def read_case_delivery_evidence(case: AlertCase) -> dict[str, Any]:
    rows = firing_journal(case)
    if len(rows) != 1:
        return _unavailable()
    row = rows[0]
    claim = audited_claim(case, row)
    if not _qualified(case, row, claim):
        return _unavailable()
    outcome = audited_outcome(case, row)
    if (row.status == 'sent') != (outcome == 'sent'):
        return _unavailable()
    status = {'sent': 'sent', 'rejected': 'failed', 'unconfirmed': 'failed'}.get(outcome or '', 'queued')
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
        'deliveries': [projected],
        'deliveries_recent': [projected],
        'deliveries_older': [],
    }


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
