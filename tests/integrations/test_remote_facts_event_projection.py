"""Regression contracts for read-only Ansible event projection (#4799)."""

from app.integrations.ansible.remote_facts_event_projection import project_remote_facts_event


def _event(name="runner_on_ok", host="node-1", task="setup"):
    return {"event": name, "event_data": {
        "host": host, "task_action": task,
        "res": {"ansible_facts": {"ansible_env": {"TOKEN": "secret"}}},
        "stdout": "PASSWORD=secret", "credential": "secret"}}


def test_allowlist_drops_secret_bearing_runner_fields():
    result = project_remote_facts_event(_event(), expected_host="node-1")
    assert result == {"host": "node-1", "task": "setup", "status": "ok"}
    assert "secret" not in str(result)


def test_fail_closed_on_untrusted_event_or_target():
    for event in (
        _event(name="runner_on_skipped"),
        _event(host="node-2"),
        _event(task="shell"),
        _event(task="command"),
        {"event": "runner_on_ok", "event_data": ["invalid"]},
        {"event": "runner_on_ok"},
        "malformed",
    ):
        assert project_remote_facts_event(event, expected_host="node-1") is None


def test_failure_is_not_projected_as_success():
    for name, status in (("runner_on_failed", "failed"),
                         ("runner_on_unreachable", "unreachable")):
        assert project_remote_facts_event(_event(name=name), expected_host="node-1") == {
            "host": "node-1", "task": "setup", "status": status}


def test_noncanonical_host_identity_denied():
    assert project_remote_facts_event(_event(), expected_host="node 1") is None
    assert project_remote_facts_event(_event(host="node\\n1"), expected_host="node\\n1") is None
