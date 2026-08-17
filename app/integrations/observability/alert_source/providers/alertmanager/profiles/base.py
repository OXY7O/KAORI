from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AlertmanagerProfile:
    key: str
    version_constraint: str
    support_level: str
    required_capabilities: tuple[str, ...]
    known_limitations: tuple[str, ...] = ()
