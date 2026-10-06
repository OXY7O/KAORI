from __future__ import annotations

from typing import Any

from app.models.object_storage import ObjectStorageSystem

_ALLOWED_PAGE_SIZES = {5, 10, 25, 50}
_ALLOWED_SEVERITIES = {'all', 'critical', 'warning', 'info', 'unknown'}
_ALLOWED_STATES = {'all', 'firing', 'pending', 'suppressed'}


def build_alert_table_view(
    rows: list[dict[str, Any]],
    query_args: Any,
    *,
    system: ObjectStorageSystem,
    selected_source: str,
) -> dict[str, Any]:
    search = str(query_args.get('alert_q') or '').strip()
    severity = _choice(query_args.get('alert_severity'), _ALLOWED_SEVERITIES, default='all')
    state = _choice(query_args.get('alert_state'), _ALLOWED_STATES, default='all')
    filtered = [row for row in rows if _matches(row, search=search, severity=severity, state=state)]

    per_page = _positive_int(query_args.get('alert_per_page'), default=5)
    if per_page not in _ALLOWED_PAGE_SIZES:
        per_page = 5
    total_items = len(filtered)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(_positive_int(query_args.get('alert_page'), default=1), total_pages)
    start_index = (page - 1) * per_page
    page_rows = filtered[start_index : start_index + per_page]

    return {
        'rows': page_rows,
        'search': search,
        'severity': severity,
        'state': state,
        'pagination': {
            'page': page,
            'current_page': page,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': total_pages,
            'start_item': start_index + 1 if total_items else 0,
            'end_item': min(start_index + per_page, total_items) if total_items else 0,
        },
        'query_params': {
            'system_id': str(system.id),
            'source': selected_source,
            'tab': 'records',
            'alert_q': search,
            'alert_severity': severity,
            'alert_state': state,
            'alert_per_page': per_page,
        },
    }


def _matches(row: dict[str, Any], *, search: str, severity: str, state: str) -> bool:
    if severity != 'all' and row.get('severity') != severity:
        return False
    if state != 'all' and row.get('state') != state:
        return False
    if not search:
        return True
    needle = search.casefold()
    haystack = ' '.join(
        str(row.get(key) or '') for key in ('name', 'target', 'summary', 'receiver', 'source')
    ).casefold()
    return needle in haystack


def _choice(value: object, allowed: set[str], *, default: str) -> str:
    normalized = str(value or '').strip().lower()
    return normalized if normalized in allowed else default


def _positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(str(value or '').strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
