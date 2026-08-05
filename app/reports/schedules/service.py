from __future__ import annotations

from calendar import monthrange
from collections.abc import Mapping
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app
from sqlalchemy import select
from werkzeug.datastructures import ImmutableMultiDict, MultiDict

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.report import Report, ReportSchedule, ReportScheduleRun
from app.models.user import User
from app.reports.catalog import ReportContractError, get_report_type_label, validate_report_contract
from app.reports.delivery import get_delivery_channel_catalog
from app.reports.export.constants import DEFAULT_REPORT_DOMAIN, DEFAULT_REPORT_SOURCE_KIND
from app.reports.generate.service import (
    OUTPUT_FORMAT_OPTIONS,
    PERIOD_OPTIONS,
    REPORT_TYPE_OPTIONS,
    SECTION_OPTIONS,
    get_form_state_from_form,
    get_report_primary_output_format,
    validate_form_state,
)
from app.reports.jobs.service import ReportJobEnqueueError, enqueue_report_generation
from app.reports.schedules.failures import mark_schedule_dispatch_failed
from app.reports.storage.health import build_local_storage_health, build_s3_storage_health
from app.reports.storage.service import get_configured_storage_backend_name

CADENCE_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'daily',
        'label': 'Daily',
        'description': 'Run once every day at the configured time.',
    },
    {
        'value': 'weekly',
        'label': 'Weekly',
        'description': 'Run once every week on the selected day.',
    },
    {
        'value': 'monthly',
        'label': 'Monthly',
        'description': 'Run once every month on the selected date.',
    },
]

DAY_OF_WEEK_OPTIONS: list[dict[str, Any]] = [
    {'value': 0, 'label': 'Monday'},
    {'value': 1, 'label': 'Tuesday'},
    {'value': 2, 'label': 'Wednesday'},
    {'value': 3, 'label': 'Thursday'},
    {'value': 4, 'label': 'Friday'},
    {'value': 5, 'label': 'Saturday'},
    {'value': 6, 'label': 'Sunday'},
]

DEFAULT_TIMEZONE = 'Asia/Jakarta'


