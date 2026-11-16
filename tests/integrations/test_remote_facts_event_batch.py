"""Fail-closed regression coverage for bounded remote facts event batches (#4799)."""
from app.integrations.ansible.remote_facts_event_batch import review_remote_facts_event_batch


def event(status="ok", host="node-01", task="setup"):
    kind = {"ok": "runner_on_ok", "failed": "runner_on_failed",
            "unreachable": "runner_on_unreachable"}[status]
    return {"event": kind, "event_data": {"host": host, "task_action": task,
            "res": {"ansible_facts": {"secret": "must-never-project"}}},
            "stdout": "sensitive output"}


def test_single_success_is_only_reviewable_and_redacted():
    result = review_remote_facts_event_batch([event()], expected_host="node-01")
    assert result.state == "requires_independent_admission"
    assert result.execution_authorized is False
    assert result.projected_events == (("node-01", "setup", "ok"),)
    assert "secret" not in repr(result)
    assert "sensitive" not in repr(result)


def test_failures_and_stale_success_cannot_override_later_failure():
    for batch in ([event("failed")], [event("unreachable")],
                  [event(), event("failed")], [event("failed"), event()],
                  [event(), event()], []):
        assert review_remote_facts_event_batch(batch, expected_host="node-01").state == "blocked"


def test_foreign_host_unknown_task_and_malformed_events_are_blocked():
    for batch in ([event(host="other")], [event(task="shell")],
                  [None], [{"event": "runner_on_ok"}],
                  [event(), {"event": "runner_on_ok", "event_data": []}]):
        assert review_remote_facts_event_batch(batch, expected_host="node-01").state == "blocked"


def test_unbounded_and_nonsequence_inputs_fail_closed():
    for batch in (None, {}, "not-an-event", [event()] * 65):
        assert review_remote_facts_event_batch(batch, expected_host="node-01").state == "blocked"
