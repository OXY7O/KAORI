from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.extensions.db import db
from app.models.alert_ops import RuleException
from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.service import create_notification

_EXPIRING_WINDOW = timedelta(days=7)
_VALID_SCOPE_MODES = {'rule_asset', 'finding_keys'}


def base_rule_key(finding_key: str) -> str:
    return str(finding_key or '').split(':', 1)[0].strip()


def finding_asset_key(finding: dict[str, Any]) -> str:
    evidence = _evidence(finding)
    return str(
        evidence.get('asset_key') or evidence.get('cluster_id') or evidence.get('object_storage_system_id') or ''
    ).strip()


def finding_asset_name(finding: dict[str, Any]) -> str:
    evidence = _evidence(finding)
    return str(
        evidence.get('system_name')
        or evidence.get('cluster_name')
        or finding.get('domain_label')
        or finding.get('domain')
        or 'Asset'
    ).strip()


def finding_target_label(finding: dict[str, Any]) -> str:
    evidence = _evidence(finding)
    return str(
        evidence.get('bucket_name')
        or evidence.get('workload_name')
        or evidence.get('pod_name')
        or evidence.get('secret_name')
        or evidence.get('namespace')
        or finding.get('affected_summary')
        or finding.get('title')
        or finding.get('rule_key')
        or 'Finding'
    ).strip()


def active_rule_exceptions(
    rule_keys: Iterable[str] | None = None,
    *,
    now: datetime | None = None,
) -> list[RuleException]:
    current = _as_utc(now or datetime.now(UTC))
    query = RuleException.query.filter(
        RuleException.revoked_at.is_(None),
        RuleException.starts_at <= current,
        RuleException.expires_at > current,
    )
    keys = {str(value or '').strip() for value in (rule_keys or ()) if str(value or '').strip()}
    if keys:
        query = query.filter(RuleException.rule_key.in_(keys))
    return query.order_by(RuleException.expires_at.asc(), RuleException.id.asc()).all()


def active_exception_counts(rule_keys: Iterable[str], *, now: datetime | None = None) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in active_rule_exceptions(rule_keys, now=now):
        counts[row.rule_key] += 1
    return dict(counts)


def matching_rule_exception(
    finding: dict[str, Any],
    *,
    rows: Iterable[RuleException] | None = None,
    now: datetime | None = None,
) -> RuleException | None:
    finding_key = str(finding.get('rule_key') or '').strip()
    rule_key = base_rule_key(finding_key)
    asset_key = finding_asset_key(finding)
    if not finding_key or not rule_key or not asset_key:
        return None
    candidates = list(rows) if rows is not None else active_rule_exceptions((rule_key,), now=now)
    current = _as_utc(now or datetime.now(UTC))
    for row in candidates:
        if row.rule_key != rule_key or row.asset_key != asset_key:
            continue
        if not rule_exception_is_active(row, now=current):
            continue
        if row.scope_mode == 'rule_asset':
            return row
        if row.scope_mode == 'finding_keys' and finding_key in set(row.finding_keys_json or []):
            return row
    return None


@dataclass(frozen=True, slots=True)
class RuleExceptionCreateSpec:
    rule_key: str
    domain: str
    asset_key: str
    scope_mode: str
    finding_keys: tuple[str, ...]
    reason: str
    risk_reference: str | None
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class _NormalizedRuleExceptionCreateSpec:
    rule_key: str
    domain: str
    asset_key: str
    scope_mode: str
    finding_keys: tuple[str, ...]
    reason: str
    risk_reference: str | None
    expires_at: datetime


def _normalize_create_spec(spec: RuleExceptionCreateSpec) -> _NormalizedRuleExceptionCreateSpec:
    return _NormalizedRuleExceptionCreateSpec(
        rule_key=str(spec.rule_key or '').strip(),
        domain=str(spec.domain or '').strip().lower(),
        asset_key=str(spec.asset_key or '').strip(),
        scope_mode=str(spec.scope_mode or '').strip().lower(),
        finding_keys=tuple(
            sorted({str(value or '').strip() for value in spec.finding_keys if str(value or '').strip()})
        ),
        reason=' '.join(str(spec.reason or '').split()),
        risk_reference=str(spec.risk_reference or '').strip() or None,
        expires_at=_as_utc(spec.expires_at),
    )


def _validate_create_spec(spec: _NormalizedRuleExceptionCreateSpec, *, current: datetime) -> None:
    if not spec.rule_key or not spec.domain or not spec.asset_key:
        raise ValueError('Rule, domain, and asset are required for an accepted-risk exception.')
    if spec.scope_mode not in _VALID_SCOPE_MODES:
        raise ValueError('Exception scope must be Entire Asset or Selected Findings.')
    if spec.scope_mode == 'finding_keys' and not spec.finding_keys:
        raise ValueError('Select at least one active finding for a scoped accepted-risk exception.')
    if not spec.reason:
        raise ValueError('Accepted-risk reason is required.')
    if spec.expires_at <= current:
        raise ValueError('Accepted-risk expiry must be in the future.')
    if spec.expires_at > current + timedelta(days=3650):
        raise ValueError('Accepted-risk expiry cannot be more than 10 years in the future.')
    if spec.risk_reference and len(spec.risk_reference) > 255:
        raise ValueError('Risk / change reference cannot exceed 255 characters.')


