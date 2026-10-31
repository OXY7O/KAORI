"""Canonical operational dashboard tab set shared across KAORI workspaces."""

from __future__ import annotations

from typing import Any

OPERATIONAL_DASHBOARD_TABS: tuple[str, ...] = (
    'overview',
    'capacity',
    'signals',
    'reporting',
)
DEFAULT_OPERATIONAL_DASHBOARD_TAB = OPERATIONAL_DASHBOARD_TABS[0]


def normalize_operational_tab(value: Any) -> str:
    """Normalize an arbitrary tab value to the canonical dashboard tab set."""

    normalized = str(value or DEFAULT_OPERATIONAL_DASHBOARD_TAB).strip().lower()
    return normalized if normalized in OPERATIONAL_DASHBOARD_TABS else DEFAULT_OPERATIONAL_DASHBOARD_TAB
