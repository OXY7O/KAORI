"""Fail-closed read-only remote-facts JobExecution envelope (#4799).

This pure contract validates the *binding* of a completed worker attempt to a
canonical job. It does not establish authority, dispatch a worker, or run SSH.
Canonical JobExecution and independently resolved authorities remain mandatory.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

_SHA = re.compile(r"[0-9a-f]{40}\\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\\Z")
_KEYS = frozenset({
    "job_id", "attempt_id", "integration_id", "asset_id", "source_sha",
    "ee_digest", "queue", "operation", "started_at", "finished_at",
    "state", "return_code", "changed", "event_count",
})


@dataclass(frozen=True, slots=True)
class FactsJobEnvelopeDecision:
    status: str
    reason: str
    execution_authorized: bool = False


def qualify_facts_job_envelope(
    *,
    evidence: object,
    job_id: str,
    attempt_id: str,
    integration_id: str,
    asset_id: str,
    source_sha: str,
    ee_digest: str,
    now: datetime,
) -> FactsJobEnvelopeDecision:
    """Qualify an exact completed attempt for independent facts review only.

    All expected values must come from canonical persisted JobExecution and
    independent source/asset authorities, never browser or runner assertions.
    """
    denied = FactsJobEnvelopeDecision("blocked", "UNQUALIFIED_REMOTE_FACTS_ATTEMPT")
    expected = (job_id, attempt_id, integration_id, asset_id)
    if (
        not isinstance(evidence, Mapping)
        or set(evidence) != _KEYS
        or any(not isinstance(v, str) or not _ID.fullmatch(v) for v in expected)
        or not isinstance(source_sha, str)
        or not _SHA.fullmatch(source_sha)
        or not isinstance(ee_digest, str)
        or not _DIGEST.fullmatch(ee_digest)
        or not isinstance(now, datetime)
        or now.tzinfo is None
    ):
        return denied
    for key, value in (
        ("job_id", job_id), ("attempt_id", attempt_id),
        ("integration_id", integration_id), ("asset_id", asset_id),
        ("source_sha", source_sha), ("ee_digest", ee_digest),
    ):
        if type(evidence[key]) is not str or evidence[key] != value:
            return denied
    if (
        evidence["queue"] != "automation"
        or evidence["operation"] != "ansible.host_facts.read_only"
        or evidence["state"] != "succeeded"
        or type(evidence["return_code"]) is not int
        or evidence["return_code"] != 0
        or evidence["changed"] is not False
        or type(evidence["event_count"]) is not int
        or not 1 <= evidence["event_count"] <= 10000
    ):
        return denied
    start, finish = evidence["started_at"], evidence["finished_at"]
    if (
        not isinstance(start, datetime)
        or not isinstance(finish, datetime)
        or start.tzinfo is None
        or finish.tzinfo is None
    ):
        return denied
    start, finish, current = start.astimezone(UTC), finish.astimezone(UTC), now.astimezone(UTC)
    if not (start <= finish <= current and finish - start <= timedelta(minutes=10)):
        return denied
    if current - finish > timedelta(minutes=15):
        return denied
    return FactsJobEnvelopeDecision("requires_independent_admission", "EXACT_READ_ONLY_ATTEMPT")