def _overlapping_exception(
    spec: _NormalizedRuleExceptionCreateSpec,
    *,
    current: datetime,
) -> RuleException | None:
    selected_keys = set(spec.finding_keys)
    for row in active_rule_exceptions((spec.rule_key,), now=current):
        if row.asset_key != spec.asset_key:
            continue
        overlaps = (
            spec.scope_mode == 'rule_asset'
            or row.scope_mode == 'rule_asset'
            or bool(set(row.finding_keys_json or []) & selected_keys)
        )
        if overlaps:
            return row
    return None


def create_rule_exception(
    spec: RuleExceptionCreateSpec,
    *,
    actor_user_id: int | None,
    owner_user_id: int | None = None,
    now: datetime | None = None,
) -> RuleException:
    current = _as_utc(now or datetime.now(UTC))
    normalized = _normalize_create_spec(spec)
    _validate_create_spec(normalized, current=current)
    conflict = _overlapping_exception(normalized, current=current)
    if conflict is not None:
        reference = str(conflict.risk_reference or conflict.public_id)
        raise ValueError(
            f'Accepted risk {reference} already overlaps this rule and asset scope. '
            'Revoke the existing exception or choose findings that are not already covered.'
        )

    row = RuleException()
    row.rule_key = normalized.rule_key
    row.domain = normalized.domain
    row.asset_key = normalized.asset_key
    row.scope_mode = normalized.scope_mode
    row.finding_keys_json = list(normalized.finding_keys) if normalized.scope_mode == 'finding_keys' else []
    row.reason = normalized.reason
    row.risk_reference = normalized.risk_reference
    row.owner_user_id = owner_user_id if owner_user_id is not None else actor_user_id
    row.created_by_user_id = actor_user_id
    row.starts_at = current
    row.expires_at = normalized.expires_at
    db.session.add(row)
    return row


def revoke_rule_exception(
    row: RuleException,
    *,
    reason: str,
    actor_user_id: int | None,
    now: datetime | None = None,
) -> None:
    normalized_reason = ' '.join(str(reason or '').split())
    if not normalized_reason:
        raise ValueError('Revocation reason is required.')
    if row.revoked_at is not None:
        raise ValueError('This accepted-risk exception is already revoked.')
    row.revoked_at = _as_utc(now or datetime.now(UTC))
    row.revoked_by_user_id = actor_user_id
    row.revocation_reason = normalized_reason


def notify_expiring_rule_exceptions(*, now: datetime | None = None) -> int:
    current = _as_utc(now or datetime.now(UTC))
    rows = [
        row
        for row in RuleException.query.filter(
            RuleException.revoked_at.is_(None),
            RuleException.starts_at <= current,
            RuleException.expires_at > current,
            RuleException.expires_at <= current + _EXPIRING_WINDOW,
        )
        .order_by(RuleException.expires_at.asc(), RuleException.id.asc())
        .all()
        if row.owner_user_id is not None
    ]
    created = 0
    for row in rows:
        reference = str(row.risk_reference or row.public_id)
        message = f'{reference} expires within 7 days and still owns accepted-risk follow-up.'
        already = Notification.query.filter_by(
            user_id=row.owner_user_id,
            event_type='rule_exception_expiring',
            message=message,
        ).first()
        if already is not None:
            continue
        create_notification(
            user_id=row.owner_user_id,
            event_type='rule_exception_expiring',
            status='warning',
            title='Accepted Risk Expiring Soon',
            message=message,
            detail='Review remediation progress, extend through a new governed decision if justified, or allow the exception to expire so active findings become alert-eligible again.',
            action_url=f'/intelligence/catalog?q={row.rule_key}',
            metadata={
                'module': 'Intelligence',
                'rule_key': row.rule_key,
                'rule_exception_id': row.public_id,
                'risk_reference': reference,
                'expires_at': row.expires_at.isoformat(),
                'work_inbox': True,
            },
            deck_visible=True,
        )
        created += 1
    return created


def rule_exception_is_active(row: RuleException, *, now: datetime | None = None) -> bool:
    current = _as_utc(now or datetime.now(UTC))
    starts_at = _as_utc(row.starts_at)
    expires_at = _as_utc(row.expires_at)
    revoked_at = _as_utc(row.revoked_at) if row.revoked_at is not None else None
    return revoked_at is None and starts_at <= current < expires_at


