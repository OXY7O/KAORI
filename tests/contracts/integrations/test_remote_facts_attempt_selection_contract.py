"""Regression tests for remote facts latest-attempt replay protection (#4799)."""

from app.infrastructure_automation.kubernetes.remote_facts_attempt_selection import (
    select_current_facts_attempt,
)


def attempt(number, state="succeeded", job="job-1", identity=None):
    return {
        "job_id": job,
        "attempt_id": identity or f"attempt-{number}",
        "attempt_number": number,
        "state": state,
    }


def select(records, expected="attempt-2"):
    return select_current_facts_attempt(
        job_id="job-1", expected_attempt_id=expected, attempts=records
    )


def test_current_success_is_review_only_even_when_unordered():
    result = select([attempt(2), attempt(1)])
    assert result.status == "requires_independent_admission"
    assert result.selected_attempt_id == "attempt-2"
    assert result.execution_authorized is False


def test_older_success_cannot_override_newer_failure_or_inflight():
    for state in ("failed", "queued", "running", "cancelled", "unknown"):
        assert select([attempt(1), attempt(2, state)], "attempt-1").status == "blocked"
        assert select([attempt(1), attempt(2, state)]).status == "blocked"


def test_new_success_cannot_be_replaced_with_older_success():
    assert select([attempt(1), attempt(2)], "attempt-1").status == "blocked"


def test_duplicate_numbers_or_ids_fail_closed():
    assert select([attempt(1), attempt(1)], "attempt-1").status == "blocked"
    assert select([attempt(1, identity="same"), attempt(2, identity="same")]).status == "blocked"


def test_foreign_job_or_malformed_attempt_fails_closed():
    assert select([attempt(1), attempt(2, job="other")]).status == "blocked"
    for value in (True, "2", 0, -1, 1.5):
        assert select([attempt(1), {**attempt(2), "attempt_number": value}]).status == "blocked"
    assert select([attempt(1), {**attempt(2), "extra": "secret"}]).status == "blocked"
    assert select([attempt(1), {**attempt(2), "state": "ready"}]).status == "blocked"


def test_empty_oversized_and_string_attempts_are_denied():
    assert select([]).status == "blocked"
    assert select("not an attempt list").status == "blocked"
    assert select([attempt(i) for i in range(1, 102)]).status == "blocked"
