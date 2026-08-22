from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.models.alert_ops import AlertCase, AlertCaseEvent, RecommendationAlertState
from app.models.audit import AuditEvent

SYSTEM_ROUTING_SUPPRESSION_REASONS = {'source_unavailable', 'source_deleted', 'policy_ineligible'}


def mark_case_source_unknown(
    case: AlertCase,
    *,
    reason: str,
    source_summary: str,
    now: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    """Hold an open case when fresh source evidence is unavailable or deleted."""

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
        _apply_system_routing_suppression(case, reason=normalized_reason, now=current)
    if changed:
        _event(
            case,
            'source_unknown',
            None,
            source_summary,
            {
                'previous_source_state': previous_state,
                'reason': normalized_reason,
                **dict(metadata or {}),
            },
        )
    return changed


def restore_case_source_firing(
    case: AlertCase,
    *,
    source_summary: str,
    now: datetime | None = None,
) -> bool:
    """Restore a source-unknown case after fresh evidence confirms the condition still fires."""

    if case.workflow_state == 'closed':
        return False
    current = now or datetime.now(UTC)
    previous_state = case.source_state
    previous_reason = case.source_state_reason
    changed = previous_state != 'firing'
    case.source_state = 'firing'
    case.source_state_reason = None
    case.source_state_changed_at = current
    case.source_resolved_at = None
    restore_system_routing(case, reasons={'source_unavailable', 'source_deleted'}, now=current)
    if changed:
        _event(
            case,
            'source_firing_restored',
            None,
            source_summary,
            {'previous_source_state': previous_state, 'previous_reason': previous_reason},
        )
    return changed


def suppress_case_routing(
    case: AlertCase,
    *,
    reason: str,
    note: str | None,
    actor_user_id: int | None,
) -> None:
    """Stop outbound routing without changing the source or workflow state."""

    _require_open(case)
    normalized_note = str(note or '').strip()
    if not normalized_note:
        raise ValueError('A routing suppression reason is required.')
    now = datetime.now(UTC)
    case.routing_state = 'suppressed'
    case.routing_override_reason = str(reason or 'manual').strip().lower()[:64]
    case.routing_override_note = normalized_note[:1000]
    case.routing_override_at = now
    case.routing_override_by_user_id = actor_user_id
    _event(
        case,
        'routing_suppressed',
        actor_user_id,
        'Outbound KAORI notification routing was explicitly suppressed without resolving the alert.',
        {'reason': case.routing_override_reason, 'note': case.routing_override_note},
    )
    _audit(case, actor_user_id, 'alert_case_routing_suppressed', 'Alert case notification routing suppressed.')


def resume_case_routing(case: AlertCase, *, actor_user_id: int | None) -> None:
    """Resume a manually suppressed route while fresh evidence confirms firing."""

    _require_open(case)
    if case.source_state != 'firing':
        raise ValueError('Routing can resume only while fresh source evidence confirms the alert is firing.')
    if case.routing_override_reason in SYSTEM_ROUTING_SUPPRESSION_REASONS:
        raise ValueError('KAORI cannot resume routing while the source or alert policy still suppresses delivery.')
    if case.routing_state == 'enabled':
        raise ValueError('Alert routing is already enabled.')
    now = datetime.now(UTC)
    case.routing_state = 'enabled'
    case.routing_override_reason = None
    case.routing_override_note = None
    case.routing_override_at = now
    case.routing_override_by_user_id = actor_user_id
    _event(case, 'routing_resumed', actor_user_id, 'Outbound KAORI notification routing resumed.')
    _audit(case, actor_user_id, 'alert_case_routing_resumed', 'Alert case notification routing resumed.')


def set_case_policy_routing_eligibility(
    case: AlertCase,
    *,
    eligible: bool,
    now: datetime | None = None,
) -> bool:
    """Apply/clear system policy suppression without replacing manual operator intent."""

    if case.workflow_state == 'closed':
        return False
    current = now or datetime.now(UTC)
    if eligible:
        return restore_system_routing(case, reasons={'policy_ineligible'}, now=current)
    if case.routing_state == 'suppressed' and case.routing_override_reason not in {None, 'policy_ineligible'}:
        return False
    changed = case.routing_state != 'suppressed' or case.routing_override_reason != 'policy_ineligible'
    _apply_system_routing_suppression(case, reason='policy_ineligible', now=current)
    if changed:
        _event(
            case,
            'routing_policy_ineligible',
            None,
            'The source condition remains active, but the current Rule Catalog policy no longer allows alert delivery.',
        )
    return changed


def withdraw_manual_alert(
    case: AlertCase,
    *,
    reason: str,
    actor_user_id: int | None,
) -> None:
    """Close an incorrect manual promotion without claiming source resolution."""

    _require_open(case)
    if case.source_type != 'recommendation' or not _was_manually_promoted(case):
        raise ValueError('Only manually promoted recommendation alerts can be withdrawn.')
    normalized_reason = str(reason or '').strip()
    if not normalized_reason:
        raise ValueError('Withdrawal reason is required.')
    now = datetime.now(UTC)
    case.workflow_state = 'closed'
    case.closure_reason = 'manual_withdrawal'
    case.closed_at = now
    case.closed_by_user_id = actor_user_id
    case.routing_state = 'suppressed'
    case.routing_override_reason = 'manual'
    case.routing_override_note = normalized_reason[:1000]
    case.routing_override_at = now
    case.routing_override_by_user_id = actor_user_id
    for state in RecommendationAlertState.query.filter_by(alert_case_id=case.id).all():
        state.promotion_suppressed_until_clear = True
        state.promotion_suppression_reason = 'manual_withdrawal'
    _event(
        case,
        'manual_alert_withdrawn',
        actor_user_id,
        'The manually promoted alert was withdrawn. The underlying recommendation may remain active.',
        {'reason': normalized_reason[:500]},
    )
    _audit(case, actor_user_id, 'alert_case_withdrawn', 'Manually promoted alert withdrawn without source resolution.')


def close_false_positive_alert(
    case: AlertCase,
    *,
    reason: str,
    actor_user_id: int | None,
) -> None:
    """Close a recommendation-origin case as false positive without claiming source recovery."""

    _require_open(case)
    if case.source_type != 'recommendation':
        raise ValueError('Only KAORI recommendation alert cases can be closed as false positive.')
    normalized_reason = str(reason or '').strip()
    if not normalized_reason:
        raise ValueError('False-positive disposition reason is required.')
    now = datetime.now(UTC)
    case.workflow_state = 'closed'
    case.closure_reason = 'false_positive'
    case.closed_at = now
    case.closed_by_user_id = actor_user_id
    case.routing_state = 'suppressed'
    case.routing_override_reason = 'false_positive'
    case.routing_override_note = normalized_reason[:1000]
    case.routing_override_at = now
    case.routing_override_by_user_id = actor_user_id
    case.resolution_summary = 'Closed as false positive; KAORI did not record technical source recovery.'
    case.verification_evidence = normalized_reason
    for state in RecommendationAlertState.query.filter_by(alert_case_id=case.id).all():
        state.promotion_suppressed_until_clear = True
        state.promotion_suppression_reason = 'false_positive'
    _event(
        case,
        'false_positive_closed',
        actor_user_id,
        'The alert was closed as a false positive without claiming the source condition resolved.',
        {'reason': normalized_reason[:500]},
    )
    _audit(case, actor_user_id, 'alert_case_false_positive_closed', 'Alert case closed as false positive.')


def retire_source_deleted_case(
    case: AlertCase,
    *,
    reason: str,
    actor_user_id: int | None,
) -> None:
    """Close a source-deleted Unknown case as a governed decommissioning disposition."""

    _require_open(case)
    if case.source_state != 'unknown' or case.source_state_reason != 'source_deleted':
        raise ValueError('Only a source-deleted Unknown alert can be retired through decommissioning.')
    normalized_reason = str(reason or '').strip()
    if not normalized_reason:
        raise ValueError('Decommissioning disposition is required.')
    now = datetime.now(UTC)
    case.workflow_state = 'closed'
    case.closure_reason = 'source_decommissioned'
    case.closed_at = now
    case.closed_by_user_id = actor_user_id
    case.routing_state = 'suppressed'
    case.routing_override_reason = 'source_deleted'
    case.routing_override_note = normalized_reason[:1000]
    case.routing_override_at = now
    case.routing_override_by_user_id = actor_user_id
    case.resolution_summary = 'The monitored source was decommissioned; KAORI cannot assert technical resolution.'
    case.verification_evidence = normalized_reason
    _event(
        case,
        'source_decommissioned',
        actor_user_id,
        'Alert case retired after its monitored source was deleted.',
        {'disposition': normalized_reason[:500]},
    )
    _audit(case, actor_user_id, 'alert_case_source_decommissioned', 'Source-deleted alert case retired.')


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


def restore_system_routing(
    case: AlertCase,
    *,
    reasons: set[str],
    now: datetime | None = None,
) -> bool:
    if case.routing_state != 'suppressed' or case.routing_override_reason not in reasons:
        return False
    case.routing_state = 'enabled'
    case.routing_override_reason = None
    case.routing_override_note = None
    case.routing_override_at = now or datetime.now(UTC)
    case.routing_override_by_user_id = None
    return True


def _apply_system_routing_suppression(case: AlertCase, *, reason: str, now: datetime) -> None:
    case.routing_state = 'suppressed'
    case.routing_override_reason = reason
    case.routing_override_note = None
    case.routing_override_at = now
    case.routing_override_by_user_id = None


def _was_manually_promoted(case: AlertCase) -> bool:
    evidence = dict(case.evidence_json or {})
    if evidence.get('promotion_mode') == 'manual':
        return True
    row = (
        AlertCaseEvent.query.filter_by(case_id=case.id, event_type='recommendation_promoted')
        .order_by(AlertCaseEvent.id.asc())
        .first()
    )
    return bool(row and 'manually promoted' in str(row.summary or '').lower())


def _require_open(case: AlertCase) -> None:
    if case.workflow_state == 'closed':
        raise ValueError('Closed alert cases are read-only.')


def _event(
    case: AlertCase,
    event_type: str,
    actor_user_id: int | None,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    row = AlertCaseEvent()
    row.case_id = case.id
    row.event_type = event_type
    row.actor_user_id = actor_user_id
    row.summary = summary[:500]
    row.metadata_json = metadata or {}
    db.session.add(row)


def _audit(case: AlertCase, actor_user_id: int | None, action: str, summary: str) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'alert_case'
    event.target_id = case.public_id
    event.action = action
    event.summary = summary[:255]
    event.metadata_json = {
        'case_id': case.public_id,
        'alert_name': case.alert_name,
        'severity': case.severity,
        'domain': case.domain,
        'asset_key': case.asset_key,
    }
    db.session.add(event)
