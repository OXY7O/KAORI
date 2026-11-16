"""Pure, fail-closed remote-facts admission contract (#4799).

This validates an authority-issued snapshot only. It does not query an asset
registry, resolve secrets, contact SSH, or authorize a worker dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import binascii
import re
from unicodedata import category, normalize

_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HOST_KEY = re.compile(r"SHA256:[A-Za-z0-9+/]{43}")
_REF = re.compile(r"[a-z][a-z0-9_-]{1,31}:[A-Za-z0-9][A-Za-z0-9._/-]{2,191}")



def _canonical_identity(value: str, maximum: int = 96) -> bool:
    return (
        bool(value)
        and len(value) <= maximum
        and value == value.strip()
        and value == normalize("NFC", value)
        and not any(category(character).startswith("C") for character in value)
    )


def _valid_host_key(value: str) -> bool:
    if not _HOST_KEY.fullmatch(value):
        return False
    try:
        # SHA-256 SSH fingerprints encode exactly 32 bytes, without padding.
        decoded = base64.b64decode(value[7:] + "=", validate=True)
        return len(decoded) == 32 and base64.b64encode(decoded).decode("ascii").rstrip("=") == value[7:]
    except (binascii.Error, ValueError):
        return False


def _safe_credential_reference(value: str) -> bool:
    if not _REF.fullmatch(value):
        return False
    # A secret locator is not a filesystem traversal or an implicit URI.
    locator = value.partition(":")[2]
    return all(segment not in {"", ".", ".."} for segment in locator.split("/"))


@dataclass(frozen=True, slots=True)
class RemoteFactsAdmission:
    """Non-secret, immutable candidate identity; not an execution permit."""

    asset_id: str
    target_id: str
    host_key_fingerprint: str
    credential_reference: str
    source_sha: str
    ee_digest: str
    authorized_asset_id: str
    authorized_target_id: str
    authorized_host_key_fingerprint: str
    authorized_credential_reference: str
    source_reviewed: bool
    ee_signature_verified: bool
    credential_scope_verified: bool
    host_key_trust_verified: bool


def qualify_remote_facts_admission(candidate: RemoteFactsAdmission) -> tuple[bool, str]:
    """Require exact matches to independent authority evidence, never self-attestation."""
    if not isinstance(candidate, RemoteFactsAdmission):
        return False, "invalid_admission"
    # Reject malformed caller-controlled types before applying string operations.
    identity_fields = (
        candidate.asset_id,
        candidate.target_id,
        candidate.host_key_fingerprint,
        candidate.credential_reference,
        candidate.source_sha,
        candidate.ee_digest,
        candidate.authorized_asset_id,
        candidate.authorized_target_id,
        candidate.authorized_host_key_fingerprint,
        candidate.authorized_credential_reference,
    )
    if any(not isinstance(value, str) for value in identity_fields):
        return False, "invalid_admission"
    if not _canonical_identity(candidate.asset_id):
        return False, "invalid_asset"
    if not _canonical_identity(candidate.target_id):
        return False, "invalid_target"
    if candidate.asset_id != candidate.authorized_asset_id or candidate.target_id != candidate.authorized_target_id:
        return False, "target_authority_mismatch"
    if not _valid_host_key(candidate.host_key_fingerprint):
        return False, "invalid_host_key"
    if candidate.host_key_fingerprint != candidate.authorized_host_key_fingerprint:
        return False, "host_key_mismatch"
    if not _safe_credential_reference(candidate.credential_reference):
        return False, "invalid_credential_reference"
    if candidate.credential_reference != candidate.authorized_credential_reference:
        return False, "credential_authority_mismatch"
    if not _SHA.fullmatch(candidate.source_sha) or not _DIGEST.fullmatch(candidate.ee_digest):
        return False, "unpinned_source_or_ee"
    authority_flags = (
        candidate.source_reviewed,
        candidate.ee_signature_verified,
        candidate.credential_scope_verified,
        candidate.host_key_trust_verified,
    )
    if any(flag is not True for flag in authority_flags):
        return False, "authority_evidence_missing"
    return True, "qualified_for_review_only"
