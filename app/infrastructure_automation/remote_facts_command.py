"""Fixed read-only Ansible Runner invocation boundary for future #4799 worker.

This constructs no SSH connection and grants no execution authority. The worker must
independently resolve trusted inventory, host keys, credentials and signed EE.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

_HOST = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,252}\Z", re.ASCII)


class RemoteFactsCommandDenied(ValueError):
    """Unsafe or ambiguous read-only remote facts invocation."""


@dataclass(frozen=True)
class RemoteFactsCommand:
    module: str
    module_args: str
    limit: str
    forks: int
    timeout: int
    become: bool
    check: bool


def build_remote_facts_command(*, inventory_host: str) -> RemoteFactsCommand:
    """Return a fixed setup-only command; never accept caller-supplied modules.

    This is an inert specification, not a runner dispatch or admission result.
    Host aliases are canonical inventory keys, not arbitrary SSH destinations.
    """
    if type(inventory_host) is not str or not _HOST.fullmatch(inventory_host):
        raise RemoteFactsCommandDenied("Canonical inventory host key is invalid")
    if inventory_host in {".", "..", "localhost", "127.0.0.1"}:
        raise RemoteFactsCommandDenied("Local or ambiguous inventory host is prohibited")
    if inventory_host.startswith("-") or ".." in inventory_host:
        raise RemoteFactsCommandDenied("Unsafe inventory host key")
    return RemoteFactsCommand(
        module="ansible.builtin.setup",
        module_args="gather_subset=!all,!min,network,hardware",
        limit=inventory_host,
        forks=1,
        timeout=30,
        become=False,
        check=True,
    )
