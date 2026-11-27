"""Read-only pre-registration qualification for the selected OpenBao release."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPTransport, SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.kv2_transport import validate_auth_mount
from app.integrations.secrets_management.secrets_pki.providers.openbao.client import (
    OpenBaoClient,
    _read_metadata,
    _verify_inspection_authority,
    _verify_internal_audit,
)

_VERSION = '2.7.3'
_INTERNAL_ENDPOINT = 'https://secret-store:8200'


@dataclass(frozen=True, slots=True, repr=False)
class OpenBaoQualificationTarget:
    ownership: str
    endpoint: str
    cluster_id: str
    kv_mount: str
    auth_mount: str
    audit_mount: str


@dataclass(frozen=True, slots=True)
class OpenBaoQualificationObservation:
    version: str
    observed_at: datetime
    evidence_ref: str


def _require_target(target: OpenBaoQualificationTarget) -> None:
    if target.ownership not in {'internal', 'external'}:
        raise SecretProviderError('Explicit OpenBao ownership is required.')
    try:
        canonical_cluster = str(UUID(target.cluster_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise SecretProviderError('An independently established cluster UUID is required.') from exc
    if canonical_cluster != target.cluster_id:
        raise SecretProviderError('A canonical cluster UUID is required.')
    for mount in (target.kv_mount, target.auth_mount, target.audit_mount):
        if validate_auth_mount(mount) != mount:
            raise SecretProviderError('Exact mount segments are required.')
    if target.ownership == 'internal':
        if target.endpoint != _INTERNAL_ENDPOINT or target.audit_mount != 'kaori-operator':
            raise SecretProviderError('Internal candidate does not match the deployment contract.')
    elif target.endpoint == _INTERNAL_ENDPOINT:
        raise SecretProviderError('The bundled endpoint cannot be treated as external.')


def _require_current_cluster(transport: KV2HTTPTransport, *, cluster_id: str) -> None:
    status, data = transport._request('/v1/sys/health')
    if (
        status != 200
        or data.get('initialized') is not True
        or data.get('sealed') is not False
        or data.get('standby') is not False
        or data.get('performance_standby', False) is not False
        or data.get('version') != _VERSION
        or data.get('cluster_id') != cluster_id
    ):
        raise SecretProviderError('OpenBao active version or independently expected cluster did not match.')


def _require_exact_mounts(
    transport: KV2HTTPTransport, target: OpenBaoQualificationTarget, *, token: str
) -> None:
    kv = _read_metadata(transport, token, '/v1/sys/mounts').get(target.kv_mount + '/')
    auth = _read_metadata(transport, token, '/v1/sys/auth').get(target.auth_mount + '/')
    if (
        not isinstance(kv, dict)
        or kv.get('type') != 'kv'
        or not isinstance(kv.get('options'), dict)
        or kv['options'].get('version') != '2'
        or not isinstance(auth, dict)
        or auth.get('type') != 'approle'
    ):
        raise SecretProviderError('Exact approved KV v2 or AppRole mount is not available.')
    audits = _read_metadata(transport, token, '/v1/sys/audit')
    if target.ownership == 'internal':
        _verify_internal_audit(audits)
        return
    audit = audits.get(target.audit_mount + '/')
    if (
        not isinstance(audit, dict)
        or audit.get('type') not in ('file', 'socket', 'syslog')
        or not isinstance(audit.get('options'), dict)
        or audit['options'].get('log_raw', 'false') != 'false'
    ):
        raise SecretProviderError('Expected non-raw audit configuration was not observed.')


def inspect_registration_candidate(
    target: OpenBaoQualificationTarget, *, token: str
) -> OpenBaoQualificationObservation:
    """Observe exact deployment metadata; never emit or persist provider material."""
    _require_target(target)
    if (
        not isinstance(token, str)
        or not 1 <= len(token) <= 4096
        or not token.isascii()
        or any(ord(char) < 33 or ord(char) > 126 for char in token)
    ):
        raise SecretProviderError('A transient inspection token is required.')
    if not os.getenv(OpenBaoClient.ca_bundle_env, '').strip():
        raise SecretProviderError('Explicit OpenBao CA trust is required.')
    transport = KV2HTTPTransport(
        endpoint=target.endpoint,
        provider_label=OpenBaoClient.provider_label,
        allowed_origins_env=OpenBaoClient.allowed_origins_env,
        ca_bundle_env=OpenBaoClient.ca_bundle_env,
    )
    if transport.endpoint != target.endpoint:
        raise SecretProviderError('The expected origin must be canonical.')
    _require_current_cluster(transport, cluster_id=target.cluster_id)
    _verify_inspection_authority(transport, token, max_ttl=3600)
    _require_exact_mounts(transport, target, token=token)
    _require_current_cluster(transport, cluster_id=target.cluster_id)
    _verify_inspection_authority(transport, token, max_ttl=3600)
    observed_at = datetime.now(UTC)
    # A correlation reference, never a signature or authorization decision.
    statement = {
        'schema': 'kaori.openbao.registration_observation.v1',
        'provider': 'openbao',
        'ownership': target.ownership,
        'origin': target.endpoint,
        'cluster_id': target.cluster_id,
        'version': _VERSION,
        'kv_mount': target.kv_mount,
        'auth_mount': target.auth_mount,
        'audit_mount': target.audit_mount,
        'observed_at': observed_at.isoformat(),
    }
    canonical = json.dumps(statement, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    return OpenBaoQualificationObservation(_VERSION, observed_at, sha256(canonical).hexdigest())
