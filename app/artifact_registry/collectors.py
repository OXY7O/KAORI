from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any

from app.artifact_registry.contracts import RegistryInventoryEvidence


InventoryProgressCallback = Callable[[int, int, str], None]
CollectorCallable = Callable[[Any], RegistryInventoryEvidence]
ProgressCollectorCallable = Callable[[Any, InventoryProgressCallback | None], RegistryInventoryEvidence]


@dataclass(frozen=True, slots=True)
class RegistryInventoryCollector:
    """Qualified provider collector that normalizes into the shared Registry contract."""

    provider_key: str
    collect: CollectorCallable
    collect_with_progress: ProgressCollectorCallable | None = None


_COLLECTORS: dict[str, RegistryInventoryCollector] = {}
_LOCK = RLock()


def register_registry_collector(
    collector: RegistryInventoryCollector,
    *,
    replace: bool = False,
) -> None:
    provider_key = str(collector.provider_key or '').strip().lower()
    if not provider_key:
        raise ValueError('Registry inventory collector requires a provider_key.')
    with _LOCK:
        if provider_key in _COLLECTORS and not replace:
            raise ValueError(f'Registry inventory collector {provider_key!r} is already registered.')
        _COLLECTORS[provider_key] = collector


def get_registry_collector(provider_key: str) -> RegistryInventoryCollector:
    normalized = str(provider_key or '').strip().lower()
    if not normalized:
        raise LookupError('Registry provider key is required for inventory collection.')

    # Loading the Registry integration imports production provider registrations.
    from app.integrations.kernel.registry import get_integration

    get_integration('registry')
    collector = _COLLECTORS.get(normalized)
    if collector is None:
        raise LookupError(
            f'No qualified Artifact Registry inventory collector is registered for provider {normalized!r}.'
        )
    return collector


def registered_registry_collectors() -> tuple[RegistryInventoryCollector, ...]:
    return tuple(_COLLECTORS[key] for key in sorted(_COLLECTORS))
