"""Independent signed remote worker evidence candidate (#5186).

The receipt is externally attested review evidence, not measured runtime
identity, source acceptance, an approved target operation or a dispatch permit.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.infrastructure_automation.kubernetes.source_policy import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    SOURCE_CANDIDATE_SHA,
)
from app.infrastructure_automation.remote_preflight_source import REMOTE_CANDIDATE_SHA, RemoteSourceReview
from app.infrastructure_automation.remote_preflight_target import RemoteTargetReview
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    canonical_statement,
    verify_statement,
)
from app.security.authority_files import read_authority_file

_AUTHORITY_DIR = Path('/run/kaori/automation-worker-authority')
_HEX = re.compile(r'[a-f0-9]{64}')
_WORKER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._@-]{0,127}')
_SIGNATURE = re.compile(r'[a-f0-9]{128}')
_MAX_VALIDITY = timedelta(hours=1)


@dataclass(frozen=True, slots=True, repr=False)
class WorkerReviewEvidence:
    fingerprint: str
    expires_at: datetime
    execution_authorized: bool = False


def _utc_time(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timedelta(0) and parsed.isoformat() == value else None


def _read_worker_file(name: str) -> bytes | None:
    if name != 'root.pub' and re.fullmatch(r'worker-[a-f0-9]{64}\.json', name) is None:
        return None
    return read_authority_file(_AUTHORITY_DIR, name)


def worker_review_selector(
    source: RemoteSourceReview, target: RemoteTargetReview, *, worker_identity: str
) -> dict[str, object]:
    """Only the trusted internal caller may derive the worker identity."""
    return {
        'repository': 'OXY7O/kaori-operations',
        'remote_candidate_sha': source.revision,
        'source_review_fingerprint': source.fingerprint,
        'committed_profile_sha': target.source_sha,
        'execution_environment_digest': target.ee_digest,
        'ansible_core_version': ANSIBLE_CORE_VERSION,
        'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
        'worker_identity': worker_identity,
        'queue': 'automation',
        'connection_id': target.connection_id,
        'actor_id': target.actor_id,
        'target_review_fingerprint': target.access_fingerprint,
        'inventory_fingerprint': target.inventory_fingerprint,
        'host_registry_fingerprint': target.host_registry_fingerprint,
    }


def resolve_remote_worker_review(
    source: RemoteSourceReview,
    target: RemoteTargetReview,
    *,
    worker_identity: str,
    now: datetime,
) -> WorkerReviewEvidence | None:
    """Verify external signed review of this exact source, EE and target scope.

    The external operator is responsible for authenticating runtime identity,
    native OCI signature/provenance and disposable host ownership. This reader
    intentionally does not claim to perform those measurements itself.
    """
    if (
        not isinstance(source, RemoteSourceReview)
        or not isinstance(target, RemoteTargetReview)
        or not isinstance(now, datetime)
        or now.utcoffset() is None
        or not isinstance(worker_identity, str)
        or _WORKER.fullmatch(worker_identity) is None
        or source.revision != REMOTE_CANDIDATE_SHA
        or target.source_sha != SOURCE_CANDIDATE_SHA
        or source.execution_authorized is not False
        or target.execution_authorized is not False
        or target.expires_at.utcoffset() is None
        or target.expires_at <= now
        or any(
            not isinstance(value, str) or _HEX.fullmatch(value) is None
            for value in (
                source.fingerprint, target.access_fingerprint,
                target.inventory_fingerprint, target.host_registry_fingerprint,
            )
        )
        or re.fullmatch(r'sha256:[a-f0-9]{64}', target.ee_digest) is None
    ):
        return None
    selector = worker_review_selector(source, target, worker_identity=worker_identity)
    name = 'worker-' + sha256(canonical_statement(selector)).hexdigest() + '.json'
    pin, raw = _read_worker_file('root.pub'), _read_worker_file(name)
    if pin is None or raw is None:
        return None
    try:
        key = pin.decode('ascii').strip()
        envelope = json.loads(raw)
        if _HEX.fullmatch(key) is None or not isinstance(envelope, dict):
            return None
        if set(envelope) != {'payload', 'signature'} or canonical_statement(envelope) != raw.strip():
            return None
        payload, signature = envelope['payload'], envelope['signature']
        if not isinstance(payload, dict) or not isinstance(signature, str) or _SIGNATURE.fullmatch(signature) is None:
            return None
        if set(payload) != {
            'schema', 'state', 'selector', 'provenance_evidence_ref',
            'target_authority_ref', 'reviewer_id', 'issued_at', 'expires_at',
        }:
            return None
        if (
            payload['schema'] != 'kaori.automation.remote_worker_review.v1'
            or payload['state'] != 'active'
            or canonical_statement({'selector': payload['selector']}) != canonical_statement({'selector': selector})
            or type(payload['reviewer_id']) is not int
            or payload['reviewer_id'] <= 0
            or payload['reviewer_id'] == target.actor_id
            or any(
                not isinstance(payload[field], str) or _HEX.fullmatch(payload[field]) is None
                for field in ('provenance_evidence_ref', 'target_authority_ref')
            )
        ):
            return None
        issued, expires = _utc_time(payload['issued_at']), _utc_time(payload['expires_at'])
        if (
            issued is None or expires is None
            or not issued <= now < expires <= target.expires_at
            or not timedelta(0) < expires - issued <= _MAX_VALIDITY
            or not verify_statement(
                canonical_statement(payload),
                issued_at=issued,
                expires_at=expires,
                signature=bytes.fromhex(signature),
                verification_key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)),
                now=now,
            )
        ):
            return None
        return WorkerReviewEvidence(sha256(raw.strip()).hexdigest(), expires)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        return None
