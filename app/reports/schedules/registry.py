from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.reports.scope import KUBERNETES_CLUSTER_ASSET_TYPE


def get_selected_filters(query_args: Mapping[str, str]) -> dict[str, str]:
    asset = str(query_args.get('asset', '') or '').strip()
    legacy_cluster = str(query_args.get('cluster', '') or '').strip()
    if not asset and legacy_cluster:
        asset = f'{KUBERNETES_CLUSTER_ASSET_TYPE}:{legacy_cluster}'
    return {
        'search': str(query_args.get('search', '') or '').strip(),
        'status': str(query_args.get('status', '') or '').strip().lower(),
        'cadence': str(query_args.get('cadence', '') or '').strip().lower(),
        'report_type': str(query_args.get('report_type', '') or '').strip(),
        'asset': asset,
        'delivery': str(query_args.get('delivery', '') or '').strip().lower(),
    }


def filter_schedule_rows(
    schedules: list[dict[str, Any]],
    selected_filters: dict[str, str],
) -> list[dict[str, Any]]:
    search = selected_filters['search'].casefold()
    status = selected_filters['status']
    cadence = selected_filters['cadence']
    report_type = selected_filters['report_type']
    asset = selected_filters['asset']
    delivery = selected_filters['delivery']

    filtered: list[dict[str, Any]] = []
    for schedule in schedules:
        if status and status != ('active' if schedule['is_enabled'] else 'paused'):
            continue
        if cadence and schedule['cadence_value'] != cadence:
            continue
        if report_type and schedule['report_type_value'] != report_type:
            continue
        if asset and schedule['scope_asset_filter_key'] != asset:
            continue
        if delivery:
            channels = {str(item).lower() for item in schedule['notification_channel_ids']}
            if delivery == 'none':
                if channels:
                    continue
            elif delivery not in channels:
                continue
        if search:
            haystack = ' '.join(
                [
                    schedule['name'],
                    schedule['description'],
                    schedule['report_type'],
                    schedule['scope'],
                    schedule['scope_label'],
                    schedule['namespace'],
                    schedule['cadence'],
                    schedule['delivery_label'],
                ]
            ).casefold()
            if search not in haystack:
                continue
        filtered.append(schedule)
    return filtered
