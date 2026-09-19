from __future__ import annotations

from calendar import monthrange
from collections.abc import Callable, Mapping
from datetime import (
    UTC,
    datetime,
    time,
    timedelta,
)
from typing import Any

from flask import current_app
from sqlalchemy import func, or_, select
from werkzeug.datastructures import ImmutableMultiDict, MultiDict

from app.common.celery_queue_health import get_queue_readiness
from app.common.pagination import PER_PAGE_OPTIONS, paginate_select, paginate_sequence
from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.object_storage import ObjectStorageSystem
from app.models.report import Report, ReportSchedule, ReportScheduleRun
from app.models.user import User
from app.reports.catalog import (
    ReportContractError,
    get_report_type_spec,
    validate_report_contract,
)
from app.reports.export.constants import DEFAULT_REPORT_DOMAIN, DEFAULT_REPORT_SOURCE_KIND
from app.reports.generate.service import (
    OUTPUT_FORMAT_OPTIONS,
    REPORT_TYPE_OPTIONS,
    SECTION_OPTIONS,
    get_form_state_from_form,
    get_report_primary_output_format,
    validate_form_state,
)
from app.reports.jobs.queue import get_reports_queue_name
from app.reports.jobs.service import ReportJobEnqueueError, enqueue_report_generation
from app.reports.notifications import get_report_notification_channel_options
from app.reports.schedules.delivery import get_recommended_actions, get_scheduler_context
from app.reports.schedules.failures import mark_schedule_dispatch_failed
from app.reports.schedules.presentation import DAY_OF_WEEK_OPTIONS
from app.reports.schedules.presentation import serialize_run as _serialize_run
from app.reports.schedules.presentation import serialize_schedule as _serialize_schedule
from app.reports.schedules.presentation import title_case_period_options as _title_case_period_options
from app.reports.schedules.registry import filter_schedule_rows as _filter_schedule_rows
from app.reports.schedules.registry import get_selected_filters as _get_selected_filters
from app.reports.schedules.support import build_schedule_evidence_snapshot as _build_schedule_evidence_snapshot
from app.reports.schedules.support import ensure_utc as _ensure_utc
from app.reports.schedules.support import get_cluster_map as _get_cluster_map
from app.reports.schedules.support import get_cluster_options as _get_cluster_options
from app.reports.schedules.support import get_default_sections as _get_default_sections
from app.reports.schedules.support import get_default_sections_by_report_type as _get_default_sections_by_report_type
from app.reports.schedules.support import get_default_timezone as _get_default_timezone
from app.reports.schedules.support import get_delivery_channel_options as _get_delivery_channel_options
from app.reports.schedules.support import get_namespace_options_by_cluster as _get_namespace_options_by_cluster
from app.reports.schedules.support import get_object_storage_system_options as _get_object_storage_system_options
from app.reports.schedules.support import get_schedule_context_map as _get_schedule_context_map
from app.reports.schedules.support import (
    get_section_options_by_report_type as _get_section_options_by_report_type_impl,
)
from app.reports.schedules.support import get_timezone as _get_timezone
from app.reports.schedules.support import is_valid_run_time as _is_valid_run_time
from app.reports.schedules.support import is_valid_timezone as _is_valid_timezone
from app.reports.schedules.support import parse_optional_int as _parse_optional_int
from app.reports.schedules.support import parse_run_time as _parse_run_time
from app.reports.scope import (
    KUBERNETES_CLUSTER_ASSET_TYPE,
    OBJECT_STORAGE_SYSTEM_ASSET_TYPE,
)
from app.reports.storage.service import get_configured_storage_backend_name, get_report_storage_backend_status

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


RUN_PERIOD_OPTIONS: list[dict[str, str]] = [
    {'value': '24h', 'label': 'Last 24 Hours'},
    {'value': '7d', 'label': 'Last 7 Days'},
    {'value': '30d', 'label': 'Last 30 Days'},
    {'value': '90d', 'label': 'Last 90 Days'},
    {'value': 'all', 'label': 'All Retained'},
]

RUN_PERIOD_DELTAS: dict[str, timedelta] = {
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    '90d': timedelta(days=90),
}


