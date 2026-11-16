"""Non-authorizing protected credential authority evidence projection (#4799).

This module never resolves secrets, opens SSH, or grants worker execution.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_REF = re.compile(r"secretref:[A-Za-z0-9][A-Za-z0-9/_-]{0,191}\Z")
_ALLOWED = frozenset({
    "authority_id", "credential_ref", "asset_id", "job_public_id",
    "source_sha", "ee_digest", "authorized", "revoked",
})


@dataclass(frozen=True, slots=True)
class CredentialAuthorityReview:
    state: str
    reason: str
    execution_authorized: bool = False


def review_credential_authority(
    evidence: object,
    *,
    expected_authority_id: str,
    expected_credential_ref: str,
    expected_asset_id: str,
    expected_job_public_id: str,
    expected_source_sha: str,
    expected_ee_digest: str,
) -> CredentialAuthorityReview:
    """Check exact identity binding; independent authority admission remains required.

    Evidence is a *projection* supplied by a trusted adapter, never browser
    payload or a credential itself. No caller can obtain Run permission here.
    """
    denied = CredentialAuthorityReview("blocked", "Credential authority evidence is not admissible")
    if not isinstance(evidence, Mapping) or set(evidence) != _ALLOWED:
        return denied
    expected = {
        "authority_id": expected_authority_id,
        "credential_ref": expected_credential_ref,
        "asset_id": expected_asset_id,
        "job_public_id": expected_job_public_id,
        "source_sha": expected_source_sha,
        "ee_digest": expected_ee_digest,
    }
    if not all(type(value) is str for value in expected.values()):
        return denied
    if not all(_ID.fullmatch(expected[k]) for k in ("authority_id", "asset_id", "job_public_id")):
        return denied
    if not _REF.fullmatch(expected_credential_ref):
        return denied
    if not _SHA.fullmatch(expected_source_sha) or not _DIGEST.fullmatch(expected_ee_digest):
        return denied
    if any(type(evidence.get(k)) is not str or evidence[k] != value for k, value in expected.items()):
        return denied
    if evidence.get("authorized") is not True or evidence.get("revoked") is not False:
        return denied
    return CredentialAuthorityReview(
        "requires_independent_admission",
        "Identity matches; independent secret authority, SSH trust and worker admission are still required",
    )
