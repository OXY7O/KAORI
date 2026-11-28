"""Shared hot journal and audit guards for exact provider firing delivery.

The existing canonical retention domains retain both hot record types.
No separate identity ledger or generic automatic replay is admitted.
"""

from __future__ import annotations

from typing import Any

from app.models.alert_ops import AlertCase
from app.models.audit import AuditEvent
from app.models.notification_channel import NotificationDelivery

CLAIM_KEY = 'vault_scoped_claim'
REJECTION_KEY = 'definitive_rejection'
CLAIM_ACTION = 'vault_provider_delivery_claimed'
OUTCOME_ACTION = 'vault_provider_delivery_outcome'


def firing_journal(case: AlertCase, *, lock: bool = False) -> list[NotificationDelivery]:
    query = (
        NotificationDelivery.query.filter(
            NotificationDelivery.event_type == 'alert_ops.firing',
            NotificationDelivery.event_key.startswith(f'alert-case:{case.public_id}:firing:', autoescape=True),
        ).order_by(NotificationDelivery.id.asc()).limit(2)
    )
    return (query.with_for_update() if lock else query).populate_existing().all()


def claim_exists(case: AlertCase) -> bool:
    return AuditEvent.query.filter_by(
        target_type='alert_case', target_id=case.public_id, action=CLAIM_ACTION
    ).first() is not None


def _latest_audit(case: AlertCase, action: str) -> AuditEvent | None:
    return (
        AuditEvent.query.filter_by(target_type='alert_case', target_id=case.public_id, action=action)
        .order_by(AuditEvent.id.desc()).first()
    )


def audited_claim(case: AlertCase, row: NotificationDelivery) -> dict[str, Any] | None:
    payload = row.payload_json
    if not isinstance(payload, dict):
        return None
    claim = payload.get(CLAIM_KEY)
    if not isinstance(claim, dict):
        return None
    audit = _latest_audit(case, CLAIM_ACTION)
    expected = {**claim, 'attempt': row.attempt_count, 'domain': 'secrets_pki'}
    if audit is None or audit.actor_user_id != claim.get('maker_id') or audit.metadata_json != expected:
        return None
    return claim


def audited_outcome(case: AlertCase, row: NotificationDelivery) -> str | None:
    claim = audited_claim(case, row)
    if claim is None:
        return None
    audit = _latest_audit(case, OUTCOME_ACTION)
    if audit is None or audit.actor_user_id != claim.get('maker_id') or not isinstance(audit.metadata_json, dict):
        return None
    result = audit.metadata_json.get('result')
    if result not in ('sent', 'rejected', 'unconfirmed'):
        return None
    if audit.metadata_json != {**claim, 'attempt': row.attempt_count, 'domain': 'secrets_pki', 'result': result}:
        return None
    return result
