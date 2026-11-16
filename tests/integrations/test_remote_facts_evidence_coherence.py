"""Negative cross-record identity coherence contracts for #4799."""
from copy import deepcopy

import pytest

from app.integrations.ansible.remote_facts_evidence_coherence import compare_remote_facts_evidence


def sample():
    return {
        "job_execution_id": "job-42",
        "attempt": 2,
        "integration_binding_id": "binding-3",
        "asset_id": "asset-7",
        "source_sha": "a" * 40,
        "ee_digest": "sha256:" + "b" * 64,
        "inventory_fingerprint": "sha256:" + "c" * 64,
    }


def decision(job, host, authority):
    return compare_remote_facts_evidence(job=job, host=host, authority=authority)


def test_exact_identity_is_not_execution_authority():
    record = sample()
    result = decision(record, deepcopy(record), deepcopy(record))
    assert result.status == "requires_independent_admission"
    assert result.execution_authorized is False


@pytest.mark.parametrize("field,value", [
    ("job_execution_id", "job-43"),
    ("attempt", 3),
    ("integration_binding_id", "binding-4"),
    ("asset_id", "asset-8"),
    ("source_sha", "d" * 40),
    ("ee_digest", "sha256:" + "d" * 64),
    ("inventory_fingerprint", "sha256:" + "d" * 64),
])
def test_host_identity_drift_blocks(field, value):
    record = sample()
    host = deepcopy(record)
    host[field] = value
    assert decision(record, host, record).status == "blocked"


def test_authority_identity_drift_blocks():
    record = sample()
    authority = deepcopy(record)
    authority["asset_id"] = "asset-other"
    assert decision(record, record, authority).status == "blocked"


@pytest.mark.parametrize("field,value", [
    ("attempt", True), ("attempt", 0), ("attempt", "2"),
    ("source_sha", "A" * 40), ("source_sha", "not-a-sha"),
    ("ee_digest", "sha256:bad"), ("inventory_fingerprint", "sha256:bad"),
    ("asset_id", ""), ("asset_id", "x" * 257),
])
def test_malformed_matching_records_still_block(field, value):
    record = sample()
    record[field] = value
    assert decision(record, record, record).status == "blocked"


@pytest.mark.parametrize("invalid", [None, [], "record", {"asset_id": "asset-7"}])
def test_incomplete_or_wrong_record_type_blocks(invalid):
    record = sample()
    assert decision(record, invalid, record).status == "blocked"


def test_unknown_or_secret_bearing_fields_block():
    record = sample()
    record["ssh_private_key"] = "secret"
    assert decision(record, record, record).status == "blocked"
