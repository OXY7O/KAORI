"""Negative and positive source-only contract for #4799 remote admission."""
from dataclasses import replace

import pytest

from app.integrations.orchestration.configuration_automation.providers.ansible.remote_admission import (
    RemoteFactsAdmission,
    qualify_remote_facts_admission,
)


@pytest.fixture
def admitted_snapshot():
    return RemoteFactsAdmission(
        asset_id="asset-001",
        target_id="host-001",
        host_key_fingerprint="SHA256:" + "A" * 43,
        credential_reference="vault:infrastructure/ssh/host-001",
        source_sha="a" * 40,
        ee_digest="sha256:" + "b" * 64,
        authorized_asset_id="asset-001",
        authorized_target_id="host-001",
        authorized_host_key_fingerprint="SHA256:" + "A" * 43,
        authorized_credential_reference="vault:infrastructure/ssh/host-001",
        source_reviewed=True,
        ee_signature_verified=True,
        credential_scope_verified=True,
        host_key_trust_verified=True,
    )


def test_exact_authority_snapshot_is_only_review_qualified(admitted_snapshot):
    assert qualify_remote_facts_admission(admitted_snapshot) == (True, "qualified_for_review_only")


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"asset_id": "asset-002"}, "target_authority_mismatch"),
        ({"target_id": "host-002"}, "target_authority_mismatch"),
        ({"asset_id": " asset-001"}, "invalid_asset"),
        ({"host_key_fingerprint": "SHA256:" + "B" * 43}, "host_key_mismatch"),
        ({"host_key_fingerprint": "ssh-rsa AAAA"}, "invalid_host_key"),
        ({"credential_reference": "vault:infrastructure/ssh/other"}, "credential_authority_mismatch"),
        ({"credential_reference": "-----BEGIN PRIVATE KEY-----"}, "invalid_credential_reference"),
        ({"source_sha": "main"}, "unpinned_source_or_ee"),
        ({"ee_digest": "latest"}, "unpinned_source_or_ee"),
        ({"source_reviewed": False}, "authority_evidence_missing"),
        ({"ee_signature_verified": False}, "authority_evidence_missing"),
        ({"credential_scope_verified": False}, "authority_evidence_missing"),
        ({"host_key_trust_verified": False}, "authority_evidence_missing"),
    ],
)
def test_untrusted_snapshot_fails_closed(admitted_snapshot, change, reason):
    assert qualify_remote_facts_admission(replace(admitted_snapshot, **change)) == (False, reason)


def test_arbitrary_payload_cannot_claim_admission():
    assert qualify_remote_facts_admission({"source_reviewed": True}) == (False, "invalid_admission")
