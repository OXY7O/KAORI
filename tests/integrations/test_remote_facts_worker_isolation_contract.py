"""Regression contracts for the dedicated read-only worker configuration gate."""

from copy import deepcopy

import pytest

from app.integrations.ansible.remote_facts_worker_isolation import (
    qualify_remote_facts_worker,
)


@pytest.fixture
def approved_shape():
    return {
        "queue": "automation-remote-facts",
        "worker_role": "dedicated-remote-facts",
        "execution_mode": "read_only",
        "allowed_operations": ["linux_facts_readonly"],
        "allow_mutation": False,
        "allow_shell": False,
        "allow_privilege_escalation": False,
        "credential_delivery": "protected_worker_reference",
        "source_pinned": True,
        "ee_digest_pinned": True,
        "network_scope": "authorized-hosts-only",
    }


def test_review_only_never_run(approved_shape):
    decision = qualify_remote_facts_worker(config=approved_shape)
    assert decision.status == "requires_independent_admission"
    assert decision.execution_authorized is False


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("queue", "celery"),
        ("worker_role", "general-worker"),
        ("execution_mode", "apply"),
        ("allowed_operations", ["linux_facts_readonly", "shell"]),
        ("allowed_operations", "linux_facts_readonly"),
        ("allowed_operations", []),
        ("allow_mutation", 0),
        ("allow_shell", None),
        ("allow_privilege_escalation", 0),
        ("credential_delivery", "inline_private_key"),
        ("source_pinned", 1),
        ("ee_digest_pinned", "true"),
        ("network_scope", "all-hosts"),
    ],
)
def test_misconfigured_worker_fails_closed(approved_shape, field, invalid):
    candidate = deepcopy(approved_shape)
    candidate[field] = invalid
    decision = qualify_remote_facts_worker(config=candidate)
    assert decision.status == "blocked"
    assert decision.execution_authorized is False


@pytest.mark.parametrize("invalid", [None, {}, [], "worker", 42])
def test_invalid_snapshot_fails_closed(invalid):
    assert qualify_remote_facts_worker(config=invalid).status == "blocked"


def test_unknown_fields_fail_closed(approved_shape):
    approved_shape["run_permission"] = True
    assert qualify_remote_facts_worker(config=approved_shape).status == "blocked"


def test_missing_fields_fail_closed(approved_shape):
    del approved_shape["network_scope"]
    assert qualify_remote_facts_worker(config=approved_shape).status == "blocked"
