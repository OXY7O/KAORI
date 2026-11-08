"""Domain-neutral application contract for KAORI Operational Dashboards."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from werkzeug.datastructures import Headers

from app.common.operational_tabs import (
    DEFAULT_OPERATIONAL_DASHBOARD_TAB as DEFAULT_OPERATIONAL_DASHBOARD_TAB,
)
from app.common.operational_tabs import (
    OPERATIONAL_DASHBOARD_TABS as OPERATIONAL_DASHBOARD_TABS,
)
from app.common.operational_tabs import (
    normalize_operational_tab as normalize_operational_tab,
)
from app.common.pagination import DEFAULT_PER_PAGE, PER_PAGE_OPTIONS, normalize_per_page

DASHBOARD_PAGE_SIZES = PER_PAGE_OPTIONS
DEFAULT_DASHBOARD_PAGE_SIZE = DEFAULT_PER_PAGE


def normalize_dashboard_page_size(value: Any) -> int:
    """Use KAORI's canonical pagination choices for dashboard tables."""

    return normalize_per_page(
        value,
        default=DEFAULT_DASHBOARD_PAGE_SIZE,
        allowed=DASHBOARD_PAGE_SIZES,
    )


def is_htmx_request(headers: Headers | Mapping[str, Any]) -> bool:
    """Return whether request headers identify an HTMX request."""

    return str(headers.get('HX-Request') or '').strip().lower() == 'true'
