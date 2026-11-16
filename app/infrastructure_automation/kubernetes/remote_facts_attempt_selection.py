"""Read-only remote facts attempt selection guard for canonical JobExecution (#4799).

Prevents a stale successful facts attempt from outranking a newer failed or
in-flight attempt. This pure selector never dispatches work or grants Run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FactsAttemptSelection:
    status: str
    reason: str
    selected_attempt_id: str | None = None
    execution_authorized: bool = False


def select_current_facts_attempt(
    *,
    job_id: str,
    expected_attempt_id: str,
    attempts: object,
) -> FactsAttemptSelection:
    """Require an exact, unique, latest completed successful attempt.

    The caller MUST obtain attempts and expected_attempt_id from the canonical
    persisted JobExecution store, never a browser, worker payload or cached
    successful attempt. Sequence order is NOT trusted: attempt_number wins.
    """
    denied = FactsAttemptSelection("blocked", "REMOTE_FACTS_ATTEMPT_NOT_CURRENT")
    if (
        type(job_id) is not str
        or not job_id
        or len(job_id) > 96
        or type(expected_attempt_id) is not str
        or not expected_attempt_id
        or len(expected_attempt_id) > 96
        or not isinstance(attempts, Sequence)
        or isinstance(attempts, (str, bytes, bytearray))
        or not 1 <= len(attempts) <= 100
    ):
        return denied
    seen_ids: set[str] = set()
    seen_numbers: set[int] = set()
    records = []
    required = {"job_id", "attempt_id", "attempt_number", "state"}
    for record in attempts:
        if not isinstance(record, Mapping) or set(record) != required:
            return denied
        attempt_id = record["attempt_id"]
        number = record["attempt_number"]
        if (
            type(record["job_id"]) is not str
            or record["job_id"] != job_id
            or type(attempt_id) is not str
            or not attempt_id
            or len(attempt_id) > 96
            or type(number) is not int
            or not 1 <= number <= 1000000
            or type(record["state"]) is not str
            or record["state"] not in {"queued", "running", "succeeded", "failed", "cancelled", "unknown"}
            or attempt_id in seen_ids
            or number in seen_numbers
        ):
            return denied
        seen_ids.add(attempt_id)
        seen_numbers.add(number)
        records.append(record)
    latest = max(records, key=lambda record: record["attempt_number"])
    if latest["attempt_id"] != expected_attempt_id or latest["state"] != "succeeded":
        return denied
    return FactsAttemptSelection(
        "requires_independent_admission",
        "CURRENT_READ_ONLY_FACTS_ATTEMPT",
        expected_attempt_id,
    )
