from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.report import ReportSchedule, ReportScheduleRun
from app.reports.catalog import REPORT_TYPE_OPTIONS, get_report_type_label
from app.reports.generate.form_options import PERIOD_OPTIONS
from app.reports.schedules.support import ensure_utc, format_datetime, get_default_timezone
from app.reports.scope import (
    KUBERNETES_CLUSTER_ASSET_TYPE,
    OBJECT_STORAGE_SYSTEM_ASSET_TYPE,
    resolve_report_scope,
)

DAY_OF_WEEK_OPTIONS: list[dict[str, Any]] = [
    {'value': 0, 'label': 'Monday'},
    {'value': 1, 'label': 'Tuesday'},
    {'value': 2, 'label': 'Wednesday'},
    {'value': 3, 'label': 'Thursday'},
    {'value': 4, 'label': 'Friday'},
    {'value': 5, 'label': 'Saturday'},
    {'value': 6, 'label': 'Sunday'},
]


def title_case_period_options() -> list[dict[str, str]]:
    return [{**item, 'label': str(item['label']).title()} for item in PERIOD_OPTIONS]


def format_period_label(value: str | None) -> str:
    normalized = str(value or '').strip()
    for item in PERIOD_OPTIONS:
        if item['value'] == normalized:
            return str(item['label']).title()
    return normalized.replace('_', ' ').title() or 'Not Available'


def format_cadence_detail(schedule: ReportSchedule) -> str:
    if schedule.cadence == 'weekly':
        day = next(
            (item['label'] for item in DAY_OF_WEEK_OPTIONS if item['value'] == schedule.day_of_week),
            'Monday',
        )
        return f'{day} at {schedule.run_time}'
    if schedule.cadence == 'monthly':
        return f'Day {schedule.day_of_month or 1} at {schedule.run_time}'
    return f'Every Day at {schedule.run_time}'


def serialize_schedule(
    schedule: ReportSchedule,
    cluster_map: dict[str, str],
    delivery_label_map: dict[int, str],
) -> dict[str, Any]:
    report_spec = next(
        (item for item in REPORT_TYPE_OPTIONS if item['value'] == schedule.report_type),
        REPORT_TYPE_OPTIONS[0],
    )
    status_tone = 'normal' if schedule.is_enabled else 'unknown'
    status_icon = 'play-circle' if schedule.is_enabled else 'pause-circle'
    delivery_channels = schedule.notification_channel_ids_as_list()
    delivery_labels = [delivery_label_map.get(item, f'Channel {item}') for item in delivery_channels]
    scope = resolve_report_scope(schedule)
    scope_label = (
        'Object Storage System'
        if schedule.scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE
        else 'Kubernetes Cluster'
    )
    return {
        'id': schedule.id,
        'name': schedule.name,
        'description': schedule.description or 'No description provided.',
        'report_type_value': schedule.report_type,
        'report_type': get_report_type_label(schedule.report_type),
        'report_icon': str(report_spec.get('icon') or 'file-text'),
        'report_family': str(report_spec.get('family') or 'analytics'),
        'cluster_id': schedule.cluster_id or '',
        'cluster': cluster_map.get(schedule.cluster_id or '', 'Not Applicable'),
        'object_storage_system_id': (
            schedule.scope_asset_id if schedule.scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE else ''
        ),
        'scope_asset_type': schedule.scope_asset_type or KUBERNETES_CLUSTER_ASSET_TYPE,
        'scope': (
            scope.label if scope is not None else (schedule.scope_asset_label_snapshot or 'Asset Selection Required')
        ),
        'scope_label': scope_label,
        'namespace': schedule.namespace
        or ('Not Applicable' if schedule.scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE else 'All Namespaces'),
        'period': format_period_label(schedule.period),
        'period_value': schedule.period,
        'output_format': str(schedule.output_format or '').upper(),
        'sections': schedule.sections_as_list(),
        'sections_count': len(schedule.sections_as_list()),
        'notification_channel_ids': delivery_channels,
        'delivery_labels': delivery_labels,
        'delivery_label': ', '.join(delivery_labels) if delivery_labels else 'No Notification',
        'cadence': schedule.cadence.title(),
        'cadence_value': schedule.cadence,
        'cadence_detail': format_cadence_detail(schedule),
        'run_time': schedule.run_time,
        'day_of_week': schedule.day_of_week,
        'day_of_month': schedule.day_of_month,
        'timezone': schedule.timezone,
        'is_enabled': bool(schedule.is_enabled),
        'status_meta': {
            'label': 'Active' if schedule.is_enabled else 'Paused',
            'tone': status_tone,
            'icon': status_icon,
        },
        'next_run_at': format_datetime(schedule.next_run_at, schedule.timezone),
        'last_run_at': format_datetime(schedule.last_run_at, schedule.timezone),
        'last_status': schedule.last_status or 'never_run',
        'last_status_label': (schedule.last_status or 'Never Run').replace('_', ' ').title(),
        'last_report_id': schedule.last_report_id,
        'created_by': schedule.created_by_display_name_snapshot or schedule.created_by_username_snapshot or 'System',
        'edit_state': schedule_edit_state(schedule),
    }


