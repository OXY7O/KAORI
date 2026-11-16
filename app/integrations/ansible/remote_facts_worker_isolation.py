"""Fail-closed dedicated remote-facts worker isolation contract (#4799).

This is a pure configuration admission check, NOT a worker dispatcher or an
authorization to resolve credentials, open SSH, or execute Ansible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

_EXPECTED_KEYS = frozenset({
    "queue", "worker_role", "execution_mode", "allowed_operations",
    "allow_mutation", "allow_shell", "allow_privilege_escalation",
    "credential_delivery", "source_pinned", "ee_digest_pinned",
    "network_scope",
})
_ALLOWED_OPERATION = "linux_facts_readonly"
_QUEUE = "automation-remote-facts"
_ROLE = "dedicated-remote-facts"
_NETWORK = "authorized-hosts-only"


@dataclass(frozen=True, slots=True)
class WorkerIsolationDecision:
    status: str
    reason: str
    execution_authorized: bool = False


def qualify_remote_facts_worker(*, config: object) -> WorkerIsolationDecision:
    """Check a trusted deployment configuration snapshot, not worker claims.

    A passing result is only eligible for independent deployment admission.
    A separate authority must attest the deployed worker and its credentials.
    """
    denied = WorkerIsolationDecision("blocked", "REMOTE_FACTS_WORKER_ISOLATION_UNPROVEN")
    if not isinstance(config, Mapping) or set(config) != _EXPECTED_KEYS:
        return denied
    if (
        type(config["queue"]) is not str
        or config["queue"] != _QUEUE
        or type(config["worker_role"]) is not str
        or config["worker_role"] != _ROLE
        or config["execution_mode"] != "read_only"
        or type(config["allowed_operations"]) not in (tuple, list)
        or len(config["allowed_operations"]) != 1
        or config["allowed_operations"][0] != _ALLOWED_OPERATION
        or config["allow_mutation"] is not False
        or config["allow_shell"] is not False
        or config["allow_privilege_escalation"] is not False
        or config["credential_delivery"] != "protected_worker_reference"
        or config["source_pinned"] is not True
        or config["ee_digest_pinned"] is not True
        or config["network_scope"] != _NETWORK
    ):
        return denied
    return WorkerIsolationDecision(
        "requires_independent_admission", "WORKER_CONFIGURATION_ONLY"
    )
