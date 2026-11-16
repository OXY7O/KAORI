"""Cross-record remote-facts evidence coherence, without execution admission (#4799).

Compare independently supplied canonical record snapshots. This pure function does
not establish issuer trust, access secrets, dispatch workers, or authorize Run.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

_SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}", re.ASCII)
_KEYS = frozenset({
    "job_execution_id", "attempt", "integration_binding_id", "asset_id",
    "source_sha", "ee_digest", "inventory_fingerprint",
})


@dataclass(frozen=True, slots=True)
class EvidenceCoherence:
    status: str
    reason: str
    execution_authorized: bool = False


def compare_remote_facts_evidence(*, job: object, host: object, authority: object) -> EvidenceCoherence:
    """Fail closed on identity drift between three separately retrieved records.

    The caller must independently authenticate each record's issuer and verify
    latest-attempt, freshness, host-key trust, credential authority and worker.
    Equality is necessary but never sufficient for execution.
    """
    blocked = EvidenceCoherence("blocked", "REMOTE_FACTS_EVIDENCE_DRIFT_OR_UNPROVEN")
    records = (job, host, authority)
    if any(not isinstance(record, Mapping) or set(record) != _KEYS for record in records):
        return blocked
    for key in _KEYS:
        values = [record[key] for record in records]
        if key == "attempt":
            if any(type(value) is not int or value < 1 for value in values):
                return blocked
        elif any(type(value) is not str or not value or len(value) > 256 for value in values):
            return blocked
        if any(value != values[0] for value in values[1:]):
            return blocked
    if not _SHA.fullmatch(job["source_sha"]) or not _DIGEST.fullmatch(job["ee_digest"]):
        return blocked
    if not _DIGEST.fullmatch(job["inventory_fingerprint"]):
        return blocked
    return EvidenceCoherence("requires_independent_admission", "EXACT_RECORD_IDENTITY_ONLY")
