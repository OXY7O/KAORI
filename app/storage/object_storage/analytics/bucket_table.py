from __future__ import annotations

from typing import Any

from app.models.object_storage import ObjectStorageSystem


def _page_endpoint(page_key: str) -> str:
    return {
        'capacity': 'analytics.object_storage_capacity',
        'performance': 'analytics.object_storage_performance',
        'top_consumers': 'analytics.object_storage_top_consumers',
    }.get(page_key, 'analytics.object_storage_top_consumers')


def _workspace_tab(page_key: str) -> str | None:
    return {
        'capacity': 'quota',
        'performance': 'buckets',
        'top_consumers': 'records',
    }.get(page_key)


def _positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(str(value or '').strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def build_bucket_table_view(
    rows: list[dict[str, Any]],
    query_args: Any,
    *,
    page_key: str,
    system: ObjectStorageSystem,
    time_range: str,
) -> dict[str, Any]:
    search = str(query_args.get('bucket_q') or '').strip()
    if search:
        needle = search.casefold()
        filtered = [row for row in rows if needle in str(row.get('name') or '').casefold()]
    else:
        filtered = list(rows)

    per_page = _positive_int(query_args.get('bucket_per_page'), default=5)
    if per_page not in {5, 10, 25, 50}:
        per_page = 5
    total_items = len(filtered)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(_positive_int(query_args.get('bucket_page'), default=1), total_pages)
    start_index = (page - 1) * per_page
    page_rows = filtered[start_index : start_index + per_page]
    start_item = start_index + 1 if total_items else 0
    end_item = min(start_index + per_page, total_items) if total_items else 0
    query_params: dict[str, object] = {
        'system_id': str(system.id),
        'time_range': time_range,
        'page_key': page_key,
        'bucket_q': search,
        'bucket_per_page': per_page,
    }
    workspace_tab = _workspace_tab(page_key)
    if workspace_tab is not None:
        query_params['tab'] = workspace_tab

    return {
        'rows': page_rows,
        'search': search,
        'pagination': {
            'page': page,
            'current_page': page,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': total_pages,
            'start_item': start_item,
            'end_item': end_item,
        },
        'query_params': query_params,
        'page_endpoint': _page_endpoint(page_key),
    }


def build_bucket_forecast_table_view(
    rows: list[dict[str, Any]],
    query_args: Any,
    *,
    system: ObjectStorageSystem,
    history_window: str,
) -> dict[str, Any]:
    search = str(query_args.get('forecast_q') or '').strip()
    watch = str(query_args.get('forecast_watch') or 'all').strip().lower()
    history_state = str(query_args.get('forecast_history_state') or 'all').strip().lower()

    allowed_watch = {'all', 'critical', 'warning', 'info', 'normal', 'unknown'}
    if watch not in allowed_watch:
        watch = 'all'
    allowed_history_states = {'all', 'ready', 'partial', 'no_data'}
    if history_state not in allowed_history_states:
        history_state = 'all'

    filtered = list(rows)
    if search:
        needle = search.casefold()
        filtered = [row for row in filtered if needle in str(row.get('name') or '').casefold()]
    if watch != 'all':
        filtered = [row for row in filtered if str(row.get('watch_tone') or 'unknown').lower() == watch]
    if history_state != 'all':
        filtered = [row for row in filtered if str(row.get('history_state') or 'no_data').lower() == history_state]

    per_page = _positive_int(query_args.get('forecast_bucket_per_page'), default=5)
    if per_page not in {5, 10, 25, 50}:
        per_page = 5
    total_items = len(filtered)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(_positive_int(query_args.get('forecast_bucket_page'), default=1), total_pages)
    start_index = (page - 1) * per_page
    page_rows = filtered[start_index : start_index + per_page]
    start_item = start_index + 1 if total_items else 0
    end_item = min(start_index + per_page, total_items) if total_items else 0

    query_params: dict[str, object] = {
        'system_id': str(system.id),
        'history_window': history_window,
        'tab': 'buckets',
        'forecast_q': search,
        'forecast_watch': watch,
        'forecast_history_state': history_state,
        'forecast_bucket_per_page': per_page,
    }

    return {
        'rows': page_rows,
        'search': search,
        'watch': watch,
        'history_state': history_state,
        'pagination': {
            'page': page,
            'current_page': page,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': total_pages,
            'start_item': start_item,
            'end_item': end_item,
        },
        'query_params': query_params,
        'page_endpoint': 'analytics.object_storage_forecast',
    }
