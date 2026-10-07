"""Domain-neutral application contract for KAORI Operational Dashboards."""

from __future__ import annotations

from typing import Any, Protocol

from app.common.pagination import DEFAULT_PER_PAGE, PER_PAGE_OPTIONS, normalize_per_page

OPERATIONAL_DASHBOARD_TABS: tuple[str, ...] = (
    'overview',
    'capacity',
    'signals',
    'reporting',
)
DEFAULT_OPERATIONAL_DASHBOARD_TAB = OPERATIONAL_DASHBOARD_TABS[0]
DASHBOARD_PAGE_SIZES = PER_PAGE_OPTIONS
DEFAULT_DASHBOARD_PAGE_SIZE = DEFAULT_PER_PAGE


def normalize_operational_tab(value: Any) -> str:
    """Normalize an arbitrary tab value to the canonical dashboard tab set."""

    normalized = str(value or DEFAULT_OPERATIONAL_DASHBOARD_TAB).strip().lower()
    return normalized if normalized in OPERATIONAL_DASHBOARD_TABS else DEFAULT_OPERATIONAL_DASHBOARD_TAB


def normalize_dashboard_page_size(value: Any) -> int:
    """Use KAORI's canonical pagination choices for dashboard tables."""

    return normalize_per_page(
        value,
        default=DEFAULT_DASHBOARD_PAGE_SIZE,
        allowed=DASHBOARD_PAGE_SIZES,
    )


class _HeaderLookup(Protocol):
    def get(self, key: str, default: Any = None, type: Any = None) -> Any: ...


def is_htmx_request(headers: _HeaderLookup) -> bool:
    """Return whether request headers identify an HTMX request."""

    return str(headers.get('HX-Request') or '').strip().lower() == 'true'
