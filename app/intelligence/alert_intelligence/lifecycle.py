from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from app.extensions.db import db
from app.intelligence.alert_intelligence.snapshots import load_snapshot_rows
from app.models.alert_ops import AlertCase, AlertCaseEvent, AlertSilence
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.object_storage import ObjectStorageSystem
from app.platform_operations.notifications.service import create_notification

_ACTIVE_SOURCE_STATES = {'firing', 'pending', 'active'}
_OPERATOR_VERIFICATION_SEVERITIES = {'critical', 'warning'}
_POSTMORTEM_DURATION_MINUTES = 120


def reconcile_alert_cases() -> dict[str, int]:
    """Reconcile fresh committed worker snapshots into durable alert cases."""

    stats = {'assets': 0, 'created': 0, 'updated': 0, 'resolved': 0, 'auto_closed': 0, 'skipped': 0}
    for domain, asset_type, asset in _managed_assets():
        rows, _status, snapshot = load_snapshot_rows(domain=domain, asset_key=str(asset.id), source='auto')
        if not snapshot.get('available') or snapshot.get('serving_last_good'):
            stats['skipped'] += 1
            continue
        stats['assets'] += 1
        asset_result = _reconcile_asset(
            domain=domain,
            asset_type=asset_type,
            asset_key=str(asset.id),
            asset_name=str(asset.name),
            rows=rows,
        )
        for key in ('created', 'updated', 'resolved', 'auto_closed'):
            stats[key] += asset_result[key]
    db.session.commit()
    return stats


def acknowledge_case(case: AlertCase, *, actor_user_id: int | None) -> None:
    _require_open(case)
    from app.intelligence.alert_intelligence.routing import acknowledgement_timeout_for_case

    now = datetime.now(UTC)
    timeout_minutes = acknowledgement_timeout_for_case(case)
    case.acknowledged_at = now
    case.acknowledgement_expires_at = now + timedelta(minutes=timeout_minutes)
    case.acknowledged_by_user_id = actor_user_id
    if case.owner_user_id is None:
        case.owner_user_id = actor_user_id
    if case.workflow_state == 'open':
        case.workflow_state = 'acknowledged'
    _event(
        case,
        'acknowledged',
        actor_user_id,
        f'Alert case acknowledged for {timeout_minutes} minutes before reminder delivery resumes.',
        {'acknowledgement_timeout_minutes': timeout_minutes},
    )
    _audit(case, actor_user_id, 'alert_case_acknowledged', 'Alert case acknowledged with a bounded reminder window.')


def assign_case(case: AlertCase, *, owner_user_id: int | None, actor_user_id: int | None) -> None:
    _require_open(case)
    case.owner_user_id = owner_user_id
    _event(
        case,
        'assigned',
        actor_user_id,
        'Alert case ownership updated.',
        {'owner_user_id': owner_user_id},
    )
    _audit(case, actor_user_id, 'alert_case_assigned', 'Alert case ownership updated.')


def mark_mitigating(case: AlertCase, *, actor_user_id: int | None, note: str | None = None) -> None:
    _require_open(case)
    now = datetime.now(UTC)
    case.workflow_state = 'mitigating'
    case.mitigating_at = case.mitigating_at or now
    _event(case, 'mitigating', actor_user_id, note or 'Operator marked the alert case as actively mitigating.')
    _audit(case, actor_user_id, 'alert_case_mitigating', 'Alert case moved to mitigation.')


def create_delivery_silence(
    case: AlertCase,
    *,
    duration_minutes: int,
    reason: str,
    actor_user_id: int | None,
) -> AlertSilence:
    _require_open(case)
    normalized_reason = str(reason or '').strip()
    if not normalized_reason:
        raise ValueError('Silence reason is required.')
    duration = max(5, min(int(duration_minutes or 0), 10080))
    now = datetime.now(UTC)
    silence = AlertSilence()
    silence.case_id = case.id
    silence.starts_at = now
    silence.ends_at = now + timedelta(minutes=duration)
    silence.reason = normalized_reason[:500]
    silence.created_by_user_id = actor_user_id
    db.session.add(silence)
    _event(
        case,
        'silenced',
        actor_user_id,
        f'KAORI delivery silence created for {duration} minutes.',
        {'duration_minutes': duration, 'reason': normalized_reason[:500]},
    )
    _audit(case, actor_user_id, 'alert_case_silenced', 'KAORI notification delivery silence created.')
    return silence


