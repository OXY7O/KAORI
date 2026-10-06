from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SecretOperationResult:
    status: str
    title: str
    message: str
    detail: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SecretImpactContext:
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
