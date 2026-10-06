from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from app.artifact_registry.collectors import InventoryProgressCallback
from app.artifact_registry.security.contracts import RegistrySecurityEvidence, RegistrySecurityTarget
SecurityTargetCurrentPredicate = Callable[[RegistrySecurityTarget], bool]

SecurityCollectorCallable = Callable[
    [
        Any,
        list[RegistrySecurityTarget],
        InventoryProgressCallback | None,
        SecurityTargetCurrentPredicate | None,
    ],
    RegistrySecurityEvidence,
]


@dataclass(frozen=True, slots=True)
class RegistrySecurityCollector:
    provider_key: str
    collect: SecurityCollectorCallable
    capabilities: frozenset[str] = field(default_factory=frozenset)


_COLLECTORS: dict[str, RegistrySecurityCollector] = {}
_LOCK = RLock()


def register_registry_security_collector(
    collector: RegistrySecurityCollector,
    *,
    replace: bool = False,
) -> None:
    provider_key = str(collector.provider_key or '').strip().lower()
    if not provider_key:
        raise ValueError('Registry security collector requires a provider_key.')
    with _LOCK:
        if provider_key in _COLLECTORS and not replace:
            raise ValueError(f'Registry security collector {provider_key!r} is already registered.')
        _COLLECTORS[provider_key] = collector


def get_registry_security_collector(provider_key: str) -> RegistrySecurityCollector:
    from app.integrations.kernel.registry import get_integration

    get_integration('registry')
    normalized = str(provider_key or '').strip().lower()
    collector = _COLLECTORS.get(normalized)
    if collector is None:
        raise LookupError(
            f'No qualified Artifact Registry security collector is registered for provider {normalized!r}.'
        )
    return collector


def registered_registry_security_collectors() -> tuple[RegistrySecurityCollector, ...]:
    from app.integrations.kernel.registry import get_integration

    get_integration('registry')
    return tuple(_COLLECTORS[key] for key in sorted(_COLLECTORS))
