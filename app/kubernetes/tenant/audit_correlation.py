from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


class TenantAuditNormalizationError(ValueError):
    """Kubernetes audit evidence cannot be normalized safely."""


@dataclass(frozen=True, slots=True)
class NormalizedTenantAuditEvent:
    event_uid: str
    source_id: str
    occurred_at: datetime
    username: str
    groups: tuple[str, ...]
    service_account_namespace: str | None
    service_account_name: str | None
    verb: str
    api_group: str | None
    api_version: str | None
    resource: str | None
    subresource: str | None
    namespace: str | None
    resource_name: str | None
    response_code: int | None
    outcome: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class TenantAuditPrincipalCandidate:
    tenant_id: str
    tenant_environment_id: int
    tenant_namespace_id: int
    namespace: str
    principal_kind: str
    subject_name: str
    membership_id: int | None = None
    access_grant_id: int | None = None
    credential_id: int | None = None
    credential_status: str | None = None
    membership_status: str | None = None
    grant_status: str | None = None


@dataclass(frozen=True, slots=True)
class TenantAuditCorrelationResult:
    status: str
    tenant_id: str | None = None
    tenant_environment_id: int | None = None
    tenant_namespace_id: int | None = None
    membership_id: int | None = None
    access_grant_id: int | None = None
    credential_id: int | None = None
    principal_kind: str = 'unknown'
    subject_name: str | None = None


def _value(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _timestamp(value: Any) -> datetime:
    raw = str(value or '').strip()
    if not raw:
        raise TenantAuditNormalizationError('Kubernetes audit event has no timestamp.')
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError as exc:
        raise TenantAuditNormalizationError('Kubernetes audit event timestamp is invalid.') from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _service_account(username: str) -> tuple[str | None, str | None]:
    prefix = 'system:serviceaccount:'
    if not username.startswith(prefix):
        return None, None
    remainder = username[len(prefix):]
    namespace, separator, name = remainder.partition(':')
    if not separator or not namespace or not name:
        return None, None
    return namespace, name


def _stable_uid(payload: dict[str, object]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def normalize_kubernetes_audit_event(
    event: dict[str, Any],
    *,
    source_id: str,
    retention_days: int,
) -> NormalizedTenantAuditEvent:
    normalized_source = source_id.strip()
    if not normalized_source:
        raise TenantAuditNormalizationError('Kubernetes audit source id is required.')
    days = int(retention_days)
    if days < 1 or days > 3650:
        raise TenantAuditNormalizationError('Kubernetes audit retention must be between 1 and 3650 days.')

    occurred_at = _timestamp(event.get('stageTimestamp') or event.get('requestReceivedTimestamp'))
    user = event.get('user') or {}
    username = str(_value(user, 'username', default='') or '').strip()
    if not username:
        raise TenantAuditNormalizationError('Kubernetes audit event has no authenticated username.')
    groups = tuple(sorted(str(item) for item in (_value(user, 'groups', default=[]) or []) if str(item)))

    object_ref = event.get('objectRef') or {}
    verb = str(event.get('verb') or '').strip().lower()
    if not verb:
        raise TenantAuditNormalizationError('Kubernetes audit event has no verb.')

    response = event.get('responseStatus') or {}
    raw_code = _value(response, 'code')
    try:
        response_code = int(raw_code) if raw_code is not None else None
    except (TypeError, ValueError):
        response_code = None
    if response_code is None:
        outcome = 'unknown'
    elif 200 <= response_code < 400:
        outcome = 'success'
    else:
        outcome = 'failed'

    sa_namespace, sa_name = _service_account(username)
    uid = str(event.get('auditID') or '').strip()
    if not uid:
        uid = _stable_uid(
            {
                'source_id': normalized_source,
                'occurred_at': occurred_at.isoformat(),
                'username': username,
                'verb': verb,
                'api_group': _value(object_ref, 'apiGroup'),
                'api_version': _value(object_ref, 'apiVersion'),
                'resource': _value(object_ref, 'resource'),
                'subresource': _value(object_ref, 'subresource'),
                'namespace': _value(object_ref, 'namespace'),
                'name': _value(object_ref, 'name'),
                'response_code': response_code,
            }
        )

    return NormalizedTenantAuditEvent(
        event_uid=uid,
        source_id=normalized_source,
        occurred_at=occurred_at,
        username=username,
        groups=groups,
        service_account_namespace=sa_namespace,
        service_account_name=sa_name,
        verb=verb,
        api_group=str(_value(object_ref, 'apiGroup') or '') or None,
        api_version=str(_value(object_ref, 'apiVersion') or '') or None,
        resource=str(_value(object_ref, 'resource') or '') or None,
        subresource=str(_value(object_ref, 'subresource') or '') or None,
        namespace=str(_value(object_ref, 'namespace') or '') or None,
        resource_name=str(_value(object_ref, 'name') or '') or None,
        response_code=response_code,
        outcome=outcome,
        expires_at=occurred_at + timedelta(days=days),
    )


def _candidate_matches(event: NormalizedTenantAuditEvent, candidate: TenantAuditPrincipalCandidate) -> bool:
    if event.namespace and candidate.namespace != event.namespace:
        return False
    if event.service_account_name is not None:
        return (
            candidate.principal_kind == 'service_account'
            and candidate.subject_name == event.service_account_name
        )
    if candidate.principal_kind == 'user':
        return candidate.subject_name == event.username
    if candidate.principal_kind == 'group':
        return candidate.subject_name in event.groups
    return False


def correlate_audit_principal(
    event: NormalizedTenantAuditEvent,
    candidates: list[TenantAuditPrincipalCandidate],
) -> TenantAuditCorrelationResult:
    matches = [candidate for candidate in candidates if _candidate_matches(event, candidate)]
    if not matches:
        return TenantAuditCorrelationResult(status='unmanaged')
    if len(matches) != 1:
        return TenantAuditCorrelationResult(status='ambiguous')

    selected = matches[0]
    revoked = (
        selected.credential_status in {'revoked', 'expired', 'suspended'}
        or selected.membership_status == 'revoked'
        or selected.grant_status == 'revoked'
    )
    status = 'managed_revoked' if revoked else 'managed'
    return TenantAuditCorrelationResult(
        status=status,
        tenant_id=selected.tenant_id,
        tenant_environment_id=selected.tenant_environment_id,
        tenant_namespace_id=selected.tenant_namespace_id,
        membership_id=selected.membership_id,
        access_grant_id=selected.access_grant_id,
        credential_id=selected.credential_id,
        principal_kind=selected.principal_kind,
        subject_name=selected.subject_name,
    )
