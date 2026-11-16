"""Non-mutating, allowlisted ansible-runner facts event projection (#4799).

This module does not establish SSH, trust a worker, or authorize execution.
Only consume events AFTER independent worker/source/target admission.
"""

from collections.abc import Mapping
from typing import Any

_ALLOWED_EVENTS = frozenset({"runner_on_ok", "runner_on_failed", "runner_on_unreachable"})
_ALLOWED_TASKS = frozenset({"gather_facts", "setup"})
_ALLOWED_STATUSES = frozenset({"ok", "failed", "unreachable"})
_MAX_IDENTIFIER = 128


def _identifier(value: Any) -> str | None:
    if not isinstance(value, str) or not (1 <= len(value) <= _MAX_IDENTIFIER):
        return None
    if not value.isascii() or any(not (c.isalnum() or c in "._-") for c in value):
        return None
    return value


def project_remote_facts_event(event: Any, *, expected_host: str) -> dict[str, str] | None:
    """Project only metadata; never persist raw runner payloads or ansible_facts.

    Fail closed on unrecognized event, task, host, status, or malformed shape.
    The caller must separately verify JobExecution, source/EE and host identity.
    """
    if _identifier(expected_host) is None or not isinstance(event, Mapping):
        return None
    if not isinstance(event.get("event"), str) or event["event"] not in _ALLOWED_EVENTS:
        return None
    data = event.get("event_data")
    if not isinstance(data, Mapping):
        return None
    host = _identifier(data.get("host"))
    task = data.get("task_action")
    if host != expected_host or not isinstance(task, str) or task not in _ALLOWED_TASKS:
        return None
    status = {"runner_on_ok": "ok", "runner_on_failed": "failed",
              "runner_on_unreachable": "unreachable"}[event["event"]]
    if status not in _ALLOWED_STATUSES:
        return None
    # No raw event_data, stdout, res, ansible_facts, exception or credentials.
    return {"host": host, "task": task, "status": status}