def serialize_run(
    run: ReportScheduleRun,
    schedule_context_map: dict[int, dict[str, str]],
) -> dict[str, Any]:
    delivery_result = run.delivery_result or {}
    requested = int(delivery_result.get('requested', 0) or 0)
    successful = int(delivery_result.get('successful', 0) or 0)
    failed = int(delivery_result.get('failed', 0) or 0)
    skipped = int(delivery_result.get('skipped', 0) or 0)
    if requested == 0:
        delivery_label = 'No Delivery'
        delivery_tone = 'unknown'
    elif failed:
        delivery_label = 'Delivery Failed' if successful == 0 else 'Partial Delivery'
        delivery_tone = 'critical' if successful == 0 else 'warning'
    elif successful:
        delivery_label = 'Delivered'
        delivery_tone = 'normal'
    else:
        delivery_label = 'Delivery Pending'
        delivery_tone = 'pending'

    duration = format_run_duration(run.started_at, run.finished_at)
    schedule_context = schedule_context_map.get(
        run.schedule_id or 0,
        {'name': 'Deleted Schedule', 'icon': 'calendar-clock'},
    )
    return {
        'id': run.id,
        'schedule_id': run.schedule_id,
        'schedule_name': schedule_context['name'],
        'schedule_icon': schedule_context['icon'],
        'report_id': run.report_id,
        'job_execution_id': run.job_execution_id,
        'status': run.status,
        'status_label': run.status.replace('_', ' ').title(),
        'status_tone': 'normal' if run.status == 'success' else 'critical' if run.status == 'failed' else 'pending',
        'result_summary': get_run_result_summary(run),
        'trigger_source': run.trigger_source.replace('_', ' ').title(),
        'started_at': format_datetime(run.started_at, get_default_timezone()),
        'finished_at': format_datetime(run.finished_at, get_default_timezone()),
        'duration': duration,
        'error_message': run.error_message,
        'delivery_result': delivery_result,
        'delivery_label': delivery_label,
        'delivery_tone': delivery_tone,
        'delivery_summary': f'{successful} Sent · {failed} Failed · {skipped} Skipped',
    }


def get_run_result_summary(run: ReportScheduleRun) -> str:
    status = str(run.status or '').strip().lower()
    error_message = str(run.error_message or '').strip().casefold()

    if status == 'failed':
        if 'storage' in error_message:
            return 'Storage unavailable · View details'
        return 'Execution failed · View details'
    if status == 'success':
        return 'Execution completed successfully'
    if status == 'queued':
        return 'Waiting for worker execution'
    if status in {'started', 'running'}:
        return 'Execution in progress'
    return 'Execution state recorded'


def format_run_duration(started_at: datetime | None, finished_at: datetime | None) -> str:
    if started_at is None:
        return 'Not Available'
    if finished_at is None:
        return 'In Progress'
    seconds = max(int((ensure_utc(finished_at) - ensure_utc(started_at)).total_seconds()), 0)
    if seconds < 60:
        return f'{seconds}s'
    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes}m {remaining_seconds}s' if remaining_seconds else f'{minutes}m'
    hours, remaining_minutes = divmod(minutes, 60)
    return f'{hours}h {remaining_minutes}m' if remaining_minutes else f'{hours}h'


def schedule_edit_state(schedule: ReportSchedule) -> dict[str, Any]:
    return {
        'name': schedule.name,
        'description': schedule.description or '',
        'cluster_id': schedule.cluster_id or '',
        'namespace': schedule.namespace or '',
        'object_storage_system_id': (
            schedule.scope_asset_id if schedule.scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE else ''
        ),
        'report_type': schedule.report_type,
        'period': schedule.period,
        'output_format': schedule.output_format,
        'sections': schedule.sections_as_list(),
        'cadence': schedule.cadence,
        'run_time': schedule.run_time,
        'day_of_week': str(schedule.day_of_week if schedule.day_of_week is not None else 0),
        'day_of_month': str(schedule.day_of_month if schedule.day_of_month is not None else 1),
        'timezone': schedule.timezone,
        'is_enabled': '1' if schedule.is_enabled else '0',
        'notification_channel_ids': schedule.notification_channel_ids_as_list(),
    }
