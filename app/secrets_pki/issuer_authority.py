"""Independent deployment-owned issuer authority resolution (#5245).

Only the fixed operator-managed, read-only authority directory may supply
pins and current signed enrollment/custody receipts. Application callers
cannot choose a verification key, path, or assert that evidence is verified.
No private key, credential material, generic signing or provider write.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.access.scope_policy import CredentialIssuerScope
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    canonical_statement,
    verify_statement,
)
from app.integrations.secrets_management.secrets_pki.providers.issuer_transit import (
    TransitIssuerBinding,
    TransitIssuerObservation,
    valid_transit_binding,
)
from app.secrets_pki.credential_issuer_resolution import IssuerPossessionChallenge

_AUTHORITY_DIR = Path('/run/kaori/issuer-authority')
_DIGEST = re.compile(r'[a-f0-9]{64}')
_SIGNATURE = re.compile(r'[a-f0-9]{128}')
_MAX_BYTES = 16384
_MAX_RECEIPT_LIFETIME = timedelta(hours=24)
_MAX_OBSERVATION_AGE = timedelta(seconds=60)
_DEPLOYMENT_SCHEMA = 'kaori.secrets.issuer_deployment.v1'
_CUSTODY_SCHEMA = 'kaori.secrets.issuer_custody.v1'


@dataclass(frozen=True, slots=True, repr=False)
class DeploymentAuthority:
    scope: CredentialIssuerScope
    transit: TransitIssuerBinding
    source_owner_id: int
    checker_id: int
    issued_at: datetime
    expires_at: datetime
    evidence_ref: str


@dataclass(frozen=True, slots=True, repr=False)
class CustodyAuthority:
    deployment: DeploymentAuthority
    revision_number: int
    challenge_sha256: str
    issued_at: datetime
    expires_at: datetime
    evidence_ref: str


def _digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _actor(value: object) -> bool:
    return type(value) is int and value > 0


def _safe_file(info: os.stat_result, *, directory: bool = False) -> bool:
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    return expected_type(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022


def _read_authority_file(name: str) -> bytes | None:
    """Fixed names only, refuse writable mount, symlinks, non-root owner and oversized files."""
    if name != 'root.pub' and re.fullmatch(r'(deployment|custody)-[a-f0-9]{64}\.json', name) is None:
        return None
    directory_fd = None
    file_fd = None
    try:
        directory_fd = os.open(_AUTHORITY_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if not _safe_file(os.fstat(directory_fd), directory=True):
            return None
        if not os.fstatvfs(directory_fd).f_flag & os.ST_RDONLY:
            return None
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        info = os.fstat(file_fd)
        if not _safe_file(info) or not 0 < info.st_size <= _MAX_BYTES:
            return None
        with os.fdopen(file_fd, 'rb') as stream:
            file_fd = None
            content = stream.read(_MAX_BYTES + 1)
        return content if 0 < len(content) <= _MAX_BYTES else None
    except (OSError, AttributeError, ValueError):
        return None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _utc_time(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timedelta(0) and parsed.isoformat() == value else None


def _signed_payload(name: str, schema: str, now: datetime) -> tuple[dict[str, object], datetime, datetime, str] | None:
    """Re-read independent pin and current receipt for every decision; no caching."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        return None
    pin = _read_authority_file('root.pub')
    raw = _read_authority_file(name)
    if pin is None or raw is None:
        return None
    try:
        pin_text = pin.decode('ascii').strip()
        envelope = json.loads(raw)
        if not _digest(pin_text) or not isinstance(envelope, dict) or set(envelope) != {'payload', 'signature'}:
            return None
        # Canonical wire encoding denies duplicate fields and alternate JSON representations.
        if canonical_statement(envelope) != raw.strip():
            return None
        payload, signature = envelope['payload'], envelope['signature']
        if not isinstance(payload, dict) or not isinstance(signature, str) or not _SIGNATURE.fullmatch(signature):
            return None
        if payload.get('schema') != schema or payload.get('state') != 'active':
            return None
        issued, expires = _utc_time(payload.get('issued_at')), _utc_time(payload.get('expires_at'))
        if issued is None or expires is None or not timedelta(0) < expires - issued <= _MAX_RECEIPT_LIFETIME:
            return None
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin_text))
        if not verify_statement(
            canonical_statement(payload),
            issued_at=issued,
            expires_at=expires,
            signature=bytes.fromhex(signature),
            verification_key=key,
            now=now,
        ):
            return None
        # The independent recovery authority must not be the candidate issuer.
        if payload.get('key_sha256') == sha256(key.public_bytes_raw()).hexdigest():
            return None
        return payload, issued, expires, sha256(raw.strip()).hexdigest()
    except (UnicodeError, ValueError, TypeError, RecursionError):
        return None


def deployment_identity_ref(scope: CredentialIssuerScope, transit: TransitIssuerBinding) -> str:
    """Canonical deployment identity excludes rotating issuer key material."""
    return sha256(
        canonical_statement(
            {
                'schema': 'kaori.secrets.deployment_identity.v1',
                'instance_id': scope.instance_id,
                'provider_key': scope.provider_key,
                'provider_namespace': scope.provider_namespace,
                'mount': scope.mount,
                'endpoint': transit.endpoint,
                'cluster_id': transit.cluster_id,
            }
        )
    ).hexdigest()


