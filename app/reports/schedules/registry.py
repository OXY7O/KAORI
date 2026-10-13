from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.extensions.db import db
from app.models.report import ReportSchedule
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


def _delivery_id_predicate(channel_id: int) -> Any:
    # Normalize serialized JSON arrays before an exact numeric token match.
    # Filtering stays in SQL and works across PostgreSQL and SQLite test DBs.
    normalized = func.replace(
        func.replace(
            func.replace(func.cast(ReportSchedule.notification_channel_ids, db.String), '[', ','),
            ']',
            ',',
        ),
        ' ',
        '',
    )
    return normalized.like(f'%,{channel_id},%')


def _schedule_search_predicate(search: str, channel_options: list[dict[str, Any]]) -> Any:
    value = search.casefold()
    pattern = f'%{value}%'
    fields = (
        ReportSchedule.name,
        ReportSchedule.description,
        ReportSchedule.report_type,
        ReportSchedule.scope_asset_label_snapshot,
        ReportSchedule.namespace,
        ReportSchedule.cadence,
    )
    predicates = [func.lower(func.coalesce(field, '')).like(pattern) for field in fields]
    predicates.append(func.lower(func.replace(ReportSchedule.report_type, '_', ' ')).like(pattern))
    for channel in channel_options:
        label = f'{channel.get("label", "")} {channel.get("provider", "")}'.casefold()
        channel_id = str(channel.get('channel_id') or '')
        if value in label and channel_id.isdigit():
            predicates.append(_delivery_id_predicate(int(channel_id)))
    return or_(*predicates)


def filter_schedule_statement(
    selected_filters: dict[str, str], channel_options: list[dict[str, Any]] | None = None
) -> Any:
    """Apply registry filters before SQL pagination; do not hydrate whole schedules."""
    statement = select(ReportSchedule)
    status = selected_filters['status']
    if status == 'active':
        statement = statement.where(ReportSchedule.is_enabled.is_(True))
    elif status == 'paused':
        statement = statement.where(ReportSchedule.is_enabled.is_(False))
    elif status:
        statement = statement.where(False)

    for key, column in (
        ('cadence', ReportSchedule.cadence),
        ('report_type', ReportSchedule.report_type),
    ):
        if selected_filters[key]:
            statement = statement.where(column == selected_filters[key])

    asset = selected_filters['asset']
    if asset:
        asset_type, separator, asset_id = asset.partition(':')
        if not separator or not asset_id:
            statement = statement.where(False)
        else:
            statement = statement.where(
                or_(
                    and_(
                        ReportSchedule.scope_asset_type == asset_type,
                        ReportSchedule.scope_asset_id == asset_id,
                    ),
                    and_(
                        ReportSchedule.scope_asset_type.is_(None),
                        ReportSchedule.cluster_id == asset_id,
                        asset_type == KUBERNETES_CLUSTER_ASSET_TYPE,
                    ),
                )
            )

    delivery = selected_filters['delivery']
    if delivery == 'none':
        statement = statement.where(
            or_(
                ReportSchedule.notification_channel_ids.is_(None),
                func.cast(ReportSchedule.notification_channel_ids, db.String) == '[]',
            )
        )
    elif delivery:
        if delivery.isdigit() and int(delivery) > 0:
            statement = statement.where(_delivery_id_predicate(int(delivery)))
        else:
            statement = statement.where(False)

    if selected_filters['search']:
        statement = statement.where(_schedule_search_predicate(selected_filters['search'], channel_options or []))
    return statement