def revoke_delivery_silence(case: AlertCase, *, actor_user_id: int | None) -> None:
    now = datetime.now(UTC)
    active = active_delivery_silence(case, now=now)
    if active is None:
        raise ValueError('This alert case has no active KAORI delivery silence.')
    active.revoked_at = now
    active.revoked_by_user_id = actor_user_id
    _event(case, 'unsilenced', actor_user_id, 'KAORI delivery silence revoked by an operator.')
    _audit(case, actor_user_id, 'alert_case_unsilenced', 'KAORI notification delivery silence revoked.')


def close_case(
    case: AlertCase,
    *,
    resolution_summary: str,
    remediation_steps: list[str],
    verification_evidence: str,
    change_reference: str | None,
    ticket_reference: str | None,
    actor_user_id: int | None,
) -> None:
    if case.source_state != 'resolved':
        raise ValueError('The source alert must be resolved before the case can be closed.')
    if case.workflow_state == 'closed':
        raise ValueError('This alert case is already closed.')
    normalized_resolution = str(resolution_summary or '').strip()
    normalized_verification = str(verification_evidence or '').strip()
    normalized_steps = [str(step).strip() for step in remediation_steps if str(step).strip()]
    if not normalized_resolution:
        raise ValueError('Resolution summary is required.')
    if not normalized_steps:
        raise ValueError('At least one remediation or recovery step is required.')
    if not normalized_verification:
        raise ValueError('Verification evidence is required before closure.')
    now = datetime.now(UTC)
    case.resolution_summary = normalized_resolution
    case.remediation_steps_json = normalized_steps
    case.verification_evidence = normalized_verification
    case.change_reference = _optional_text(change_reference)
    case.ticket_reference = _optional_text(ticket_reference)
    case.workflow_state = 'closed'
    case.closed_at = now
    case.closed_by_user_id = actor_user_id
    case.postmortem_required = _requires_postmortem(case)
    case.postmortem_status = 'required' if case.postmortem_required else 'not_required'
    _event(
        case,
        'closed',
        actor_user_id,
        'Alert case closed after verified resolution evidence was committed.',
        {
            'change_reference': case.change_reference,
            'ticket_reference': case.ticket_reference,
            'postmortem_required': case.postmortem_required,
        },
    )
    _audit(case, actor_user_id, 'alert_case_closed', 'Alert case closed with resolution evidence.')


def close_case_from_automation_verification(
    *,
    case_public_id: str,
    execution_public_id: str,
    action_key: str,
    verification_summary: str,
    verification_evidence: Mapping[str, Any],
    actor_user_id: int | None,
) -> bool:
    """Commit verified Automation Control remediation into the same durable AlertCase.

    Automation does not own a parallel incident lifecycle. Successful resolver verification
    resolves and closes the originating KAORI AlertCase with deterministic evidence.
    """
    case = AlertCase.query.filter_by(public_id=case_public_id, source_type='recommendation').first()
    if case is None or case.workflow_state == 'closed':
        return False
    now = datetime.now(UTC)
    case.source_state = 'resolved'
    case.source_resolved_at = case.source_resolved_at or now
    case.workflow_state = 'closed'
    case.closed_at = now
    case.closed_by_user_id = actor_user_id
    case.resolution_summary = str(verification_summary or 'Automation Control remediation verified.').strip()
    case.remediation_steps_json = [f'Automation Control executed resolver action {action_key}.']
    evidence = dict(verification_evidence or {})
    case.verification_evidence = str(
        evidence.get('summary')
        or evidence.get('observed')
        or verification_summary
        or 'Resolver post-action verification succeeded.'
    )
    case.change_reference = f'AUTOMATION:{execution_public_id}'
    case.postmortem_required = _requires_postmortem(case)
    case.postmortem_status = 'required' if case.postmortem_required else 'not_required'
    case.evidence_json = {
        **dict(case.evidence_json or {}),
        'automation_resolution': {
            'execution_id': execution_public_id,
            'action_key': action_key,
            'verification_summary': verification_summary,
            'verification_evidence': evidence,
            'verified_at': now.isoformat(),
        },
    }
    _event(
        case,
        'automation_verified_resolution',
        actor_user_id,
        'Automation Control remediation was verified and committed as the case resolution.',
        {'execution_id': execution_public_id, 'action_key': action_key},
    )
    _audit(
        case,
        actor_user_id,
        'alert_case_automation_closed',
        'Alert case closed from verified Automation Control remediation.',
    )
    return True


