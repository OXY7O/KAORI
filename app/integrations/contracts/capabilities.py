from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    key: str
    label: str
    description: str
    required: bool = False


@dataclass(frozen=True, slots=True)
class CompatibilityProfileDefinition:
    key: str
    label: str
    supported_constraint: str
    description: str = ''


def normalize_capability_keys(values: Iterable[str] | None) -> tuple[str, ...]:
    """Return deterministic canonical capability keys."""
    return tuple(sorted({str(value).strip().lower() for value in values or () if str(value).strip()}))
