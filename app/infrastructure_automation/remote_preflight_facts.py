"""Bounded normalization for the reviewed remote setup facts contract (#5186).

No Runner invocation, no credential material and no worker attestation. A
successful facts-only recap is NOT the canonical Kubespray preflight result.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from app.infrastructure_automation.kubernetes.kubespray_preflight import SUPPORTED_OPERATING_SYSTEMS
from app.infrastructure_automation.source import AutomationPilotDenied

_ALIAS = re.compile(r'kaori-[1-9][0-9]{0,18}')
_TEXT = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,127}')
_GIB = 1024 ** 3


@dataclass(frozen=True, slots=True)
class RemoteFactsTarget:
    alias: str
    asset_id: str
    role: str


@dataclass(frozen=True, slots=True)
class RemoteLinuxFacts:
    asset_id: str
    role: str
    os_distribution: str
    os_release: str
    kernel: str
    architecture: str
    package_manager: str
    python_version: str
    cpu_count: int
    memory_mib: int
    root_disk_gib: int
    root_available_gib: int
    effective_user_id: int
    os_supported: bool
    capacity_sufficient: bool


@dataclass(frozen=True, slots=True)
class RemoteFactsReview:
    hosts: tuple[RemoteLinuxFacts, ...]
    changed: bool = False
    execution_authorized: bool = False

    def committed_summary(self) -> dict[str, Any]:
        # Separate result contract; never claim host-key, privilege, network,
        # source/EE or clock-synchronization proof from setup output.
        return {
            'schema_version': 1,
            'facts_contract': 'linux.remote_preflight.facts.v1',
            'hosts': [asdict(host) for host in self.hosts],
            'changed': False,
            'full_preflight_verified': False,
            'execution_authorized': False,
        }


def _deny() -> AutomationPilotDenied:
    return AutomationPilotDenied('Remote facts candidate evidence is incomplete or unqualified')


def _integer(value: object, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _deny()
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or _TEXT.fullmatch(value) is None:
        raise _deny()
    return value


def _qualified_targets(targets: tuple[RemoteFactsTarget, ...]) -> dict[str, RemoteFactsTarget]:
    if type(targets) is not tuple or len(targets) != 3:
        raise _deny()
    if any(
        type(target) is not RemoteFactsTarget
        or not isinstance(target.alias, str)
        or _ALIAS.fullmatch(target.alias) is None
        or not isinstance(target.asset_id, str)
        or re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', target.asset_id) is None
        for target in targets
    ):
        raise _deny()
    expected = {target.alias: target for target in targets}
    roles = [target.role for target in targets]
    if (
        len(expected) != 3
        or len({target.asset_id for target in targets}) != 3
        or roles.count('control_plane') != 1
        or roles.count('worker') != 2
    ):
        raise _deny()
    return expected


def _verify_stats(stats: object, aliases: set[str]) -> None:
    if not isinstance(stats, dict):
        raise _deny()
    ok, changed = stats.get('ok'), stats.get('changed')
    if (
        not isinstance(ok, dict)
        or set(ok) != aliases
        or any(type(count) is not int or count != 1 for count in ok.values())
        or not isinstance(changed, dict)
    ):
        raise _deny()
    for name in ('changed', 'failures', 'dark', 'unreachable', 'skipped', 'rescued', 'ignored'):
        counts = stats.get(name, {})
        if (
            not isinstance(counts, dict)
            or set(counts) - aliases
            or any(type(count) is not int or count != 0 for count in counts.values())
        ):
            raise _deny()


def _normalize(target: RemoteFactsTarget, facts: dict[str, Any]) -> RemoteLinuxFacts:
    distribution = _text(facts.get('ansible_distribution'))
    release = _text(facts.get('ansible_distribution_version'))
    major = _text(facts.get('ansible_distribution_major_version'))
    if distribution == 'OracleLinux':
        release = major
    cpu = _integer(facts.get('ansible_processor_vcpus'), minimum=1, maximum=65536)
    memory = _integer(facts.get('ansible_memtotal_mb'), minimum=1, maximum=2**40)
    mounts = facts.get('ansible_mounts')
    if not isinstance(mounts, list) or len(mounts) > 128:
        raise _deny()
    roots = [item for item in mounts if isinstance(item, dict) and item.get('mount') == '/']
    if len(roots) != 1:
        raise _deny()
    total = _integer(roots[0].get('size_total'), minimum=1, maximum=2**63 - 1)
    available = _integer(roots[0].get('size_available'), minimum=0, maximum=total)
    # Exact current policy supports these two distribution/version pairs only.
    os_supported = (distribution, release) in SUPPORTED_OPERATING_SYSTEMS
    manager = _text(facts.get('ansible_pkg_mgr'))
    os_supported = os_supported and (
        (distribution == 'Ubuntu' and manager == 'apt')
        or (distribution == 'OracleLinux' and manager in ('dnf', 'dnf5', 'yum'))
    )
    return RemoteLinuxFacts(
        asset_id=target.asset_id,
        role=target.role,
        os_distribution=distribution,
        os_release=release,
        kernel=_text(facts.get('ansible_kernel')),
        architecture=_text(facts.get('ansible_architecture')),
        package_manager=manager,
        python_version=_text(facts.get('ansible_python_version')),
        cpu_count=cpu,
        memory_mib=memory,
        root_disk_gib=total // _GIB,
        root_available_gib=available // _GIB,
        effective_user_id=_integer(facts.get('ansible_effective_user_id'), minimum=0, maximum=2**32 - 1),
        os_supported=os_supported,
        capacity_sufficient=cpu >= 2 and memory >= 4096 and total >= 40 * _GIB,
    )


def normalize_remote_facts(
    targets: tuple[RemoteFactsTarget, ...], *, events: list[dict[str, Any]], stats: object
) -> RemoteFactsReview:
    """Require exactly one successful unchanged setup event per expected host.

    The future admitted worker owns canonical target derivation and trusted
    Runner event custody. Do not pass caller-controlled inventory or evidence.
    """
    expected = _qualified_targets(targets)
    _verify_stats(stats, set(expected))
    if not isinstance(events, list) or not 1 <= len(events) <= 256:
        raise _deny()
    observed: dict[str, RemoteLinuxFacts] = {}
    for event in events:
        if not isinstance(event, dict):
            raise _deny()
        kind = event.get('event')
        if kind in ('runner_on_failed', 'runner_on_unreachable', 'runner_on_skipped', 'runner_on_async_failed'):
            raise _deny()
        if kind != 'runner_on_ok':
            continue
        data = event.get('event_data')
        if not isinstance(data, dict):
            raise _deny()
        alias = data.get('host')
        if (
            not isinstance(alias, str)
            or alias not in expected
            or alias in observed
            or data.get('task_action') not in ('ansible.builtin.setup', 'setup')
        ):
            raise _deny()
        result = data.get('res')
        if not isinstance(result, dict) or result.get('changed') is not False:
            raise _deny()
        facts = result.get('ansible_facts')
        if not isinstance(facts, dict):
            raise _deny()
        observed[alias] = _normalize(expected[alias], facts)
    if set(observed) != set(expected):
        raise _deny()
    return RemoteFactsReview(tuple(observed[alias] for alias in sorted(observed)))