def _deployment_fields(payload: dict[str, object], scope: CredentialIssuerScope) -> TransitIssuerBinding | None:
    if set(payload) != {
        'schema',
        'state',
        'scope',
        'transit',
        'key_sha256',
        'source_owner_id',
        'checker_id',
        'issued_at',
        'expires_at',
    }:
        return None
    if canonical_statement({'scope': payload['scope']}) != canonical_statement({'scope': asdict(scope)}):
        return None
    if not isinstance(payload['transit'], dict):
        return None
    fields = payload['transit']
    if set(fields) != {
        'provider_key',
        'endpoint',
        'cluster_id',
        'namespace',
        'transit_mount',
        'key_name',
        'key_version',
        'key_sha256',
    }:
        return None
    transit = TransitIssuerBinding(**fields)
    if (
        not valid_transit_binding(transit)
        or transit.provider_key != scope.provider_key
        or transit.namespace != scope.provider_namespace
        or payload['key_sha256'] != transit.key_sha256
        or deployment_identity_ref(scope, transit) != scope.deployment_ref
    ):
        return None
    return transit


def resolve_deployment_authority(scope: CredentialIssuerScope, *, now: datetime) -> DeploymentAuthority | None:
    """Independently pinned, current operator-signed exact deployment enrollment."""
    if (
        not isinstance(scope, CredentialIssuerScope)
        or not _digest(scope.deployment_ref)
        or type(scope.instance_id) is not int
        or scope.instance_id <= 0
        or scope.provider_key not in ('vault', 'openbao')
        or not isinstance(scope.provider_namespace, str)
        or not isinstance(scope.mount, str)
        or not scope.mount
        or any(ord(char) < 32 or ord(char) == 127 or char in '*+' for char in scope.provider_namespace + scope.mount)
    ):
        return None
    result = _signed_payload(f'deployment-{scope.deployment_ref}.json', _DEPLOYMENT_SCHEMA, now)
    if result is None:
        return None
    payload, issued, expires, evidence_ref = result
    transit = _deployment_fields(payload, scope)
    owner, checker = payload.get('source_owner_id'), payload.get('checker_id')
    if transit is None or type(owner) is not int or type(checker) is not int:
        return None
    if not _actor(owner) or not _actor(checker) or owner == checker:
        return None
    return DeploymentAuthority(scope, transit, owner, checker, issued, expires, evidence_ref)


def resolve_custody_authority(
    expected: IssuerPossessionChallenge, *, checker_id: int, observation: TransitIssuerObservation, now: datetime
) -> CustodyAuthority | None:
    """Bind fresh independent receipt to expected committed challenge and native read.

    Internal caller must reconstruct expected from locked persisted intent,
    obtain the native observation itself before DB locks, and authenticate
    actors with canonical Access. No caller-supplied authority is sufficient.
    """
    if (
        not isinstance(expected, IssuerPossessionChallenge)
        or not _digest(expected.challenge_sha256)
        or not isinstance(now, datetime)
        or now.utcoffset() is None
        or not isinstance(expected.issued_at, datetime)
        or expected.issued_at.utcoffset() is None
        or not isinstance(expected.expires_at, datetime)
        or expected.expires_at.utcoffset() is None
        or not expected.issued_at <= now < expected.expires_at
    ):
        return None
    target = expected.target
    scope = CredentialIssuerScope(
        target.integration_instance_id, target.provider_key, target.provider_namespace, target.mount, target.deployment_ref
    )
    deployment = resolve_deployment_authority(scope, now=now)
    if (
        deployment is None
        or deployment.source_owner_id != expected.source_owner_id
        or deployment.checker_id != checker_id
        or deployment.transit.key_sha256 != expected.key_sha256
        or not isinstance(observation, TransitIssuerObservation)
        or observation.binding != deployment.transit
        or not _digest(observation.public_key_hex)
        or sha256(bytes.fromhex(observation.public_key_hex)).hexdigest() != expected.key_sha256
        or not isinstance(observation.observed_at, datetime)
        or observation.observed_at.utcoffset() is None
        or not timedelta(0) <= now - observation.observed_at <= _MAX_OBSERVATION_AGE
    ):
        return None
    result = _signed_payload(f'custody-{expected.challenge_sha256}.json', _CUSTODY_SCHEMA, now)
    if result is None:
        return None
    payload, issued, expires, evidence_ref = result
    if (
        set(payload) != {
            'schema',
            'state',
            'deployment_evidence_ref',
            'key_sha256',
            'revision_number',
            'challenge_sha256',
            'source_owner_id',
            'checker_id',
            'issued_at',
            'expires_at',
        }
        or payload['deployment_evidence_ref'] != deployment.evidence_ref
        or payload['key_sha256'] != expected.key_sha256
        or type(payload['revision_number']) is not int
        or payload['revision_number'] != target.revision_number
        or payload['challenge_sha256'] != expected.challenge_sha256
        or type(payload['source_owner_id']) is not int
        or payload['source_owner_id'] != expected.source_owner_id
        or type(payload['checker_id']) is not int
        or payload['checker_id'] != checker_id
        or not expected.issued_at <= issued <= now < expires <= min(expected.expires_at, deployment.expires_at)
    ):
        return None
    return CustodyAuthority(deployment, target.revision_number, expected.challenge_sha256, issued, expires, evidence_ref)
