from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.cluster import Cluster


@dataclass(frozen=True)
class ConfigMapTarget:
    cluster: Cluster
    namespace: str
    name: str


@dataclass(frozen=True)
class LiveConfigMapOption:
    name: str
    immutable: bool


@dataclass(frozen=True)
class ConfigMapEntries:
    data: dict[str, str]
    binary_data: dict[str, str]
    payload_size_bytes: int

    @property
    def key_names(self) -> list[str]:
        return sorted([*self.data, *self.binary_data])


@dataclass(frozen=True)
class ConfigMapImpactContext:
    items: list[dict[str, Any]]
    collection_state: str
    reported: bool

    @property
    def count(self) -> int | None:
        return len(self.items) if self.reported else None

    @property
    def display(self) -> str:
        if not self.reported:
            return 'Not Reported'
        count = len(self.items)
        return f'{count} Workload Reference' if count == 1 else f'{count} Workload References'

    @property
    def supporting(self) -> str:
        if self.reported:
            return 'Latest committed Pod snapshot'
        return f'Pod collection: {self.collection_state}'
