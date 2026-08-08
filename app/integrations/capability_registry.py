"""Shared server-side capability registry filtering and pagination."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.common.pagination import PER_PAGE_OPTIONS, paginate_sequence


def _value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def build_capability_registry_view(
    rows: Sequence[Any],
    *,
    query: str = '',
    requirement: str = 'all',
    status: str = 'all',
    page: Any = 1,
    per_page: Any = 5,
    search_fields: tuple[str, ...] = ('label', 'category'),
    distinguish_optional_gap: bool = False,
) -> dict[str, Any]:
    """Return one normalized KAORI capability-registry view.

    The registry interaction model intentionally mirrors Recent Runtime
    Observations: filters and pagination are server-backed, HTMX swaps one
    registry partial, and the shared loading indicator reflects real work.
    """

    normalized_query = str(query or '').strip()
    normalized_requirement = str(requirement or 'all').strip().lower()
    if normalized_requirement not in {'all', 'required', 'optional'}:
        normalized_requirement = 'all'

    allowed_statuses = {'all', 'ready', 'blocked'}
    if distinguish_optional_gap:
        allowed_statuses.add('optional_gap')
    normalized_status = str(status or 'all').strip().lower()
    if normalized_status not in allowed_statuses:
        normalized_status = 'all'

    lowered_query = normalized_query.lower()
    filtered: list[Any] = []
    for row in rows:
        required = bool(_value(row, 'required', False))
        available = bool(_value(row, 'available', False))
        requirement_key = 'required' if required else 'optional'
        if available:
            status_key = 'ready'
        elif distinguish_optional_gap and not required:
            status_key = 'optional_gap'
        else:
            status_key = 'blocked'

        if lowered_query:
            searchable = ' '.join(str(_value(row, field, '') or '') for field in search_fields).lower()
            if lowered_query not in searchable:
                continue
        if normalized_requirement != 'all' and requirement_key != normalized_requirement:
            continue
        if normalized_status != 'all' and status_key != normalized_status:
            continue
        filtered.append(row)

    page_rows, pagination = paginate_sequence(
        filtered,
        page=page,
        per_page=per_page,
        allowed_per_page=PER_PAGE_OPTIONS,
    )
    return {
        'rows': page_rows,
        'pagination': pagination,
        'filters': {
            'query': normalized_query,
            'requirement': normalized_requirement,
            'status': normalized_status,
        },
    }