def get_report_schedules_payload(
    query_args: Mapping[str, str] | None = None,
    form_state: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    schedules = _get_schedule_rows()
    recent_runs = _get_recent_runs()
    storage_context = _get_storage_context()

    if form_state is None:
        form_state = build_default_schedule_form_state()

    return {
        'page_title': 'Report Schedules',
        'page_subtitle': (
            'Automate report generation and delivery through the dedicated Reports worker.'
        ),
        'status_label': 'Report worker enabled',
        'status_description': (
            'Schedules are dispatched through the dedicated Reports worker and recorded in Job Execution.'
        ),
        'summary_cards': get_summary_cards(
            schedules=schedules,
            recent_runs=recent_runs,
        ),
        'schedules': schedules,
        'recent_runs': recent_runs,
        'clusters': _get_cluster_options(),
        'report_type_options': REPORT_TYPE_OPTIONS,
        'period_options': PERIOD_OPTIONS,
        'output_format_options': OUTPUT_FORMAT_OPTIONS,
        'section_options': SECTION_OPTIONS,
        'section_options_by_report_type': _get_section_options_by_report_type(),
        'default_sections_by_report_type': _get_default_sections_by_report_type(),
        'cadence_options': CADENCE_OPTIONS,
        'day_of_week_options': DAY_OF_WEEK_OPTIONS,
        'day_of_month_options': list(range(1, 29)),
        'form_state': form_state,
        'errors': errors or [],
        'storage_context': storage_context,
        'scheduler_context': get_scheduler_context(storage_context),
        'recommended_actions': get_recommended_actions(),
        'delivery_channel_options': get_delivery_channel_catalog(),
    }


def get_summary_cards(
    *,
    schedules: list[dict[str, Any]],
    recent_runs: list[dict[str, Any]],
) -> list[dict[str, str]]:
    active_count = sum(1 for item in schedules if item['is_enabled'])
    paused_count = len(schedules) - active_count
    successful_runs = sum(1 for item in recent_runs if item['status'] == 'success')

    return [
        {
            'label': 'Total Schedules',
            'value': str(len(schedules)),
            'caption': 'Persisted recurring definitions',
            'icon': 'calendar-clock',
            'tone': 'blue',
        },
        {
            'label': 'Active Schedules',
            'value': str(active_count),
            'caption': 'Enabled schedules with next run tracking',
            'icon': 'play-circle',
            'tone': 'green',
        },
        {
            'label': 'Paused Schedules',
            'value': str(paused_count),
            'caption': 'Disabled schedules kept for later',
            'icon': 'pause-circle',
            'tone': 'purple',
        },
        {
            'label': 'Recent Successful Runs',
            'value': str(successful_runs),
            'caption': 'Latest recorded scheduler executions',
            'icon': 'check-circle-2',
            'tone': 'green',
        },
    ]


def build_default_schedule_form_state() -> dict[str, Any]:
    report_type = REPORT_TYPE_OPTIONS[0]['value']
    return {
        'name': '',
        'description': '',
        'cluster_id': '',
        'namespace': '',
        'report_type': report_type,
        'period': '30d',
        'output_format': get_report_primary_output_format(report_type),
        'sections': _get_default_sections(report_type),
        'cadence': 'weekly',
        'run_time': '08:00',
        'day_of_week': '0',
        'day_of_month': '1',
        'timezone': _get_default_timezone(),
        'is_enabled': '1',
        'notification_channels': [],
    }


def get_form_state_from_schedule_form(
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
) -> dict[str, Any]:
    report_form_state = get_form_state_from_form(form)
    state = build_default_schedule_form_state()
    state.update(report_form_state)
    state.update(
        {
            'name': form.get('name', '').strip(),
            'description': form.get('description', '').strip(),
            'cadence': form.get('cadence', 'weekly').strip(),
            'run_time': form.get('run_time', '08:00').strip(),
            'day_of_week': form.get('day_of_week', '0').strip(),
            'day_of_month': form.get('day_of_month', '1').strip(),
            'timezone': form.get('timezone', _get_default_timezone()).strip() or _get_default_timezone(),
            'is_enabled': '1' if form.get('is_enabled') in ['1', 'true', 'on', 'yes'] else '0',
            'notification_channels': [
                value.strip().lower() for value in form.getlist('notification_channels') if value.strip()
            ],
        }
    )
    return state


def create_report_schedule(
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
    user_id: int | None,
) -> tuple[bool, list[str], ReportSchedule | None]:
    form_state = get_form_state_from_schedule_form(form)
    errors = validate_schedule_form_state(form_state)

    if errors:
        return False, errors, None

    schedule = ReportSchedule()
    schedule.report_domain = DEFAULT_REPORT_DOMAIN
    schedule.source_kind = DEFAULT_REPORT_SOURCE_KIND
    _apply_form_state_to_schedule(schedule, form_state)
    schedule.created_by_id = user_id
    _apply_user_snapshot(schedule, user_id)
    schedule.next_run_at = calculate_next_run_at(schedule)

    db.session.add(schedule)
    db.session.commit()

    return True, [], schedule


def update_report_schedule(
    schedule_id: int,
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
) -> tuple[bool, list[str]]:
    schedule = db.session.get(ReportSchedule, schedule_id)
    if schedule is None:
        return False, ['Schedule not found.']

    form_state = get_form_state_from_schedule_form(form)
    errors = validate_schedule_form_state(form_state)

    if errors:
        return False, errors

    _apply_form_state_to_schedule(schedule, form_state)
    schedule.next_run_at = calculate_next_run_at(schedule)
    db.session.commit()

    return True, []


def toggle_report_schedule(schedule_id: int) -> tuple[bool, str]:
    schedule = db.session.get(ReportSchedule, schedule_id)
    if schedule is None:
        return False, 'Schedule not found.'

    schedule.is_enabled = not bool(schedule.is_enabled)
    if schedule.is_enabled:
        schedule.next_run_at = calculate_next_run_at(schedule)
    db.session.commit()

    status = 'enabled' if schedule.is_enabled else 'paused'
    return True, f'Schedule {status} successfully.'


def delete_report_schedule(schedule_id: int) -> tuple[bool, str]:
    schedule = db.session.get(ReportSchedule, schedule_id)
    if schedule is None:
        return False, 'Schedule not found.'

    db.session.delete(schedule)
    db.session.commit()
    return True, 'Schedule deleted successfully.'


def run_schedule_now(
    schedule_id: int,
    *,
    requested_by_user_id: int | None = None,
) -> tuple[bool, str, int | None]:
    schedule = db.session.get(ReportSchedule, schedule_id)
    if schedule is None:
        return False, 'Schedule not found.', None

    from app.reports.schedules.job_adapter import dispatch_report_schedule_job

    result = dispatch_report_schedule_job(
        requested_by_user_id=requested_by_user_id,
        trigger_type='manual',
        parameters={'schedule_id': schedule_id, 'limit': 1},
    )
    if not result.accepted:
        return False, result.message, None
    return True, result.message, None


def run_due_schedules(
    *,
    limit: int = 20,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_utc = _ensure_utc(now or datetime.now(UTC))
    due_schedules = db.session.scalars(
        select(ReportSchedule)
        .where(
            ReportSchedule.is_enabled.is_(True),
            ReportSchedule.next_run_at.is_not(None),
            ReportSchedule.next_run_at <= now_utc,
        )
        .order_by(ReportSchedule.next_run_at.asc(), ReportSchedule.id.asc())
        .limit(limit)
    ).all()

    results: list[dict[str, Any]] = []

    for schedule in due_schedules:
        if dry_run:
            results.append(
                {
                    'schedule_id': schedule.id,
                    'name': schedule.name,
                    'status': 'due',
                    'next_run_at': schedule.next_run_at,
                }
            )
            continue

        success, message, report_id = execute_schedule(schedule, trigger_source='scheduler')
        results.append(
            {
                'schedule_id': schedule.id,
                'name': schedule.name,
                'status': 'success' if success else 'failed',
                'message': message,
                'report_id': report_id,
            }
        )

    return {
        'checked_at': now_utc,
        'dry_run': dry_run,
        'due_count': len(due_schedules),
        'results': results,
    }


def execute_schedule(
    schedule: ReportSchedule,
    *,
    trigger_source: str,
) -> tuple[bool, str, int | None]:
    run = ReportScheduleRun()
    run.schedule_id = schedule.id
    run.status = 'started'
    run.trigger_source = trigger_source
    run.started_at = datetime.now(UTC)
    db.session.add(run)

    try:
        validate_report_contract(
            report_type=schedule.report_type,
            output_format=schedule.output_format,
            cluster_id=schedule.cluster_id,
        )
    except ReportContractError as exc:
        run.status = 'failed'
        run.finished_at = datetime.now(UTC)
        run.error_message = str(exc)
        schedule.last_status = 'failed'
        schedule.last_run_at = run.finished_at
        schedule.next_run_at = calculate_next_run_at(schedule, base=run.finished_at)
        db.session.commit()
        return False, str(exc), None

    report = _create_report_from_schedule(schedule)
    db.session.add(report)
    db.session.flush()
    run.report_id = report.id
    schedule.last_run_at = run.started_at
    schedule.last_report_id = report.id
    schedule.next_run_at = calculate_next_run_at(schedule, base=run.started_at)
    db.session.commit()

    try:
        dispatch = enqueue_report_generation(
            report,
            requested_by_user_id=schedule.created_by_id,
            trigger_type=trigger_source,
            schedule_id=schedule.id,
            schedule_run_id=run.id,
        )
    except ReportJobEnqueueError:
        current_app.logger.exception(
            'Scheduled report %s could not be queued for schedule %s.',
            report.id,
            schedule.id,
        )
        db.session.rollback()
        failed_report_id = mark_schedule_dispatch_failed(
            schedule_id=schedule.id,
            schedule_run_id=run.id,
            report_id=report.id,
        )
        return False, 'The scheduled report could not be queued.', failed_report_id

    run = db.session.get(ReportScheduleRun, run.id)
    if run is not None:
        run.job_execution_id = dispatch.job.id
        run.status = 'queued'
    schedule = db.session.get(ReportSchedule, schedule.id)
    if schedule is not None:
        schedule.last_status = 'queued'
    db.session.commit()
    return True, dispatch.message, report.id


def validate_schedule_form_state(form_state: dict[str, Any]) -> list[str]:
    errors = validate_form_state(form_state)

    if not form_state['name']:
        errors.append('Schedule name is required.')

    if form_state['cadence'] not in {item['value'] for item in CADENCE_OPTIONS}:
        errors.append('Please select a valid schedule cadence.')

    if not _is_valid_run_time(form_state['run_time']):
        errors.append('Run time must use HH:MM format.')

    if form_state['cadence'] == 'weekly':
        day_of_week = _parse_optional_int(form_state['day_of_week'])
        if day_of_week is None or day_of_week < 0 or day_of_week > 6:
            errors.append('Weekly schedules require a valid day of week.')

    if form_state['cadence'] == 'monthly':
        day_of_month = _parse_optional_int(form_state['day_of_month'])
        if day_of_month is None or day_of_month < 1 or day_of_month > 28:
            errors.append('Monthly schedules currently support day 1 through 28 to avoid invalid calendar dates.')

    if not _is_valid_timezone(form_state['timezone']):
        errors.append('Please use a valid IANA timezone, for example Asia/Jakarta.')

    return errors


def calculate_next_run_at(
    schedule: ReportSchedule,
    *,
    base: datetime | None = None,
) -> datetime:
    base_utc = _ensure_utc(base or datetime.now(UTC))
    tz = _get_timezone(schedule.timezone)
    local_base = base_utc.astimezone(tz)
    run_hour, run_minute = _parse_run_time(schedule.run_time)
    target_time = time(hour=run_hour, minute=run_minute)

    if schedule.cadence == 'daily':
        candidate = datetime.combine(local_base.date(), target_time, tzinfo=tz)
        if candidate <= local_base:
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC)

    if schedule.cadence == 'weekly':
        target_weekday = schedule.day_of_week if schedule.day_of_week is not None else 0
        days_ahead = (target_weekday - local_base.weekday()) % 7
        candidate = datetime.combine(local_base.date(), target_time, tzinfo=tz) + timedelta(days=days_ahead)
        if candidate <= local_base:
            candidate += timedelta(days=7)
        return candidate.astimezone(UTC)

    target_day = schedule.day_of_month or 1
    year = local_base.year
    month = local_base.month
    day = min(target_day, monthrange(year, month)[1])
    candidate = datetime.combine(local_base.replace(day=day).date(), target_time, tzinfo=tz)
    if candidate <= local_base:
        month += 1
        if month > 12:
            month = 1
            year += 1
        day = min(target_day, monthrange(year, month)[1])
        candidate = datetime(year, month, day, run_hour, run_minute, tzinfo=tz)
    return candidate.astimezone(UTC)


def get_scheduler_context(storage_context: dict[str, Any]) -> list[dict[str, str]]:
    telegram = next(
        (item for item in get_delivery_channel_catalog() if item['value'] == 'telegram'),
        None,
    )
    return [
        {
            'label': 'Database Schedule',
            'description': 'Cadence, scope, sections, owner, delivery channels, and next run time are stored with each schedule.',
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'database',
        },
        {
            'label': 'Reports Worker',
            'description': 'Due and manual schedule runs use the dedicated Reports queue and canonical Job Execution records.',
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'worker',
        },
        {
            'label': 'Artifact Storage',
            'description': storage_context['description'],
            'status': storage_context['status'],
            'tone': 'normal' if storage_context['status'] == 'Ready' else 'warning',
            'icon': 'hard-drive',
        },
        {
            'label': 'Telegram Delivery',
            'description': telegram['description'] if telegram else 'Telegram delivery is unavailable.',
            'status': telegram['status'] if telegram else 'Unavailable',
            'tone': telegram['tone'] if telegram else 'unknown',
            'icon': 'send',
        },
    ]


def get_recommended_actions() -> list[str]:
    return [
        'Run the database migration before enabling delivery channels.',
        'Start the dedicated Reports worker and keep the Report Schedule Dispatcher enabled in Job Configuration.',
        'Use Run Now to validate report generation, artifact storage, and Telegram delivery before unattended execution.',
        'Configure REPORT_TELEGRAM_BOT_TOKEN, REPORT_TELEGRAM_CHAT_ID, and REPORT_PUBLIC_BASE_URL for Telegram notifications.',
    ]

def _apply_form_state_to_schedule(schedule: ReportSchedule, form_state: dict[str, Any]) -> None:
    schedule.name = form_state['name']
    schedule.description = form_state['description'] or None
    schedule.report_type = form_state['report_type']
    schedule.report_domain = DEFAULT_REPORT_DOMAIN
    schedule.source_kind = DEFAULT_REPORT_SOURCE_KIND
    schedule.cluster_id = form_state['cluster_id'] or None
    schedule.namespace = form_state['namespace'] or None
    schedule.period = form_state['period']
    schedule.output_format = form_state['output_format']
    schedule.sections = list(form_state['sections'])
    schedule.notification_channels = list(form_state.get('notification_channels') or [])
    schedule.cadence = form_state['cadence']
    schedule.run_time = form_state['run_time']
    schedule.day_of_week = _parse_optional_int(form_state['day_of_week']) if form_state['cadence'] == 'weekly' else None
    schedule.day_of_month = (
        _parse_optional_int(form_state['day_of_month']) if form_state['cadence'] == 'monthly' else None
    )
    schedule.timezone = form_state['timezone']
    schedule.is_enabled = form_state['is_enabled'] == '1'


def _apply_user_snapshot(schedule: ReportSchedule, user_id: int | None) -> None:
    if user_id is None:
        return

    user = db.session.get(User, user_id)
    if user is None:
        return

    schedule.created_by_username_snapshot = user.username
    schedule.created_by_display_name_snapshot = user.display_label
    schedule.created_by_auth_source_snapshot = user.auth_source


def _create_report_from_schedule(schedule: ReportSchedule) -> Report:
    report = Report()
    report.name = f'{schedule.name} - {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}'
    report.report_type = schedule.report_type
    report.report_domain = schedule.report_domain
    report.source_kind = schedule.source_kind
    report.cluster_id = schedule.cluster_id
    report.namespace = schedule.namespace
    report.period = schedule.period
    report.output_format = schedule.output_format
    report.status = 'requested'
    report.sections = schedule.sections_as_list()
    report.generated_by_id = schedule.created_by_id
    report.generated_by_username_snapshot = schedule.created_by_username_snapshot
    report.generated_by_display_name_snapshot = schedule.created_by_display_name_snapshot
    report.generated_by_auth_source_snapshot = schedule.created_by_auth_source_snapshot
    report.file_path = None
    report.file_size_bytes = None
    report.error_message = None
    return report


def _get_schedule_rows() -> list[dict[str, Any]]:
    schedules = db.session.scalars(
        select(ReportSchedule).order_by(ReportSchedule.created_at.desc(), ReportSchedule.id.desc())
    ).all()
    cluster_map = _get_cluster_map([item.cluster_id for item in schedules if item.cluster_id])

    return [_serialize_schedule(item, cluster_map) for item in schedules]


def _get_recent_runs(limit: int = 8) -> list[dict[str, Any]]:
    runs = db.session.scalars(
        select(ReportScheduleRun)
        .order_by(ReportScheduleRun.started_at.desc(), ReportScheduleRun.id.desc())
        .limit(limit)
    ).all()
    schedule_map = _get_schedule_map([item.schedule_id for item in runs if item.schedule_id])

    return [_serialize_run(item, schedule_map) for item in runs]


def _serialize_schedule(schedule: ReportSchedule, cluster_map: dict[str, str]) -> dict[str, Any]:
    status_tone = 'green' if schedule.is_enabled else 'gray'
    status_icon = 'play-circle' if schedule.is_enabled else 'pause-circle'
    return {
        'id': schedule.id,
        'name': schedule.name,
        'description': schedule.description or 'No description provided.',
        'report_type_value': schedule.report_type,
        'report_type': get_report_type_label(schedule.report_type),
        'cluster_id': schedule.cluster_id or '',
        'cluster': cluster_map.get(schedule.cluster_id or '', 'Cluster Selection Required'),
        'namespace': schedule.namespace or 'All Namespaces',
        'period': schedule.period,
        'output_format': str(schedule.output_format or '').upper(),
        'sections': schedule.sections_as_list(),
        'sections_count': len(schedule.sections_as_list()),
        'notification_channels': schedule.notification_channels_as_list(),
        'cadence': schedule.cadence.title(),
        'cadence_value': schedule.cadence,
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
        'next_run_at': _format_datetime(schedule.next_run_at, schedule.timezone),
        'last_run_at': _format_datetime(schedule.last_run_at, schedule.timezone),
        'last_status': schedule.last_status or 'Never run',
        'last_report_id': schedule.last_report_id,
        'created_by': schedule.created_by_display_name_snapshot or schedule.created_by_username_snapshot or 'System',
        'edit_state': _schedule_edit_state(schedule),
    }


def _serialize_run(run: ReportScheduleRun, schedule_map: dict[int, str]) -> dict[str, Any]:
    return {
        'id': run.id,
        'schedule_id': run.schedule_id,
        'schedule_name': schedule_map.get(run.schedule_id or 0, 'Deleted schedule'),
        'report_id': run.report_id,
        'status': run.status,
        'status_label': run.status.replace('_', ' ').title(),
        'status_tone': 'green' if run.status == 'success' else 'red' if run.status == 'failed' else 'blue',
        'trigger_source': run.trigger_source.replace('_', ' ').title(),
        'started_at': _format_datetime(run.started_at, _get_default_timezone()),
        'finished_at': _format_datetime(run.finished_at, _get_default_timezone()),
        'error_message': run.error_message,
        'delivery_result': run.delivery_result or {},
    }


def _schedule_edit_state(schedule: ReportSchedule) -> dict[str, Any]:
    return {
        'name': schedule.name,
        'description': schedule.description or '',
        'cluster_id': schedule.cluster_id or '',
        'namespace': schedule.namespace or '',
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
        'notification_channels': schedule.notification_channels_as_list(),
    }


def _get_cluster_options() -> list[dict[str, str]]:
    clusters = db.session.scalars(select(Cluster).order_by(Cluster.name.asc())).all()
    return [{'value': item.id, 'label': item.name} for item in clusters]


def _get_cluster_map(cluster_ids: list[str]) -> dict[str, str]:
    if not cluster_ids:
        return {}
    clusters = db.session.scalars(select(Cluster).where(Cluster.id.in_(cluster_ids))).all()
    return {item.id: item.name for item in clusters}


def _get_schedule_map(schedule_ids: list[int]) -> dict[int, str]:
    if not schedule_ids:
        return {}
    schedules = db.session.scalars(select(ReportSchedule).where(ReportSchedule.id.in_(schedule_ids))).all()
    return {item.id: item.name for item in schedules}


def _get_default_sections(report_type: str) -> list[str]:
    for item in REPORT_TYPE_OPTIONS:
        if item['value'] == report_type:
            return list(item['default_sections'])
    return list(REPORT_TYPE_OPTIONS[0]['default_sections'])


def _get_section_options_by_report_type() -> dict[str, list[dict[str, str]]]:
    section_map = {item['value']: item for item in SECTION_OPTIONS}
    return {
        item['value']: [section_map[section] for section in item['default_sections'] if section in section_map]
        for item in REPORT_TYPE_OPTIONS
    }


def _get_default_sections_by_report_type() -> dict[str, list[str]]:
    return {item['value']: list(item['default_sections']) for item in REPORT_TYPE_OPTIONS}


def _get_storage_context() -> dict[str, Any]:
    try:
        backend_name = get_configured_storage_backend_name()
        if backend_name == 's3':
            health = build_s3_storage_health()
            ready = bool(health.get('configuration_complete', False))
            return {
                'backend': 's3',
                'status': 'Ready' if ready else 'Needs Review',
                'tone': 'blue' if ready else 'amber',
                'description': 'S3-compatible storage is configured for scheduled report artifacts.'
                if ready
                else 'S3-compatible storage requires bucket/dependency configuration review.',
            }

        health = build_local_storage_health()
        ready = bool(health.get('root_writable', False))
        return {
            'backend': 'local',
            'status': 'Ready' if ready else 'Needs Review',
            'tone': 'blue' if ready else 'amber',
            'description': 'Local storage is writable for scheduled report artifacts.'
            if ready
            else 'Local report storage root needs write permission review.',
        }
    except Exception as exc:
        return {
            'backend': 'unknown',
            'status': 'Needs Review',
            'tone': 'amber',
            'description': f'Storage readiness could not be evaluated: {exc}',
        }


def _get_default_timezone() -> str:
    return str(current_app.config.get('REPORT_SCHEDULE_TIMEZONE', DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE)


def _is_valid_run_time(value: str) -> bool:
    try:
        _parse_run_time(value)
        return True
    except ValueError:
        return False


def _parse_run_time(value: str) -> tuple[int, int]:
    hour_raw, minute_raw = value.split(':', maxsplit=1)
    hour = int(hour_raw)
    minute = int(minute_raw)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError('Invalid run time')
    return hour, minute


def _parse_optional_int(value: Any) -> int | None:
    try:
        if value in [None, '']:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_valid_timezone(value: str) -> bool:
    try:
        ZoneInfo(value)
        return True
    except ZoneInfoNotFoundError:
        return False


def _get_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _format_datetime(value: datetime | None, timezone: str) -> str:
    if value is None:
        return 'Never'
    return value.astimezone(_get_timezone(timezone)).strftime('%Y-%m-%d %H:%M %Z')