def rule_exception_status(row: RuleException, *, now: datetime | None = None) -> tuple[str, str, str]:
    current = _as_utc(now or datetime.now(UTC))
    if row.revoked_at is not None:
        return 'revoked', 'Revoked', 'unknown'
    if _as_utc(row.expires_at) <= current:
        return 'expired', 'Expired', 'unknown'
    if _as_utc(row.starts_at) > current:
        return 'scheduled', 'Scheduled', 'info'
    if _as_utc(row.expires_at) - current <= _EXPIRING_WINDOW:
        return 'expiring', 'Expiring', 'warning'
    return 'active', 'Accepted Risk', 'info'


def build_rule_exception_view(
    rule_key: str,
    findings: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _as_utc(now or datetime.now(UTC))
    normalized_rule = str(rule_key or '').strip()
    rule_findings = [
        finding for finding in findings if base_rule_key(str(finding.get('rule_key') or '')) == normalized_rule
    ]
    rows = (
        RuleException.query.filter_by(rule_key=normalized_rule)
        .order_by(RuleException.created_at.desc(), RuleException.id.desc())
        .all()
    )
    active_rows = [row for row in rows if rule_exception_is_active(row, now=current)]
    active_ids = {row.id for row in active_rows}

    assets: dict[str, dict[str, Any]] = {}
    for finding in rule_findings:
        asset_key = finding_asset_key(finding)
        if not asset_key:
            continue
        asset = assets.setdefault(
            asset_key,
            {
                'asset_key': asset_key,
                'asset_name': finding_asset_name(finding),
                'findings': [],
            },
        )
        exception = matching_rule_exception(finding, rows=active_rows, now=current)
        asset['findings'].append(
            {
                'finding_key': str(finding.get('rule_key') or ''),
                'target': finding_target_label(finding),
                'severity': str(finding.get('severity') or 'info').title(),
                'exception_id': exception.id if exception is not None else None,
                'excepted': exception is not None,
            }
        )

    asset_rows = []
    for asset in sorted(assets.values(), key=lambda value: (value['asset_name'].lower(), value['asset_key'])):
        asset['findings'].sort(key=lambda value: value['target'].lower())
        asset['finding_count'] = len(asset['findings'])
        asset['excepted_count'] = sum(1 for finding in asset['findings'] if finding['excepted'])
        asset['uncovered_count'] = asset['finding_count'] - asset['excepted_count']
        asset_rows.append(asset)

    serialized = [_serialize_exception(row, rule_findings, now=current) for row in rows[:12]]
    covered_keys = {
        str(finding.get('rule_key') or '')
        for finding in rule_findings
        if matching_rule_exception(finding, rows=active_rows, now=current) is not None
    }
    expiring = sum(1 for row in active_rows if rule_exception_status(row, now=current)[0] == 'expiring')
    return {
        'active_count': len(active_rows),
        'expiring_count': expiring,
        'covered_findings': len(covered_keys),
        'uncovered_findings': max(len(rule_findings) - len(covered_keys), 0),
        'active_ids': active_ids,
        'exceptions': serialized,
        'assets': asset_rows,
        'owner_options': [
            {
                'id': user.id,
                'label': user.display_label,
            }
            for user in User.query.order_by(User.username.asc(), User.id.asc()).all()
            if user.is_active
        ],
        'has_candidates': bool(asset_rows),
    }


def _serialize_exception(
    row: RuleException,
    findings: list[dict[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    status, label, tone = rule_exception_status(row, now=now)
    covered = [
        finding
        for finding in findings
        if finding_asset_key(finding) == row.asset_key
        and (row.scope_mode == 'rule_asset' or str(finding.get('rule_key') or '') in set(row.finding_keys_json or []))
    ]
    owner = row.owner
    owner_label = str(getattr(owner, 'username', None) or getattr(owner, 'email', None) or 'Unassigned')
    return {
        'id': row.id,
        'public_id': row.public_id,
        'status': status,
        'status_label': label,
        'tone': tone,
        'scope_mode': row.scope_mode,
        'scope_label': 'Entire Asset' if row.scope_mode == 'rule_asset' else 'Selected Findings',
        'asset_key': row.asset_key,
        'asset_name': finding_asset_name(covered[0]) if covered else row.asset_key,
        'covered_count': len(covered) if row.scope_mode == 'finding_keys' else max(len(covered), 0),
        'reason': row.reason,
        'risk_reference': row.risk_reference or '-',
        'owner': owner_label,
        'starts_at': row.starts_at,
        'expires_at': row.expires_at,
        'revoked_at': row.revoked_at,
        'revocation_reason': row.revocation_reason or '',
        'active': rule_exception_is_active(row, now=now),
    }


def _evidence(finding: dict[str, Any]) -> dict[str, Any]:
    raw = finding.get('evidence')
    if not isinstance(raw, dict):
        return {}
    return {str(key): value for key, value in raw.items()}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
