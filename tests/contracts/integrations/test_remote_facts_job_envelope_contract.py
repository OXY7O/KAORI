"""Negative/positive exact-attempt remote facts envelope contracts (#4799)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.infrastructure_automation.kubernetes.remote_facts_job_envelope import (
    qualify_facts_job_envelope,
)

NOW = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
SHA = "a" * 40
EE = "sha256:" + "b" * 64
EXPECTED = dict(
    job_id="job-17", attempt_id="attempt-2", integration_id="integration-4",
    asset_id="asset-9", source_sha=SHA, ee_digest=EE, now=NOW,
)


def valid_evidence():
    return {
        "job_id": "job-17", "attempt_id": "attempt-2",
        "integration_id": "integration-4", "asset_id": "asset-9",
        "source_sha": SHA, "ee_digest": EE,
        "queue": "automation", "operation": "ansible.host_facts.read_only",
        "started_at": NOW - timedelta(minutes=2),
        "finished_at": NOW - timedelta(minutes=1),
        "state": "succeeded", "return_code": 0, "changed": False,
        "event_count": 3,
    }


def test_exact_read_only_attempt_requires_independent_admission():
    decision = qualify_facts_job_envelope(evidence=valid_evidence(), **EXPECTED)
    assert decision.status == "requires_independent_admission"
    assert decision.execution_authorized is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_id", "job-18"), ("attempt_id", "attempt-1"),
        ("integration_id", "integration-5"), ("asset_id", "asset-10"),
        ("source_sha", "c" * 40), ("ee_digest", "sha256:" + "d" * 64),
        ("queue", "default"), ("operation", "ansible.playbook.run"),
        ("state", "running"), ("return_code", True), ("return_code", 1),
        ("changed", True), ("changed", 0), ("event_count", 0),
        ("event_count", True), ("event_count", 10001),
        ("started_at", NOW + timedelta(seconds=1)),
        ("finished_at", NOW + timedelta(seconds=1)),
        ("finished_at", NOW - timedelta(minutes=16)),
        ("started_at", NOW - timedelta(hours=1)),
        ("started_at", NOW.replace(tzinfo=None)),
    ],
)
def test_mismatched_or_unsafe_attempt_is_blocked(field, value):
    evidence = valid_evidence()
    evidence[field] = value
    decision = qualify_facts_job_envelope(evidence=evidence, **EXPECTED)
    assert decision.status == "blocked"
    assert not decision.execution_authorized


def test_secret_bearing_or_unexpected_fields_are_denied():
    evidence = valid_evidence()
    evidence["stdout"] = "secret"
    assert qualify_facts_job_envelope(evidence=evidence, **EXPECTED).status == "blocked"


def test_expected_authority_identifiers_must_be_canonical():
    for override in ({"job_id": " job-17"}, {"source_sha": "not-a-sha"}, {"now": NOW.replace(tzinfo=None)}):
        assert qualify_facts_job_envelope(
            evidence=valid_evidence(), **(EXPECTED | override)
        ).status == "blocked"
