from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


class TenantAuditNormalizationError(ValueError):
    """Kubernetes audit evidence cannot be normalized without guessing identity."""


@dataclass(frozen=True, slots=True)
class NormalizedKubernetesAuditEvent:
    source_event_id: str | None
    idempotency_key: str
    source_reference: str | None
    principal_username: str
    principal_groups: tuple[str, ...]
    principal_kind: str
    namespace: str | None
    resource_group: str | None
    resource_version: str | None
    resource: str | None
    subresource: str | None
    resource_name: str | None
    verb: str
    response_code: int | None
    outcome: str
    event_at: datetime

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload['principal_groups'] = list(self.principal_groups)
        payload['event_at'] = self.event_at.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class CorrelationCandidate:
    credential_id: int
    credential_public_id: str
    credential_status: str
    credential_type: str
    tenant_id: str
    namespace_id: int | None
    owner_user_id: int
    access_grant_id: int | None
    application_name: str | None
    jumpserver_reference: str | None


@dataclass(frozen=True, slots=True)
class CorrelationChoice:
    status: str
    credential_id: int | None = None
    credential_public_id: str | None = None
    credential_status: str | None = None
    credential_type: str | None = None
    tenant_id: str | None = None
    namespace_id: int | None = None
    owner_user_id: int | None = None
    access_grant_id: int | None = None
    application_name: str | None = None
    jumpserver_reference: str | None = None


def _text(value: object, *, limit: int) -> str | None:
    normalized = str(value or '').strip()
    return normalized[:limit] if normalized else None


def _parse_timestamp(value: object) -> datetime:
    text = _text(value, limit=80)
    if not text:
        raise TenantAuditNormalizationError('Kubernetes audit event timestamp is required.')
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError as exc:
        raise TenantAuditNormalizationError('Kubernetes audit event timestamp is invalid.') from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def service_account_identity(principal_username: str) -> tuple[str, str] | None:
    prefix = 'system:serviceaccount:'
    if not principal_username.startswith(prefix):
        return None
    parts = principal_username[len(prefix) :].split(':')
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0], parts[1]


def _safe_digest(payload: dict[str, object]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(rendered.encode()).hexdigest()


def normalize_kubernetes_audit_event(
    event: dict[str, Any],
    *,
    source_reference: str | None = None,
) -> NormalizedKubernetesAuditEvent:
    user = event.get('user') if isinstance(event.get('user'), dict) else {}
    principal = _text(user.get('username'), limit=500)
    if not principal:
        raise TenantAuditNormalizationError('Kubernetes audit principal username is required.')

    groups_value = user.get('groups') if isinstance(user.get('groups'), list) else []
    groups = tuple(sorted({_text(item, limit=255) for item in groups_value if _text(item, limit=255)}))
    obj = event.get('objectRef') if isinstance(event.get('objectRef'), dict) else {}
    response = event.get('responseStatus') if isinstance(event.get('responseStatus'), dict) else {}
    verb = _text(event.get('verb'), limit=40)
    if not verb:
        raise TenantAuditNormalizationError('Kubernetes audit verb is required.')

    event_at = _parse_timestamp(event.get('stageTimestamp') or event.get('requestReceivedTimestamp'))
    response_code = response.get('code')
    try:
        code = int(response_code) if response_code is not None else None
    except (TypeError, ValueError):
        code = None
    outcome = 'unknown' if code is None else ('success' if code < 400 else 'failure')
    namespace = _text(obj.get('namespace'), limit=253)
    resource_group = _text(obj.get('apiGroup'), limit=120)
    resource_version = _text(obj.get('apiVersion'), limit=80)
    resource = _text(obj.get('resource'), limit=120)
    subresource = _text(obj.get('subresource'), limit=120)
    resource_name = _text(obj.get('name'), limit=253)
    source_event_id = _text(event.get('auditID'), limit=160)
    principal_kind = 'service_account' if service_account_identity(principal) else 'user'

    safe = {
        'principal_username': principal,
        'principal_groups': list(groups),
        'namespace': namespace,
        'resource_group': resource_group,
        'resource_version': resource_version,
        'resource': resource,
        'subresource': subresource,
        'resource_name': resource_name,
        'verb': verb,
        'response_code': code,
        'event_at': event_at.isoformat(),
    }
    idempotency_key = _safe_digest({'audit_id': source_event_id} if source_event_id else safe)
    return NormalizedKubernetesAuditEvent(
        source_event_id=source_event_id,
        idempotency_key=idempotency_key,
        source_reference=_text(source_reference, limit=500),
        principal_username=principal,
        principal_groups=groups,
        principal_kind=principal_kind,
        namespace=namespace,
        resource_group=resource_group,
        resource_version=resource_version,
        resource=resource,
        subresource=subresource,
        resource_name=resource_name,
        verb=verb,
        response_code=code,
        outcome=outcome,
        event_at=event_at,
    )


def choose_correlation_candidate(candidates: list[CorrelationCandidate]) -> CorrelationChoice:
    if not candidates:
        return CorrelationChoice(status='unmanaged')
    if len(candidates) != 1:
        return CorrelationChoice(status='ambiguous')
    candidate = candidates[0]
    return CorrelationChoice(
        status='matched',
        credential_id=candidate.credential_id,
        credential_public_id=candidate.credential_public_id,
        credential_status=candidate.credential_status,
        credential_type=candidate.credential_type,
        tenant_id=candidate.tenant_id,
        namespace_id=candidate.namespace_id,
        owner_user_id=candidate.owner_user_id,
        access_grant_id=candidate.access_grant_id,
        application_name=candidate.application_name,
        jumpserver_reference=candidate.jumpserver_reference,
    )