def save_postmortem(
    case: AlertCase,
    *,
    payload: dict[str, str],
    complete: bool,
    actor_user_id: int | None,
) -> None:
    if case.workflow_state != 'closed':
        raise ValueError('Postmortem evidence can only be recorded after case closure.')
    normalized = {key: str(value or '').strip() for key, value in payload.items()}
    required = ('impact', 'timeline_summary', 'root_cause', 'recovery', 'action_items')
    if complete and any(not normalized.get(key) for key in required):
        raise ValueError('Complete postmortems require impact, timeline, root cause, recovery, and action items.')
    case.postmortem_json = normalized
    case.postmortem_status = 'complete' if complete else 'draft'
    _event(
        case,
        'postmortem_completed' if complete else 'postmortem_saved',
        actor_user_id,
        'Postmortem completed.' if complete else 'Postmortem draft saved.',
    )
    _audit(case, actor_user_id, 'alert_case_postmortem', 'Alert case postmortem updated.')


def active_delivery_silence(case: AlertCase, *, now: datetime | None = None) -> AlertSilence | None:
    current = now or datetime.now(UTC)
    return (
        AlertSilence.query.filter(
            AlertSilence.case_id == case.id,
            AlertSilence.starts_at <= current,
            AlertSilence.ends_at > current,
            AlertSilence.revoked_at.is_(None),
        )
        .order_by(AlertSilence.ends_at.desc())
        .first()
    )


