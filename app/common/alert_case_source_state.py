from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.models.alert_ops import AlertCase, AlertCaseEvent

SYSTEM_ROUTING_SUPPRESSION_REASONS = {'source_unavailable', 'source_deleted', 'policy_ineligible'}


def mark_case_source_unknown(
    case: AlertCase,
    *,
    reason: str,
    source_summary: str,
    now: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    """Apply the shared source-unknown transition without importing an owning feature domain."""
    if case.workflow_state == 'closed' or case.source_state == 'resolved':
        return False
    current = now or datetime.now(UTC)
    normalized_reason = str(reason or 'source_unavailable').strip().lower()[:64]
    changed = case.source_state != 'unknown' or case.source_state_reason != normalized_reason
    previous_state = case.source_state
    case.source_state = 'unknown'
    case.source_state_reason = normalized_reason
    case.source_state_changed_at = current
    case.source_resolved_at = None
    if case.routing_state == 'enabled' or case.routing_override_reason in SYSTEM_ROUTING_SUPPRESSION_REASONS:
        case.routing_state = 'suppressed'
        case.routing_override_reason = normalized_reason
        case.routing_override_note = None
        case.routing_override_at = current
        case.routing_override_by_user_id = None
    if changed:
        event = AlertCaseEvent()
        event.case_id = case.id
        event.event_type = 'source_unknown'
        event.actor_user_id = None
        event.summary = source_summary[:500]
        event.metadata_json = {
            'previous_source_state': previous_state,
            'reason': normalized_reason,
            **dict(metadata or {}),
        }
        db.session.add(event)
    return changed


def mark_asset_alert_cases_source_unknown(
    *,
    domain: str,
    asset_key: str,
    reason: str = 'source_deleted',
    source_kind: str | None = None,
) -> int:
    """Mark open recommendation-origin cases Unknown before a managed asset is removed."""
    rows = AlertCase.query.filter(
        AlertCase.source_type == 'recommendation',
        AlertCase.domain == str(domain),
        AlertCase.asset_key == str(asset_key),
        AlertCase.workflow_state != 'closed',
        AlertCase.source_state != 'resolved',
    ).all()
    changed = 0
    for case in rows:
        changed += int(
            mark_case_source_unknown(
                case,
                reason=reason,
                source_summary='The managed source was removed; KAORI no longer has fresh evidence to evaluate this alert.',
                metadata={'source_kind': source_kind or domain},
            )
        )
    return changed
