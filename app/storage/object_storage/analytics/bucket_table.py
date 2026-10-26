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
    quota_state = str(query_args.get('bucket_quota_state') or 'all').strip().lower()
    quota_pressure = str(query_args.get('bucket_quota_pressure') or 'all').strip().lower()
    usage_context = str(query_args.get('bucket_usage_context') or 'all').strip().lower()
    request_evidence = str(query_args.get('bucket_request_evidence') or 'all').strip().lower()
    if page_key not in {'performance', 'top_consumers'} or usage_context not in {
        'all',
        'metrics',
        'inventory',
        'unavailable',
    }:
        usage_context = 'all'
    allowed_quota_states = {'all', 'configured', 'not_configured', 'unknown'}
    if page_key not in {'capacity', 'top_consumers'} or quota_state not in allowed_quota_states:
        quota_state = 'all'
    if page_key not in {'capacity', 'top_consumers'} or quota_pressure not in {'all', 'within', 'warning', 'critical'}:
        quota_pressure = 'all'
    if page_key != 'top_consumers' or request_evidence not in {'all', 'available', 'unavailable'}:
        request_evidence = 'all'

    filtered = list(rows)
    if search:
        needle = search.casefold()
        filtered = [row for row in filtered if needle in str(row.get('name') or '').casefold()]
    if usage_context != 'all':
        filtered = [
            row
            for row in filtered
            if (
                (usage_context == 'unavailable' and row.get('usage_bytes') is None)
                or (
                    usage_context == 'inventory'
                    and row.get('usage_bytes') is not None
                    and row.get('usage_source') == 'Committed Snapshot'
                )
                or (
                    usage_context == 'metrics'
                    and row.get('usage_bytes') is not None
                    and row.get('usage_source') != 'Committed Snapshot'
                )
            )
        ]

    if request_evidence != 'all':
        filtered = [
            row for row in filtered if (row.get('request_rate') is not None) == (request_evidence == 'available')
        ]

    if quota_state == 'configured':
        filtered = [row for row in filtered if row.get('quota_bytes') is not None]
    elif quota_state == 'not_configured':
        filtered = [row for row in filtered if row.get('quota_state') == 'not_configured']
    elif quota_state == 'unknown':
        filtered = [
            row for row in filtered if row.get('quota_bytes') is None and row.get('quota_state') != 'not_configured'
        ]

    if quota_pressure != 'all':
        filtered = [
            row
            for row in filtered
            if row.get('quota_bytes') is not None
            and row.get('quota_utilization') is not None
            and (
                (quota_pressure == 'within' and row['quota_utilization'] < 85)
                or (quota_pressure == 'warning' and 85 <= row['quota_utilization'] < 95)
                or (quota_pressure == 'critical' and row['quota_utilization'] >= 95)
            )
        ]

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
    if page_key in {'performance', 'top_consumers'}:
        query_params['bucket_usage_context'] = usage_context
    if page_key in {'capacity', 'top_consumers'}:
        query_params['bucket_quota_state'] = quota_state
        query_params['bucket_quota_pressure'] = quota_pressure
    if page_key == 'top_consumers':
        query_params['bucket_request_evidence'] = request_evidence
    workspace_tab = _workspace_tab(page_key)
    if workspace_tab is not None:
        query_params['tab'] = workspace_tab

    return {
        'rows': page_rows,
        'search': search,
        'quota_state': quota_state,
        'quota_pressure': quota_pressure,
        'usage_context': usage_context,
        'request_evidence': request_evidence,
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
