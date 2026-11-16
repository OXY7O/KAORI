"""Negative authority-binding regression coverage; no credential resolution."""
from app.infrastructure_automation.kubernetes.remote_facts_credential_authority import (
    review_credential_authority,
)

BASE = {
    "authority_id": "vault-prod",
    "credential_ref": "secretref:kaori/nonprod/host-01",
    "asset_id": "asset-01",
    "job_public_id": "job-01",
    "source_sha": "a" * 40,
    "ee_digest": "sha256:" + "b" * 64,
}
EVIDENCE = {**BASE, "authorized": True, "revoked": False}


def review(evidence, **changes):
    return review_credential_authority(evidence, **{**BASE, **changes})


def test_exact_evidence_is_never_run_permission():
    result = review(EVIDENCE)
    assert result.state == "requires_independent_admission"
    assert result.execution_authorized is False


def test_source_or_job_or_asset_drift_fails_closed():
    for field in ("asset_id", "job_public_id", "source_sha", "ee_digest", "credential_ref", "authority_id"):
        assert review({**EVIDENCE, field: "wrong"}).state == "blocked"


def test_revocation_and_false_or_nonboolean_flags_fail_closed():
    for changes in (
        {"revoked": True}, {"authorized": False}, {"authorized": 1},
        {"revoked": 0}, {"authorized": "true"},
    ):
        assert review({**EVIDENCE, **changes}).state == "blocked"


def test_unknown_secret_fields_and_malformed_payloads_fail_closed():
    for evidence in (
        None, [], {}, {**EVIDENCE, "private_key": "secret"},
        {**EVIDENCE, "credential_ref": ["secretref:kaori"]},
    ):
        assert review(evidence).state == "blocked"


def test_untrusted_expected_identity_fails_closed():
    for field, value in (
        ("credential_ref", "ssh-rsa PRIVATE"),
        ("credential_ref", "secretref:../escape"),
        ("source_sha", "A" * 40),
        ("ee_digest", "sha256:bad"),
        ("asset_id", "host\nspoof"),
    ):
        assert review(EVIDENCE, **{field: value}).state == "blocked"
