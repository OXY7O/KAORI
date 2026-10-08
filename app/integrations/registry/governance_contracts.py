from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from app.integrations.kernel.registry import get_integration
from app.integrations.registry.collectors import InventoryProgressCallback


@dataclass(slots=True)
class ProjectGovernanceRecord:
    project_name: str
    retention_status: str = 'not_collected'
    retention_policy_ref: str | None = None
    retention_summary: dict[str, Any] = field(default_factory=dict)
    immutability_status: str = 'not_collected'
    immutability_rule_count: int | None = None
    immutability_summary: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReplicationPolicyRecord:
    provider_native_id: str
    name: str
    enabled: bool | None = None
    trigger_type: str | None = None
    source_registry: str | None = None
    destination_registry: str | None = None
    destination_namespace: str | None = None
    filters: list[Any] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RegistryGovernanceEvidence:
    projects: list[ProjectGovernanceRecord] = field(default_factory=list)
    replication_policies: list[ReplicationPolicyRecord] = field(default_factory=list)
    capability_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegistryGovernanceCollector:
    provider_key: str
    collect: Callable[[Any], RegistryGovernanceEvidence]
    collect_with_progress: (
        Callable[
            [Any, InventoryProgressCallback | None],
            RegistryGovernanceEvidence,
        ]
        | None
    ) = None


_COLLECTORS: dict[str, RegistryGovernanceCollector] = {}
_LOCK = RLock()


def register_registry_governance_collector(
    collector: RegistryGovernanceCollector,
    *,
    replace: bool = False,
) -> None:
    key = str(collector.provider_key or '').strip().lower()
    if not key:
        raise ValueError('Registry governance collector requires a provider_key.')
    with _LOCK:
        if key in _COLLECTORS and not replace:
            raise ValueError(f'Registry governance collector {key!r} is already registered.')
        _COLLECTORS[key] = collector


def get_registry_governance_collector(provider_key: str) -> RegistryGovernanceCollector:
    get_integration('registry')
    key = str(provider_key or '').strip().lower()
    collector = _COLLECTORS.get(key)
    if collector is None:
        raise LookupError(f'No qualified Registry governance collector is registered for provider {key!r}.')
    return collector


def registered_registry_governance_collectors() -> tuple[RegistryGovernanceCollector, ...]:
    get_integration('registry')
    return tuple(_COLLECTORS[key] for key in sorted(_COLLECTORS))
