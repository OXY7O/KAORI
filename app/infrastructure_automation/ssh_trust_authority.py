"""Independent console evidence candidate for SSH host trust (#5185).

The deployment owner provides a restricted, read-only authority mount separate
from the Secrets issuer authority. No caller-selected key/path, SSH, TOFU,
active trust writer or execution permit.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.infrastructure_automation.host_enrollment import host_revision
from app.infrastructure_automation.ssh_host_key import qualify_ed25519_host_key
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    canonical_statement,
    verify_statement,
)
from app.models.automation import AutomationHostAccessBinding, AutomationInventoryAssignment
from app.security.authority_files import read_authority_file

_AUTHORITY_DIR = Path('/run/kaori/ssh-trust-authority')
_DIGEST = re.compile(r'[a-f0-9]{64}')
_SIGNATURE = re.compile(r'[a-f0-9]{128}')
_MAX_VALIDITY = timedelta(hours=24)


@dataclass(frozen=True, slots=True, repr=False)
class ConsoleTarget:
    connection_id: int
    assignment_id: int
    host_id: str
    host_revision: str
    reference_fingerprint: str
    address: str
    ssh_port: int
    host_key_digest: str
    revision_number: int
    requested_by_user_id: int
    verified_by_user_id: int


@dataclass(frozen=True, slots=True, repr=False)
class ConsoleEvidence:
    target: ConsoleTarget
    public_key: str
    evidence_ref: str
    verified_at: datetime
    expires_at: datetime


def console_target(
    assignment: AutomationInventoryAssignment,
    binding: AutomationHostAccessBinding,
    *,
    revision_number: int,
    requester_id: int,
    verifier_id: int,
) -> ConsoleTarget | None:
    """Build exact target from canonical records, never from browser fields."""
    if (
        any(type(value) is not int or value <= 0 for value in (revision_number, requester_id, verifier_id))
        or verifier_id in (requester_id, binding.recorded_by_user_id)
        or assignment.enabled is not True
        or binding.assignment_id != assignment.id
        or assignment.host.id != assignment.host_id
        or assignment.host.lifecycle_status != 'registered'
        or binding.host_revision != host_revision(assignment)
        or _DIGEST.fullmatch(binding.reference_fingerprint) is None
        or re.fullmatch(r'sha256:[a-f0-9]{64}', binding.host_key_digest) is None
    ):
        return None
    return ConsoleTarget(
        assignment.integration_instance_id,
        assignment.id,
        assignment.host_id,
        binding.host_revision,
        binding.reference_fingerprint,
        assignment.host.address,
        assignment.host.ssh_port,
        binding.host_key_digest,
        revision_number,
        requester_id,
        verifier_id,
    )


def console_evidence_name(target: ConsoleTarget) -> str:
    digest = sha256(canonical_statement({'target': asdict(target)})).hexdigest()
    return f'console-{digest}.json'


def _read_console_file(name: str) -> bytes | None:
    if name != 'root.pub' and re.fullmatch(r'console-[a-f0-9]{64}\.json', name) is None:
        return None
    return read_authority_file(_AUTHORITY_DIR, name)


def _utc_time(value: object) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    return result if result.utcoffset() == timedelta(0) and result.isoformat() == value else None


def resolve_console_evidence(target: ConsoleTarget, *, now: datetime) -> ConsoleEvidence | None:
    """Re-read exact independently signed artifact; return public review evidence only."""
    if not isinstance(target, ConsoleTarget) or not isinstance(now, datetime) or now.utcoffset() is None:
        return None
    pin, raw = _read_console_file('root.pub'), _read_console_file(console_evidence_name(target))
    if pin is None or raw is None:
        return None
    try:
        pin_text = pin.decode('ascii').strip()
        envelope = json.loads(raw)
        if _DIGEST.fullmatch(pin_text) is None or not isinstance(envelope, dict):
            return None
        if set(envelope) != {'payload', 'signature'} or canonical_statement(envelope) != raw.strip():
            return None
        payload, signature = envelope['payload'], envelope['signature']
        if not isinstance(payload, dict) or not isinstance(signature, str) or _SIGNATURE.fullmatch(signature) is None:
            return None
        if set(payload) != {
            'schema', 'state', 'target', 'source_kind', 'console_asset_ref',
            'public_key', 'verified_at', 'expires_at',
        }:
            return None
        if (
            payload['schema'] != 'kaori.automation.ssh_console_evidence.v1'
            or payload['state'] != 'active'
            or payload['source_kind'] != 'independent_console'
            or canonical_statement({'target': payload['target']}) != canonical_statement({'target': asdict(target)})
            or not isinstance(payload['console_asset_ref'], str)
            or _DIGEST.fullmatch(payload['console_asset_ref']) is None
            or not isinstance(payload['public_key'], str)
        ):
            return None
        verified, expires = _utc_time(payload['verified_at']), _utc_time(payload['expires_at'])
        key = qualify_ed25519_host_key(payload['public_key'], expected_digest=target.host_key_digest)
        if (
            verified is None or expires is None or key is None
            or not verified <= now < expires
            or not timedelta(0) < expires - verified <= _MAX_VALIDITY
            or not verify_statement(
                canonical_statement(payload),
                issued_at=verified,
                expires_at=expires,
                signature=bytes.fromhex(signature),
                verification_key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin_text)),
                now=now,
            )
        ):
            return None
        return ConsoleEvidence(target, key.public_key, 'sha256:' + sha256(raw.strip()).hexdigest(), verified, expires)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        return None
