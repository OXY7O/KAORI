"""Pure, fail-closed remote-facts admission contract (#4799).

This validates an authority-issued snapshot only. It does not query an asset
registry, resolve secrets, contact SSH, or authorize a worker dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HOST_KEY = re.compile(r"SHA256:[A-Za-z0-9+/]{43}=?")
_REF = re.compile(r"[a-z][a-z0-9_-]{1,31}:[A-Za-z0-9][A-Za-z0-9._/-]{2,191}")


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
    if not candidate.asset_id or len(candidate.asset_id) > 96 or candidate.asset_id != candidate.asset_id.strip():
        return False, "invalid_asset"
    if any(ord(c) < 33 or ord(c) == 127 for c in candidate.asset_id):
        return False, "invalid_asset"
    if not candidate.target_id or candidate.target_id != candidate.target_id.strip():
        return False, "invalid_target"
    if candidate.asset_id != candidate.authorized_asset_id or candidate.target_id != candidate.authorized_target_id:
        return False, "target_authority_mismatch"
    if not _HOST_KEY.fullmatch(candidate.host_key_fingerprint):
        return False, "invalid_host_key"
    if candidate.host_key_fingerprint != candidate.authorized_host_key_fingerprint:
        return False, "host_key_mismatch"
    if not _REF.fullmatch(candidate.credential_reference):
        return False, "invalid_credential_reference"
    if candidate.credential_reference != candidate.authorized_credential_reference:
        return False, "credential_authority_mismatch"
    if not _SHA.fullmatch(candidate.source_sha) or not _DIGEST.fullmatch(candidate.ee_digest):
        return False, "unpinned_source_or_ee"
    if not all((
        candidate.source_reviewed,
        candidate.ee_signature_verified,
        candidate.credential_scope_verified,
        candidate.host_key_trust_verified,
    )):
        return False, "authority_evidence_missing"
    return True, "qualified_for_review_only"