def acknowledgement_suppresses_delivery(case: AlertCase, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(UTC)
    expires_at = case.acknowledgement_expires_at
    if case.acknowledged_at is None or expires_at is None:
        return False
    return _as_utc(expires_at) > current


def expire_acknowledgements_and_notify() -> int:
    """Record overdue ACK ownership while leaving the case acknowledged and firing."""
    now = datetime.now(UTC)
    rows = AlertCase.query.filter(
        AlertCase.source_type == 'recommendation',
        AlertCase.source_state == 'firing',
        AlertCase.workflow_state.in_(('acknowledged', 'mitigating')),
        AlertCase.acknowledgement_expires_at.is_not(None),
        AlertCase.acknowledgement_expires_at <= now,
    ).all()
    count = 0
    for case in rows:
        expires_at = _as_utc(case.acknowledgement_expires_at)
        already = (
            AlertCaseEvent.query.filter_by(case_id=case.id, event_type='acknowledgement_overdue')
            .filter(AlertCaseEvent.created_at >= expires_at)
            .first()
        )
        if already is not None:
            continue
        _event(
            case,
            'acknowledgement_overdue',
            None,
            'Acknowledgement reminder window expired while the alert is still firing.',
            {'acknowledgement_expires_at': expires_at.isoformat()},
        )
        recipient = case.owner_user_id or case.acknowledged_by_user_id
        create_notification(
            user_id=recipient,
            event_type='alert_case_acknowledgement_overdue',
            status='warning',
            title='Acknowledged Alert Still Firing',
            message=f'{case.alert_name} remains active after its acknowledgement reminder window.',
            detail='KAORI channel delivery is eligible again until the condition resolves, is re-acknowledged, or is silenced.',
            action_url=f'/intelligence/alert-intelligence?tab=active&case={case.public_id}',
            metadata={'case_id': case.public_id, 'domain': case.domain, 'asset_key': case.asset_key},
            deck_visible=True,
        )
        count += 1
    if count:
        db.session.commit()
    return count


def expire_silences_and_notify() -> int:
    now = datetime.now(UTC)
    rows = (
        AlertSilence.query.join(AlertCase, AlertCase.id == AlertSilence.case_id)
        .filter(
            AlertSilence.ends_at <= now,
            AlertSilence.revoked_at.is_(None),
            AlertCase.source_state == 'firing',
            AlertCase.workflow_state != 'closed',
        )
        .all()
    )
    count = 0
    for silence in rows:
        case = silence.case
        already = (
            AlertCaseEvent.query.filter_by(case_id=case.id, event_type='silence_expired')
            .filter(AlertCaseEvent.created_at >= silence.ends_at)
            .first()
        )
        if already is not None:
            continue
        _event(case, 'silence_expired', None, 'KAORI delivery silence expired while the alert is still firing.')
        recipient = case.owner_user_id or case.acknowledged_by_user_id
        create_notification(
            user_id=recipient,
            event_type='alert_case_silence_expired',
            status='warning',
            title='Silence Expired · Alert Still Firing',
            message=f'{case.alert_name} is still firing after its KAORI delivery silence expired.',
            detail='Review the alert case before creating another silence or applying remediation.',
            action_url=f'/intelligence/alert-intelligence?tab=active&case={case.public_id}',
            metadata={'case_id': case.public_id, 'domain': case.domain, 'asset_key': case.asset_key},
            deck_visible=True,
        )
        count += 1
    if count:
        db.session.commit()
    return count


def mark_case_source_resolved(
    case: AlertCase,
    *,
    source_summary: str,
    now: datetime | None = None,
    auto_resolution_summary: str | None = None,
    auto_remediation_step: str | None = None,
    auto_verification_evidence: str | None = None,
) -> str:
    """Move one firing source to resolved without conflating source recovery and operator closure."""

    current = now or datetime.now(UTC)
    if case.source_state == 'resolved':
        return case.workflow_state
    case.source_state = 'resolved'
    case.source_resolved_at = current
    _event(case, 'source_resolved', None, source_summary)
    if case.severity in _OPERATOR_VERIFICATION_SEVERITIES or case.acknowledged_at is not None:
        case.workflow_state = 'verification_pending'
        case.verification_started_at = current
        recipient = case.owner_user_id or case.acknowledged_by_user_id
        create_notification(
            user_id=recipient,
            event_type='alert_case_verification_required',
            status='warning',
            title='Resolution Verification Required',
            message=f'{case.alert_name} is source-resolved and requires operator closure evidence.',
            action_url=f'/intelligence/alert-intelligence?tab=resolved&case={case.public_id}',
            metadata={'case_id': case.public_id, 'domain': case.domain, 'asset_key': case.asset_key},
            deck_visible=True,
        )
        return case.workflow_state
    case.workflow_state = 'closed'
    case.closed_at = current
    case.resolution_summary = (
        auto_resolution_summary or 'The source alert recovered without a recorded manual remediation.'
    )
    case.remediation_steps_json = [
        auto_remediation_step or 'Observed source recovery in the committed worker snapshot.'
    ]
    case.verification_evidence = (
        auto_verification_evidence or 'Alert absent from the next fresh committed source snapshot.'
    )
    case.postmortem_required = False
    case.postmortem_status = 'not_required'
    _event(case, 'auto_closed', None, 'Case auto-closed by the source-resolved policy for non-paging severity.')
    return case.workflow_state


def get_case(public_id: str) -> AlertCase | None:
    return AlertCase.query.filter_by(public_id=str(public_id)).first()


def _reconcile_asset(
    *,
    domain: str,
    asset_type: str,
    asset_key: str,
    asset_name: str,
    rows: list[Mapping[str, Any]],
) -> dict[str, int]:
    now = datetime.now(UTC)
    stats = {'created': 0, 'updated': 0, 'resolved': 0, 'auto_closed': 0}
    seen: set[str] = set()
    for raw in rows:
        state = str(raw.get('status') or raw.get('state') or 'active').lower()
        if state not in _ACTIVE_SOURCE_STATES:
            continue
        case_key = _case_key(domain, asset_key, raw)
        seen.add(case_key)
        case = (
            AlertCase.query.filter(
                AlertCase.case_key == case_key,
                AlertCase.workflow_state != 'closed',
            )
            .order_by(AlertCase.id.desc())
            .first()
        )
        if case is None:
            case = AlertCase()
            case.case_key = case_key
            case.fingerprint = _optional_text(raw.get('fingerprint'))
            case.source_type = 'provider_alert'
            case.source_ref = _optional_text(raw.get('fingerprint') or case_key)
            case.rule_key = _optional_text(raw.get('name'))
            case.domain = domain
            case.asset_type = asset_type
            case.asset_key = asset_key
            case.asset_name = asset_name
            case.alert_name = str(raw.get('name') or 'Unknown Alert')[:255]
            case.first_seen_at = _coerce_datetime(raw.get('starts_at')) or now
            case.workflow_state = 'open'
            case.source_state = 'firing'
            db.session.add(case)
            db.session.flush()
            _event(case, 'detected', None, 'Alert detected from the committed worker snapshot.')
            stats['created'] += 1
        else:
            if case.source_state == 'resolved':
                case.source_state = 'firing'
                case.source_resolved_at = None
                case.workflow_state = 'open'
                _event(case, 'source_reopened', None, 'The source alert started firing again before case closure.')
            stats['updated'] += 1
        _update_case_from_row(case, raw, now=now)

    open_cases = AlertCase.query.filter(
        AlertCase.domain == domain,
        AlertCase.asset_key == asset_key,
        AlertCase.source_type == 'provider_alert',
        AlertCase.workflow_state != 'closed',
        AlertCase.source_state == 'firing',
    ).all()
    for case in open_cases:
        if case.case_key in seen:
            continue
        workflow_state = mark_case_source_resolved(
            case,
            now=now,
            source_summary='The alert is no longer firing in the latest committed source snapshot.',
        )
        stats['resolved'] += 1
        if workflow_state == 'closed':
            stats['auto_closed'] += 1
    return stats


def _update_case_from_row(case: AlertCase, row: Mapping[str, Any], *, now: datetime) -> None:
    case.last_seen_at = now
    case.severity = _severity(row.get('severity'))
    case.summary = _optional_text(row.get('summary') or row.get('description'))
    case.target = _optional_text(row.get('target'))
    case.namespace = _optional_text(row.get('namespace'))
    case.receiver = _optional_text(row.get('receiver'))
    labels = dict(row.get('labels')) if isinstance(row.get('labels'), Mapping) else {}
    labels.setdefault('source_type', 'provider_alert')
    if case.rule_key:
        labels.setdefault('rule_key', case.rule_key)
    case.labels_json = labels
    case.evidence_json = {
        'summary': case.summary,
        'target': case.target,
        'namespace': case.namespace,
        'receiver': case.receiver,
        'silenced_at_source': bool(row.get('silenced')),
        'inhibited_at_source': bool(row.get('inhibited')),
        'source': str(row.get('source') or '-'),
    }


def _managed_assets():
    for cluster in Cluster.query.order_by(Cluster.id.asc()).all():
        yield 'kubernetes', 'kubernetes_cluster', cluster
    for system in ObjectStorageSystem.query.order_by(ObjectStorageSystem.id.asc()).all():
        yield 'object_storage', 'object_storage_system', system


def _case_key(domain: str, asset_key: str, row: Mapping[str, Any]) -> str:
    fingerprint = str(row.get('fingerprint') or '').strip()
    if fingerprint:
        identity = f'{domain}|{asset_key}|{fingerprint}'
    else:
        labels = row.get('labels') if isinstance(row.get('labels'), Mapping) else {}
        identity = '|'.join(
            [
                domain,
                asset_key,
                str(row.get('name') or ''),
                str(row.get('target') or ''),
                str(labels.get('namespace') or row.get('namespace') or ''),
            ]
        )
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()[:64]


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


def _requires_postmortem(case: AlertCase) -> bool:
    if case.severity == 'critical':
        return True
    end = case.closed_at or case.source_resolved_at or datetime.now(UTC)
    duration = end - case.first_seen_at
    return case.severity == 'warning' and duration >= timedelta(minutes=_POSTMORTEM_DURATION_MINUTES)


def _require_open(case: AlertCase) -> None:
    if case.workflow_state == 'closed':
        raise ValueError('Closed alert cases are read-only.')


def _severity(value: Any) -> str:
    normalized = str(value or 'info').strip().lower()
    return normalized if normalized in {'critical', 'warning', 'info', 'unknown'} else 'unknown'


def _optional_text(value: Any) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    normalized = str(value or '').strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