def get_report_schedules_payload(
    query_args: Mapping[str, str] | None = None,
    form_state: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    *,
    edit_schedule_id: int | None = None,
    edit_form_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_args = query_args or {}
    all_schedules = _get_schedule_rows()
    recent_runs = _get_recent_runs()
    run_rows, run_pagination, run_selected_filters = _get_run_registry(
        query_args,
        all_schedules,
    )
    cluster_options = _get_cluster_options()
    object_storage_system_options = _get_object_storage_system_options()
    storage_context = _get_storage_context()
    worker_context = get_queue_readiness(get_reports_queue_name())
    selected_filters = _get_selected_filters(query_args)
    filtered_schedules = _filter_schedule_rows(all_schedules, selected_filters)
    schedules, pagination = paginate_sequence(
        filtered_schedules,
        page=query_args.get('page', 1),
        per_page=query_args.get('per_page', PER_PAGE_OPTIONS[0]),
    )

    if form_state is None:
        form_state = build_default_schedule_form_state()

    if edit_schedule_id is None:
        edit_schedule_id = _parse_optional_int(query_args.get('edit_schedule_id'))
    edit_schedule = next(
        (item for item in all_schedules if item['id'] == edit_schedule_id),
        None,
    )
    if edit_schedule is not None and edit_form_state is not None:
        edit_schedule = {**edit_schedule, 'edit_state': edit_form_state}

    report_family_by_report_type = {
        item['value']: str(item.get('family') or 'analytics') for item in REPORT_TYPE_OPTIONS
    }
    allowed_formats_by_report_type = {
        item['value']: list(item.get('allowed_formats') or []) for item in REPORT_TYPE_OPTIONS
    }
    scope_asset_type_by_report_type = {
        item['value']: str(item.get('scope_asset_type') or KUBERNETES_CLUSTER_ASSET_TYPE)
        for item in REPORT_TYPE_OPTIONS
    }
    report_domain_by_report_type = {
        item['value']: str(item.get('domain') or DEFAULT_REPORT_DOMAIN) for item in REPORT_TYPE_OPTIONS
    }

    return {
        'page_title': 'Report Schedules',
        'page_subtitle': (
            'Automate Analytics PDF, XLSX, or CSV artifacts and Inventory XLSX/CSV exports with timezone-aware schedules and retained run evidence.'
        ),
        'status_label': f'Reports Worker {worker_context["label"]}',
        'status_description': worker_context['description'],
        'summary_cards': get_summary_cards(
            schedules=all_schedules,
            recent_runs=recent_runs,
        ),
        'schedules': schedules,
        'all_schedule_count': len(all_schedules),
        'recent_runs': recent_runs,
        'run_rows': run_rows,
        'run_pagination': run_pagination,
        'run_selected_filters': run_selected_filters,
        'run_filter_options': _get_run_filter_options(all_schedules),
        'run_registry_query_params': {
            'workspace': 'runs',
            **{key: value for key, value in run_selected_filters.items() if value},
        },
        'active_workspace': (
            'runs' if str(query_args.get('workspace', '') or '').strip().lower() == 'runs' else 'registry'
        ),
        'clusters': cluster_options,
        'namespace_options_by_cluster': _get_namespace_options_by_cluster(),
        'object_storage_systems': object_storage_system_options,
        'report_type_options': REPORT_TYPE_OPTIONS,
        'period_options': _title_case_period_options(),
        'output_format_options': OUTPUT_FORMAT_OPTIONS,
        'section_options': SECTION_OPTIONS,
        'section_options_by_report_type': _get_section_options_by_report_type_impl(SECTION_OPTIONS),
        'default_sections_by_report_type': _get_default_sections_by_report_type(),
        'report_family_by_report_type': report_family_by_report_type,
        'allowed_formats_by_report_type': allowed_formats_by_report_type,
        'scope_asset_type_by_report_type': scope_asset_type_by_report_type,
        'report_domain_by_report_type': report_domain_by_report_type,
        'cadence_options': CADENCE_OPTIONS,
        'day_of_week_options': DAY_OF_WEEK_OPTIONS,
        'day_of_month_options': list(range(1, 29)),
        'form_state': form_state,
        'errors': errors or [],
        'open_create_dialog': bool(errors) and edit_schedule is None,
        'edit_schedule': edit_schedule,
        'storage_context': storage_context,
        'run_actions_enabled': bool(storage_context.get('ready', False)),
        'worker_context': worker_context,
        'automation_posture': get_automation_posture(storage_context, worker_context),
        'scheduler_context': get_scheduler_context(storage_context, worker_context),
        'recommended_actions': get_recommended_actions(),
        'delivery_channel_options': _get_delivery_channel_options(),
        'filter_options': _get_schedule_filter_options(
            all_schedules,
            cluster_options,
            object_storage_system_options,
        ),
        'selected_filters': selected_filters,
        'pagination': pagination,
        'per_page_options': list(PER_PAGE_OPTIONS),
        'registry_query_params': {
            'workspace': 'registry',
            **{
                key: value
                for key, value in selected_filters.items()
                if key in {'search', 'status', 'cadence', 'report_type', 'asset', 'delivery'} and value
            },
        },
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
        'object_storage_system_id': '',
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
        'notification_channel_ids': [],
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
            'notification_channel_ids': [
                int(value)
                for value in form.getlist('notification_channel_ids')
                if str(value).isdigit() and int(value) > 0
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


def run_due_schedules(
    *,
    limit: int = 20,
    dry_run: bool = False,
    now: datetime | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
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

    total_due = len(due_schedules)
    for index, schedule in enumerate(due_schedules, start=1):
        if progress_callback is not None:
            progress_callback(index - 1, total_due, schedule.name)
        if dry_run:
            results.append(
                {
                    'schedule_id': schedule.id,
                    'name': schedule.name,
                    'status': 'due',
                    'next_run_at': schedule.next_run_at.isoformat() if schedule.next_run_at else None,
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
        if progress_callback is not None:
            progress_callback(index, total_due, schedule.name)

    return {
        'checked_at': now_utc.isoformat(),
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
    run.schedule_snapshot = _build_schedule_evidence_snapshot(schedule)
    db.session.add(run)

    storage_status = get_report_storage_backend_status()
    if not bool(storage_status.get('write_available', False)):
        run.status = 'failed'
        run.finished_at = datetime.now(UTC)
        run.error_message = 'Artifact storage is unavailable. Scheduled report generation was not started.'
        schedule.last_status = 'failed'
        schedule.last_run_at = run.finished_at
        schedule.next_run_at = calculate_next_run_at(schedule, base=run.finished_at)
        db.session.commit()
        return False, 'Artifact storage is unavailable. The scheduled report was not created.', None

    try:
        validate_report_contract(
            report_type=schedule.report_type,
            output_format=schedule.output_format,
            cluster_id=schedule.cluster_id,
            scope_asset_type=schedule.scope_asset_type,
            scope_asset_id=schedule.scope_asset_id,
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

    dispatch_job = dispatch.job
    if dispatch_job is None:
        failed_report_id = mark_schedule_dispatch_failed(
            schedule_id=schedule.id,
            schedule_run_id=run.id,
            report_id=report.id,
        )
        return False, 'The scheduled report could not be queued.', failed_report_id

    run = db.session.get(ReportScheduleRun, run.id)
    if run is not None:
        run.job_execution_id = dispatch_job.id
        run.status = 'queued'
    refreshed_schedule = db.session.get(ReportSchedule, schedule.id)
    if refreshed_schedule is not None:
        refreshed_schedule.last_status = 'queued'
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

    selected_channel_ids = set(form_state.get('notification_channel_ids') or [])
    if selected_channel_ids:
        report_domain = get_report_type_spec(form_state['report_type']).domain
        options = {
            int(item['channel_id']): item for item in get_report_notification_channel_options(domain=report_domain)
        }
        for channel_id in sorted(selected_channel_ids):
            option = options.get(channel_id)
            if option is None:
                errors.append(f'Notification channel {channel_id} no longer exists.')
            elif not option.get('selectable'):
                errors.append(
                    f'Notification channel {option["label"]} must be enabled, tested, and allowed for Scheduled Reports.'
                )

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


def get_automation_posture(
    storage_context: dict[str, Any],
    worker_context: dict[str, Any],
) -> dict[str, str]:
    storage_ready = bool(storage_context.get('ready', False))
    worker_tone = str(worker_context.get('tone') or 'unknown')
    worker_ready = worker_tone == 'normal'

    if not storage_ready:
        return {
            'status_label': 'Execution Needs Review',
            'status_tone': 'warning',
            'title': 'Artifact Execution Paused',
            'description': (
                'Schedule definitions remain available for management, but Run Now and unattended '
                'generation stay paused until artifact storage is writable.'
            ),
            'execution_label': 'Paused',
            'execution_tone': 'warning',
        }

    if not worker_ready:
        return {
            'status_label': 'Dispatcher Needs Review',
            'status_tone': worker_tone if worker_tone in {'warning', 'critical', 'unknown'} else 'warning',
            'title': 'Dispatcher Needs Attention',
            'description': (
                'Artifact storage is writable, but unattended execution depends on a healthy Reports '
                'worker consuming the dedicated queue.'
            ),
            'execution_label': 'Needs Review',
            'execution_tone': worker_tone if worker_tone in {'warning', 'critical', 'unknown'} else 'warning',
        }

    return {
        'status_label': 'Automation Ready',
        'status_tone': 'normal',
        'title': 'Ready for Unattended Execution',
        'description': (
            'Schedule definitions, the Reports worker, and artifact storage are ready for Run Now '
            'and recurring report execution.'
        ),
        'execution_label': 'Ready',
        'execution_tone': 'normal',
    }


def _apply_form_state_to_schedule(schedule: ReportSchedule, form_state: dict[str, Any]) -> None:
    schedule.name = form_state['name']
    schedule.description = form_state['description'] or None
    schedule.report_type = form_state['report_type']
    spec = get_report_type_spec(schedule.report_type)
    schedule.report_domain = spec.domain
    schedule.source_kind = spec.source_kind
    schedule.scope_asset_type = spec.scope_asset_type
    if spec.scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
        system_id = str(form_state.get('object_storage_system_id') or '').strip()
        system = db.session.get(ObjectStorageSystem, system_id) if system_id else None
        schedule.scope_asset_id = system_id or None
        schedule.scope_asset_label_snapshot = system.name if system is not None else None
        schedule.cluster_id = None
        schedule.namespace = None
    else:
        cluster_id = str(form_state.get('cluster_id') or '').strip()
        cluster = db.session.get(Cluster, cluster_id) if cluster_id else None
        schedule.scope_asset_id = cluster_id or None
        schedule.scope_asset_label_snapshot = cluster.name if cluster is not None else None
        schedule.cluster_id = cluster_id or None
        schedule.namespace = form_state['namespace'] or None
    schedule.period = form_state['period']
    schedule.output_format = form_state['output_format']
    schedule.sections = list(form_state['sections'])
    schedule.notification_channel_ids = list(form_state.get('notification_channel_ids') or [])
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
    report.scope_asset_type = schedule.scope_asset_type
    report.scope_asset_id = schedule.scope_asset_id
    report.scope_asset_label_snapshot = schedule.scope_asset_label_snapshot
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


def _get_run_registry(
    query_args: Mapping[str, str],
    schedules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    selected_filters = _get_run_selected_filters(query_args)
    statement = (
        select(ReportScheduleRun)
        .outerjoin(ReportSchedule, ReportScheduleRun.schedule_id == ReportSchedule.id)
        .order_by(ReportScheduleRun.started_at.desc(), ReportScheduleRun.id.desc())
    )

    search = selected_filters['run_search'].casefold()
    if search:
        pattern = f'%{search}%'
        statement = statement.where(
            or_(
                func.lower(func.coalesce(ReportSchedule.name, 'deleted schedule')).like(pattern),
                func.lower(func.coalesce(ReportScheduleRun.error_message, '')).like(pattern),
            )
        )

    schedule_id = _parse_optional_int(selected_filters['run_schedule'])
    if schedule_id is not None:
        statement = statement.where(ReportScheduleRun.schedule_id == schedule_id)

    trigger = selected_filters['run_trigger']
    if trigger:
        statement = statement.where(ReportScheduleRun.trigger_source == trigger)

    status = selected_filters['run_status']
    if status:
        statement = statement.where(ReportScheduleRun.status == status)

    period = selected_filters['run_period']
    if period in RUN_PERIOD_DELTAS:
        statement = statement.where(ReportScheduleRun.started_at >= datetime.now(UTC) - RUN_PERIOD_DELTAS[period])

    runs, pagination = paginate_select(
        db.session,
        statement,
        page=query_args.get('run_page', 1),
        per_page=query_args.get('run_per_page', PER_PAGE_OPTIONS[0]),
    )
    schedule_context_map = {
        int(item['id']): {
            'name': str(item['name']),
            'icon': str(item.get('report_icon') or 'calendar-clock'),
        }
        for item in schedules
        if item.get('id') is not None
    }
    return (
        [_serialize_run(item, schedule_context_map) for item in runs],
        pagination,
        selected_filters,
    )


def _get_run_selected_filters(query_args: Mapping[str, str]) -> dict[str, str]:
    period = str(query_args.get('run_period', '30d') or '30d').strip().lower()
    allowed_periods = {item['value'] for item in RUN_PERIOD_OPTIONS}
    if period not in allowed_periods:
        period = '30d'
    return {
        'run_search': str(query_args.get('run_search', '') or '').strip(),
        'run_schedule': str(query_args.get('run_schedule', '') or '').strip(),
        'run_trigger': str(query_args.get('run_trigger', '') or '').strip().lower(),
        'run_status': str(query_args.get('run_status', '') or '').strip().lower(),
        'run_period': period,
    }


def _get_run_filter_options(
    schedules: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    return {
        'schedules': [
            {'value': '', 'label': 'All Schedules'},
            *[
                {'value': str(item['id']), 'label': str(item['name'])}
                for item in sorted(schedules, key=lambda row: str(row['name']).casefold())
            ],
        ],
        'triggers': [
            {'value': '', 'label': 'All Triggers'},
            {'value': 'scheduler', 'label': 'Scheduler'},
            {'value': 'manual', 'label': 'Manual'},
        ],
        'statuses': [
            {'value': '', 'label': 'All Results'},
            {'value': 'queued', 'label': 'Queued'},
            {'value': 'started', 'label': 'Started'},
            {'value': 'success', 'label': 'Success'},
            {'value': 'failed', 'label': 'Failed'},
        ],
        'periods': list(RUN_PERIOD_OPTIONS),
    }


def _get_schedule_filter_options(
    schedules: list[dict[str, Any]],
    cluster_options: list[dict[str, str]],
    object_storage_system_options: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    delivery_catalog = _get_delivery_channel_options()
    asset_options: dict[str, str] = {
        f'{KUBERNETES_CLUSTER_ASSET_TYPE}:{item["value"]}': f'Kubernetes · {item["label"]}' for item in cluster_options
    }
    asset_options.update(
        {
            f'{OBJECT_STORAGE_SYSTEM_ASSET_TYPE}:{item["value"]}': f'Object Storage · {item["label"]}'
            for item in object_storage_system_options
        }
    )
    for schedule in schedules:
        key = str(schedule.get('scope_asset_filter_key') or '')
        if key and key not in asset_options:
            asset_options[key] = f'{schedule["scope_label"]} · {schedule["scope"]}'
    return {
        'statuses': [
            {'value': '', 'label': 'All Statuses'},
            {'value': 'active', 'label': 'Active'},
            {'value': 'paused', 'label': 'Paused'},
        ],
        'cadences': [
            {'value': '', 'label': 'All Cadences'},
            *[{'value': item['value'], 'label': item['label']} for item in CADENCE_OPTIONS],
        ],
        'report_types': [
            {'value': '', 'label': 'All Report Types'},
            *[{'value': item['value'], 'label': item['label']} for item in REPORT_TYPE_OPTIONS],
        ],
        'assets': [
            {'value': '', 'label': 'All Infrastructure Assets'},
            *[
                {'value': value, 'label': label}
                for value, label in sorted(asset_options.items(), key=lambda item: item[1].casefold())
            ],
        ],
        'deliveries': [
            {'value': '', 'label': 'All Delivery'},
            {'value': 'none', 'label': 'No Notification'},
            *[
                {'value': item['value'], 'label': item['label']}
                for item in delivery_catalog
                if item.get('selectable')
                or item.get('value')
                in {str(channel) for schedule in schedules for channel in schedule['notification_channel_ids']}
            ],
        ],
    }


def _get_schedule_rows() -> list[dict[str, Any]]:
    schedules = db.session.scalars(
        select(ReportSchedule).order_by(ReportSchedule.created_at.desc(), ReportSchedule.id.desc())
    ).all()
    cluster_map = _get_cluster_map([item.cluster_id for item in schedules if item.cluster_id])
    delivery_label_map = {
        int(item['channel_id']): f'{item["label"]} · {item["provider"]}' for item in _get_delivery_channel_options()
    }

    return [_serialize_schedule(item, cluster_map, delivery_label_map) for item in schedules]


def _get_recent_runs(limit: int = 8) -> list[dict[str, Any]]:
    runs = db.session.scalars(
        select(ReportScheduleRun)
        .order_by(ReportScheduleRun.started_at.desc(), ReportScheduleRun.id.desc())
        .limit(limit)
    ).all()
    schedule_context_map = _get_schedule_context_map([item.schedule_id for item in runs if item.schedule_id])

    return [_serialize_run(item, schedule_context_map) for item in runs]


def _get_storage_context() -> dict[str, Any]:
    try:
        backend_name = get_configured_storage_backend_name()
        status = get_report_storage_backend_status(backend_name)
        ready = bool(status.get('write_available', False))
        return {
            'backend': backend_name,
            'status': 'Ready' if ready else str(status.get('status') or 'Needs Review'),
            'tone': 'normal' if ready else 'warning',
            'description': str(status.get('description') or 'Report storage readiness could not be evaluated.'),
            'ready': ready,
            'state': str(status.get('state') or 'unknown'),
            'checked_at': status.get('checked_at'),
            'source': str(status.get('source') or 'direct'),
        }
    except Exception:
        return {
            'backend': 'unknown',
            'status': 'Needs Review',
            'tone': 'warning',
            'description': 'Storage readiness could not be evaluated. Review Reports Storage and server logs.',
            'ready': False,
            'state': 'unknown',
            'checked_at': None,
            'source': 'fallback',
        }
