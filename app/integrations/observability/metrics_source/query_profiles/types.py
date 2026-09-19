from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QueryReadinessTier = Literal['required', 'recommended', 'optional']


@dataclass(frozen=True)
class QueryDefinition:
    key: str
    expression: str
    domain: str
    required_metrics: tuple[str, ...] = ()
    required_labels: tuple[tuple[str, tuple[str, ...]], ...] = ()
    required_history: str | None = None
    deprecated_since: str | None = None
    replacement_key: str | None = None
    notes: str | None = None
    readiness_tier: QueryReadinessTier = 'required'

    @property
    def is_deprecated(self) -> bool:
        return self.deprecated_since is not None
