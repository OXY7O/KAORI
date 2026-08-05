from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import abort, current_app
from sqlalchemy import Select, func, or_, select

from app.extensions.db import db
from app.jobs.presentation import present_job_execution
from app.models.job import JobExecution
from app.models.cluster import Cluster
from app.models.report import Report
from app.models.user import User
from app.reports.catalog import REPORT_TYPE_SPECS
from app.reports.export.artifacts import get_report_artifact_format
from app.reports.generate.service import REPORT_TYPE_OPTIONS
from app.reports.storage.service import (
    get_configured_storage_backend_name,
    parse_report_storage_uri,
    report_file_exists,
)

REPORT_TYPE_LABELS = {spec.value: spec.label for spec in REPORT_TYPE_SPECS}

STATUS_LABELS = {
    'requested': 'Requested',
    'queued': 'Queued',
    'generating': 'Generating',
    'ready': 'Ready',
    'failed': 'Failed',
    'archived': 'Archived',
}

STATUS_META = {
    'queued': {
        'label': 'Queued',
        'tone': 'blue',
        'icon': 'clock-3',
        'description': 'The report is waiting for the Reports worker.',
    },
    'requested': {
        'label': 'Requested',
        'tone': 'blue',
        'icon': 'send',
    },
    'generating': {
        'label': 'Generating',
        'tone': 'purple',
        'icon': 'loader-circle',
    },
    'ready': {
        'label': 'Ready',
        'tone': 'green',
        'icon': 'check-circle-2',
    },
    'failed': {
        'label': 'Failed',
        'tone': 'red',
        'icon': 'triangle-alert',
    },
    'archived': {
        'label': 'Archived',
        'tone': 'gray',
        'icon': 'archive',
    },
}

PENDING_STATUSES = [
    'requested',
    'generating',
]


def get_generated_reports_payload(
    query_args: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    selected_filters = get_selected_filters(
        query_args,
    )

    reports, total_items = get_reports(
        selected_filters,
    )

    summary_cards = get_summary_cards()
    unavailable_artifacts = sum(
        1
        for item in reports
        if item.get('file_path') and not bool(item.get('storage_reachable', True))
    )
    storage_notice = (
        f'{unavailable_artifacts} artifact(s) on this page could not be verified because the storage backend is unreachable. '
        'Report records remain available; download actions stay paused until connectivity returns.'
        if unavailable_artifacts
        else None
    )

    return {
        'page_title': 'Generated Reports',
        'page_subtitle': (
            'Review generated report records, artifact availability, and lifecycle actions.'
        ),
        'summary_cards': summary_cards,
        'filter_options': get_filter_options(),
        'selected_filters': selected_filters,
        'reports': reports,
        'pagination': get_pagination(
            selected_filters,
            total_items,
        ),
        'lifecycle_status': get_lifecycle_status(),
        'storage_context': get_storage_context(),
        'hero_posture': get_hero_posture(),
        'storage_notice': storage_notice,
    }


def get_report_detail_payload(
    report_id: int,
) -> dict[str, Any]:
    report = db.session.get(
        Report,
        report_id,
    )

    if report is None:
        abort(
            404,
        )

    cluster_map = _get_cluster_map(
        [
            report,
        ]
    )
    user_map = _get_user_map(
        [
            report,
        ]
    )

    report_detail = _serialize_report_detail(
        report,
        cluster_map,
        user_map,
    )
    artifact_access = report_detail['artifact_access']
    job = db.session.get(JobExecution, report.job_execution_id) if report.job_execution_id else None

    return {
        'page_title': 'Report Detail',
        'page_subtitle': 'Review report request metadata, selected sections, lifecycle status, and export readiness.',
        'report': report_detail,
        'job_execution': present_job_execution(job) if job else None,
        'status_context': get_report_detail_status_context(
            report.status,
        ),
        'export_readiness': get_report_detail_export_readiness(
            report,
            artifact_access,
        ),
        'storage_context': get_storage_context(
            artifact_access,
        ),
        'recommended_actions': get_report_detail_recommended_actions(
            report,
            artifact_access,
        ),
        'artifact_access_notice': get_report_artifact_access_notice(
            report,
            artifact_access,
        ),
    }


def get_hero_posture() -> list[dict[str, str]]:
    backend_name = _get_active_storage_backend_name()
    total_reports = _count_reports()
    ready_reports = _count_reports_by_status(
        [
            'ready',
        ]
    )
    missing_artifacts = _count_missing_artifacts()

    storage_label = 'S3-Compatible Storage' if backend_name == 's3' else 'Local Storage'
    storage_tone = 'green' if missing_artifacts == 0 else 'amber'
    storage_status = storage_label if missing_artifacts == 0 else 'Storage Review'

    return [
        {
            'label': 'Registry Posture',
            'value': 'Ready',
            'caption': f'{total_reports} report records tracked',
            'icon': 'database',
            'tone': 'blue',
        },
        {
            'label': 'Downloadable Artifacts',
            'value': str(ready_reports),
            'caption': 'Ready report artifacts',
            'icon': 'download',
            'tone': 'green',
        },
        {
            'label': 'Storage Backend',
            'value': storage_status,
            'caption': 'Active artifact backend',
            'icon': 'hard-drive',
            'tone': storage_tone,
        },
    ]


def get_summary_cards() -> list[dict[str, str]]:
    total_reports = _count_reports()
    ready_reports = _count_reports_by_status(
        [
            'ready',
        ]
    )
    pending_reports = _count_reports_by_status(
        PENDING_STATUSES,
    )
    failed_reports = _count_reports_by_status(
        [
            'failed',
        ]
    )

    return [
        {
            'label': 'Total Reports',
            'value': str(
                total_reports,
            ),
            'caption': 'All report request records',
            'icon': 'files',
            'tone': 'blue',
        },
        {
            'label': 'Ready Reports',
            'value': str(
                ready_reports,
            ),
            'caption': 'Reports available for download',
            'icon': 'check-circle-2',
            'tone': 'green',
        },
        {
            'label': 'Pending Reports',
            'value': str(
                pending_reports,
            ),
            'caption': 'Requested or generating reports',
            'icon': 'clock-3',
            'tone': 'purple',
        },
        {
            'label': 'Failed Reports',
            'value': str(
                failed_reports,
            ),
            'caption': 'Reports requiring review',
            'icon': 'triangle-alert',
            'tone': 'red',
        },
    ]


def get_filter_options() -> dict[str, list[dict[str, str]]]:
    return {
        'clusters': _get_cluster_options(),
        'report_types': [
            {
                'value': '',
                'label': 'All Types',
            },
            *[
                {
                    'value': str(item['value']),
                    'label': REPORT_TYPE_LABELS.get(
                        str(item['value']),
                        str(item['label']).removesuffix(' Report'),
                    ),
                }
                for item in REPORT_TYPE_OPTIONS
            ],
        ],
        'statuses': [
            {
                'value': '',
                'label': 'All Status',
            },
            {
                'value': 'requested',
                'label': 'Requested',
            },
            {
                'value': 'generating',
                'label': 'Generating',
            },
            {
                'value': 'ready',
                'label': 'Ready',
            },
            {
                'value': 'failed',
                'label': 'Failed',
            },
            {
                'value': 'archived',
                'label': 'Archived',
            },
        ],
        'periods': [
            {
                'value': 'snapshot',
                'label': 'Current Inventory Snapshot',
            },
            {
                'value': '30d',
                'label': 'Last 30 days',
            },
            {
                'value': '7d',
                'label': 'Last 7 days',
            },
            {
                'value': '90d',
                'label': 'Last 90 days',
            },
            {
                'value': 'month',
                'label': 'This month',
            },
            {
                'value': 'all',
                'label': 'All time',
            },
        ],
        'per_page_options': [
            {
                'value': '5',
                'label': '5',
            },
            {
                'value': '10',
                'label': '10',
            },
            {
                'value': '25',
                'label': '25',
            },
            {
                'value': '50',
                'label': '50',
            },
        ],
    }


def get_selected_filters(
    query_args: Mapping[str, str] | None = None,
) -> dict[str, str]:
    if query_args is None:
        query_args = {}

    return {
        'cluster_id': query_args.get(
            'cluster_id',
            '',
        ),
        'report_type': query_args.get(
            'report_type',
            '',
        ),
        'status': query_args.get(
            'status',
            '',
        ),
        'period': query_args.get(
            'period',
            '30d',
        ),
        'search': query_args.get(
            'search',
            '',
        ),
        'page': query_args.get(
            'page',
            '1',
        ),
        'per_page': query_args.get(
            'per_page',
            '5',
        ),
    }


def get_reports(
    selected_filters: dict[str, str],
) -> tuple[list[dict[str, Any]], int]:
    page = _safe_int(
        selected_filters.get(
            'page',
            '1',
        ),
        1,
    )
    per_page = _safe_int(
        selected_filters.get(
            'per_page',
            '5',
        ),
        5,
    )

    page = max(
        page,
        1,
    )
    per_page = min(
        max(
            per_page,
            1,
        ),
        100,
    )

    statement = select(
        Report,
    )

    statement = _apply_filters(
        statement,
        selected_filters,
    )

    total_items = (
        db.session.scalar(
            select(
                func.count(),
            ).select_from(
                statement.subquery(),
            )
        )
        or 0
    )

    statement = (
        statement.order_by(
            Report.created_at.desc(),
            Report.id.desc(),
        )
        .offset((page - 1) * per_page)
        .limit(
            per_page,
        )
    )

    report_items = (
        db.session.execute(
            statement,
        )
        .scalars()
        .all()
    )

    cluster_map = _get_cluster_map(
        report_items,
    )
    user_map = _get_user_map(
        report_items,
    )

    return [
        _serialize_report(
            report,
            cluster_map,
            user_map,
        )
        for report in report_items
    ], total_items


def get_pagination(
    selected_filters: dict[str, str],
    total_items: int,
) -> dict[str, int | str | bool]:
    page = _safe_int(
        selected_filters.get(
            'page',
            '1',
        ),
        1,
    )
    per_page = _safe_int(
        selected_filters.get(
            'per_page',
            '5',
        ),
        5,
    )

    page = max(
        page,
        1,
    )
    per_page = min(
        max(
            per_page,
            1,
        ),
        100,
    )

    total_pages = max(
        (total_items + per_page - 1) // per_page,
        1,
    )

    current_page = min(
        page,
        total_pages,
    )

    has_prev = current_page > 1
    has_next = current_page < total_pages

    start_item = 0 if total_items == 0 else ((current_page - 1) * per_page) + 1
    end_item = min(
        current_page * per_page,
        total_items,
    )

    return {
        'page': current_page,
        'total_pages': total_pages,
        'total_items': total_items,
        'per_page': per_page,
        'start_item': start_item,
        'end_item': end_item,
        'label': f'Showing {start_item} - {end_item} of {total_items} reports',
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_page': max(
            current_page - 1,
            1,
        ),
        'next_page': min(
            current_page + 1,
            total_pages,
        ),
    }


def get_lifecycle_status() -> list[dict[str, str]]:
    return [
        {
            'name': 'Requested',
            'description': 'Report request has been stored and is ready to be rendered into a downloadable report artifact.',
            'status': 'Queued',
            'tone': 'blue',
            'icon': 'send',
        },
        {
            'name': 'Generating',
            'description': 'The export engine is building the configured artifact and writing it to the configured storage backend.',
            'status': 'Rendering',
            'tone': 'purple',
            'icon': 'loader-circle',
        },
        {
            'name': 'Ready',
            'description': 'The generated report artifact is available for download and can be archived or regenerated when needed.',
            'status': 'Downloadable',
            'tone': 'green',
            'icon': 'check-circle-2',
        },
        {
            'name': 'Failed',
            'description': 'Generation failed. Open the report detail to inspect the error, then regenerate after correction.',
            'status': 'Action required',
            'tone': 'red',
            'icon': 'triangle-alert',
        },
        {
            'name': 'Archived',
            'description': 'Report is retained for operational history without deleting the stored artifact by default.',  # noqa: E501
            'status': 'Retention state',
            'tone': 'gray',
            'icon': 'archive',
        },
    ]


def get_storage_context(
    artifact_access: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    backend_name = _get_active_storage_backend_name()
    ready_reports = _count_reports_by_status(
        [
            'ready',
        ]
    )
    archived_reports = _count_reports_by_status(
        [
            'archived',
        ]
    )
    missing_artifacts = (
        _count_missing_artifacts()
        if artifact_access is None
        else 0
    )

    storage_tone = 'green'
    storage_status = 'Active'
    storage_description = (
        f'Generated report artifacts use the {backend_name.upper()} backend. '
        'Existing records keep their own backend prefix, so mixed local/S3 history remains readable.'
    )

    if artifact_access is not None and not bool(artifact_access.get('reachable', True)):
        storage_tone = 'amber'
        storage_status = 'Unavailable'
        storage_description = (
            f"KAORI could not reach {artifact_access.get('backend_label', 'Report Storage')} "
            'to verify this report artifact. The report record remains available for review.'
        )
    elif missing_artifacts > 0:
        storage_tone = 'amber'
        storage_status = 'Review needed'
        storage_description = (
            f'{missing_artifacts} ready or archived report artifact reference(s) are missing in configured storage. '
            'Open Reports Storage to run an integrity check.'
        )

    return [
        {
            'label': 'Active storage backend',
            'description': storage_description,
            'status': storage_status,
            'tone': storage_tone,
        },
        {
            'label': 'Download route active',
            'description': 'Ready and archived reports are downloadable when their storage artifact still exists.',
            'status': 'Ready',
            'tone': 'green',
        },
        {
            'label': 'Ready artifacts tracked',
            'description': f'{ready_reports} ready report record(s) are currently tracked for download.',
            'status': str(ready_reports),
            'tone': 'blue',
        },
        {
            'label': 'Archived artifacts tracked',
            'description': f'{archived_reports} archived report record(s) are retained for historical reference.',
            'status': str(archived_reports),
            'tone': 'gray',
        },
        {
            'label': 'Retention policy',
            'description': 'Retention cleanup is read-only by default. Archive and restore remain metadata operations unless destructive cleanup is explicitly enabled.',  # noqa: E501
            'status': 'Dry-run only',
            'tone': 'amber',
        },
    ]


def get_recommended_actions() -> list[dict[str, str]]:
    missing_artifacts = _count_missing_artifacts()

    actions = [
        {
            'label': 'Download ready reports',
            'description': 'Use Download for Ready or Archived records whose artifact is still available.',
            'href': '#reports-table',
        },
        {
            'label': 'Generate pending artifacts',
            'description': 'Generate the configured report artifact directly from the list or open a report detail for deeper review.',
            'href': '#reports-table',
        },
        {
            'label': 'Review failed reports',
            'description': 'Open failed reports to inspect error_message before regenerating.',
            'href': '#reports-table',
        },
        {
            'label': 'Run storage integrity check',
            'description': 'Open Reports Storage to verify database file_path references against local/S3 storage.',
            'href': '/reports/storage',
        },
        {
            'label': 'Generate a new report',
            'description': 'Create a new report request from the system report template catalog.',
            'href': '/reports/generate',
        },
    ]

    if missing_artifacts > 0:
        actions.insert(
            0,
            {
                'label': 'Resolve missing artifacts',
                'description': f'{missing_artifacts} report artifact reference(s) are missing. Regenerate affected reports or inspect storage integrity.',  # noqa: E501
                'href': '/reports/storage',
            },
        )

    return actions


def bulk_archive_report_records(
    report_ids: Sequence[int],
) -> tuple[bool, str]:
    normalized_ids = [int(report_id) for report_id in report_ids if str(report_id).isdigit()]

    if not normalized_ids:
        return False, 'Select at least one report to archive.'

    reports = (
        db.session.execute(
            select(
                Report,
            ).where(
                Report.id.in_(normalized_ids),
                Report.status.in_(
                    [
                        'requested',
                        'failed',
                        'ready',
                    ]
                ),
            )
        )
        .scalars()
        .all()
    )

    if not reports:
        return False, 'No selected reports can be archived.'

    now = datetime.now(
        UTC,
    )

    for report in reports:
        report.status = 'archived'
        report.updated_at = now

    db.session.commit()

    return True, f'Archived {len(reports)} report(s).'


def _apply_filters(
    statement: Select[tuple[Report]],
    selected_filters: dict[str, str],
) -> Select[tuple[Report]]:
    cluster_id = selected_filters.get(
        'cluster_id',
        '',
    )
    report_type = selected_filters.get(
        'report_type',
        '',
    )
    status = selected_filters.get(
        'status',
        '',
    )
    period = selected_filters.get(
        'period',
        '30d',
    )
    search = selected_filters.get(
        'search',
        '',
    ).strip()

    if cluster_id:
        statement = statement.where(
            Report.cluster_id == cluster_id,
        )

    if report_type:
        statement = statement.where(
            Report.report_type == report_type,
        )

    if status:
        statement = statement.where(
            Report.status == status,
        )

    if period != 'all':
        start_date = _get_period_start_date(
            period,
        )

        if start_date is not None:
            statement = statement.where(
                Report.created_at >= start_date,
            )

    if search:
        statement = statement.where(
            or_(
                Report.name.ilike(
                    f'%{search}%',
                ),
                Report.namespace.ilike(
                    f'%{search}%',
                ),
            )
        )

    return statement


def _get_period_start_date(
    period: str,
) -> datetime | None:
    now = datetime.now(
        UTC,
    )

    if period == '7d':
        return now - timedelta(
            days=7,
        )

    if period == '30d':
        return now - timedelta(
            days=30,
        )

    if period == '90d':
        return now - timedelta(
            days=90,
        )

    if period == 'month':
        return datetime(
            now.year,
            now.month,
            1,
            tzinfo=UTC,
        )

    return None


def _serialize_report(
    report: Report,
    cluster_map: dict[str, str],
    user_map: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    status_meta = _get_status_meta(
        report.status,
    )

    artifact_access = _probe_report_file(
        report.file_path,
    )
    file_exists = bool(artifact_access['exists'])

    file_state = _get_file_state(
        report,
        artifact_access,
    )
    storage_location = _parse_storage_location(
        report.file_path,
    )
    artifact_format = get_report_artifact_format(report.output_format)
    can_generate_artifact = report.status in ['requested', 'failed', 'ready']
    can_download_artifact = (
        report.status in ['ready', 'archived']
        and bool(report.file_path)
        and file_exists
    )

    return {
        'id': report.id,
        'name': report.name,
        'report_type': format_report_type(
            report.report_type,
        ),
        'raw_report_type': report.report_type,
        'report_domain': _format_report_domain(getattr(report, 'report_domain', 'kubernetes')),
        'source_kind': _format_source_kind(getattr(report, 'source_kind', 'kubernetes')),
        'source_badge': _format_source_badge(
            getattr(report, 'report_domain', 'kubernetes'),
            getattr(report, 'source_kind', 'kubernetes'),
        ),
        'cluster': cluster_map.get(
            report.cluster_id,
            'Unknown Cluster',
        )
        if report.cluster_id
        else 'Cluster Selection Missing',
        'cluster_id': report.cluster_id or '',
        'namespace': report.namespace or 'All Namespaces',
        'period': _format_period(
            report.period,
        ),
        'raw_period': report.period,
        'output_format': artifact_format.label,
        'raw_output_format': artifact_format.value,
        'artifact_label': artifact_format.label,
        'artifact_extension': artifact_format.extension,
        'artifact_mimetype': artifact_format.mimetype,
        'status': status_meta['label'],
        'raw_status': report.status,
        'status_meta': status_meta,
        'status_tone': status_meta['tone'],
        'status_icon': status_meta['icon'],
        'sections_count': len(
            report.sections_as_list(),
        ),
        'generated_by': _build_report_owner_label(
            report,
            user_map,
        )['label'],
        'generated_by_meta': _build_report_owner_label(
            report,
            user_map,
        ),
        'created_at': _format_datetime(
            report.created_at,
        ),
        'updated_at': _format_datetime(
            report.updated_at,
        ),
        'file_size': _format_file_size(
            report.file_size_bytes,
        ),
        'file_path': report.file_path or '',
        'file_exists': file_exists,
        'storage_reachable': bool(artifact_access['reachable']),
        'artifact_access': artifact_access,
        'file_state': file_state,
        'storage_backend': storage_location['backend'],
        'storage_backend_label': storage_location['backend_label'],
        'storage_object_key': storage_location['object_key'],
        'storage_uri_display': storage_location['display'],
        'can_generate_artifact': can_generate_artifact,
        'generate_artifact_label': (
            f'Regenerate {artifact_format.label}'
            if report.status == 'ready'
            else f'Generate {artifact_format.label}'
        ),
        'can_archive_report': report.status
        in [
            'requested',
            'failed',
            'ready',
        ],
        'can_restore_report': report.status == 'archived',
        'can_download_artifact': can_download_artifact,
    }


def _get_status_meta(
    status: str,
) -> dict[str, str]:
    default_meta = {
        'label': status.title(),
        'tone': 'gray',
        'icon': 'circle',
    }

    return STATUS_META.get(
        status,
        default_meta,
    )


def _serialize_report_detail(
    report: Report,
    cluster_map: dict[str, str],
    user_map: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    report_item = _serialize_report(
        report,
        cluster_map,
        user_map,
    )

    file_exists = bool(
        report_item['file_exists'],
    )

    return {
        **report_item,
        'namespace': report.namespace or 'All Namespaces',
        'raw_status': report.status,
        'raw_report_type': report.report_type,
        'report_domain': _format_report_domain(getattr(report, 'report_domain', 'kubernetes')),
        'source_kind': _format_source_kind(getattr(report, 'source_kind', 'kubernetes')),
        'source_badge': _format_source_badge(
            getattr(report, 'report_domain', 'kubernetes'),
            getattr(report, 'source_kind', 'kubernetes'),
        ),
        'raw_period': report.period,
        'sections': _format_sections(
            report.sections_as_list(),
        ),
        'sections_count': len(
            report.sections_as_list(),
        ),
        'file_path': report.file_path or 'Not generated yet',
        'file_size': _format_file_size(
            report.file_size_bytes,
        ),
        'file_exists': file_exists,
        'file_state': report_item['file_state'],
        'error_message': report.error_message or 'No error recorded',
        'updated_at': _format_datetime(
            report.updated_at,
        ),
        'can_generate_artifact': report_item['can_generate_artifact'],
        'can_archive_report': report.status
        in [
            'requested',
            'failed',
            'ready',
        ],
        'can_restore_report': report.status == 'archived',
        'can_download_artifact': report_item['can_download_artifact'],
    }


def get_report_detail_status_context(
    status: str,
) -> list[dict[str, str]]:
    status_map = {
        'requested': [
            {
                'label': 'Request stored',
                'description': 'The report request has been saved in the database.',
                'status': 'Done',
                'tone': 'blue',
                'icon': 'check-circle-2',
            },
            {
                'label': 'Artifact generation available',
                'description': 'Generate the configured PDF, Excel, or CSV artifact for this request.',
                'status': 'Ready to run',
                'tone': 'blue',
                'icon': 'file-text',
            },
            {
                'label': 'Download availability',
                'description': 'Download becomes active after artifact generation completes successfully.',
                'status': 'Waiting',
                'tone': 'amber',
                'icon': 'download',
            },
        ],
        'generating': [
            {
                'label': 'Generation running',
                'description': 'The configured artifact renderer is composing the requested output.',
                'status': 'Ready',
                'tone': 'purple',
                'icon': 'loader-circle',
            },
            {
                'label': 'Storage update pending',
                'description': 'file_path, file_size_bytes, and status will be updated after rendering completes.',
                'status': 'Waiting',
                'tone': 'amber',
                'icon': 'hard-drive',
            },
            {
                'label': 'Download availability',
                'description': 'Download will be enabled after the generated file is saved successfully.',
                'status': 'Waiting',
                'tone': 'amber',
                'icon': 'download',
            },
        ],
        'ready': [
            {
                'label': 'Report ready',
                'description': 'The report has been generated successfully.',
                'status': 'Ready',
                'tone': 'green',
                'icon': 'check-circle-2',
            },
            {
                'label': 'Download validation',
                'description': 'Download is active only when the generated artifact still exists in configured storage.',  # noqa: E501
                'status': 'Validated by file check',
                'tone': 'blue',
                'icon': 'search-check',
            },
            {
                'label': 'Storage metadata record',
                'description': 'The report record contains backend-aware storage URI and file size metadata for the generated artifact.',  # noqa: E501
                'status': 'Available',
                'tone': 'blue',
                'icon': 'hard-drive',
            },
            {
                'label': 'Regeneration supported',
                'description': 'Regenerate Artifact can recreate the file from the same report request.',
                'status': 'Available',
                'tone': 'blue',
                'icon': 'refresh-cw',
            },
        ],
        'failed': [
            {
                'label': 'Generation failed',
                'description': 'Artifact generation failed and the recorded error should be reviewed.',
                'status': 'Failed',
                'tone': 'red',
                'icon': 'triangle-alert',
            },
            {
                'label': 'Error message recorded',
                'description': 'The detail page keeps the latest error_message from the failed export attempt.',
                'status': 'Available',
                'tone': 'amber',
                'icon': 'bug',
            },
            {
                'label': 'Regeneration available',
                'description': 'After reviewing the error, retry artifact generation.',
                'status': 'Ready to retry',
                'tone': 'blue',
                'icon': 'refresh-cw',
            },
        ],
        'archived': [
            {
                'label': 'Archived report',
                'description': 'The report has been archived for retention or historical reference.',
                'status': 'Archived',
                'tone': 'gray',
                'icon': 'archive',
            },
            {
                'label': 'Historical artifact retained',
                'description': 'Archived reports keep storage metadata and remain downloadable when the generated artifact still exists.',  # noqa: E501
                'status': 'Storage dependent',
                'tone': 'gray',
                'icon': 'hard-drive',
            },
            {
                'label': 'Restore supported',
                'description': 'Restore Report can move this record back to Ready when the artifact is still available.',  # noqa: E501
                'status': 'Available',
                'tone': 'blue',
                'icon': 'rotate-ccw',
            },
        ],
    }

    return status_map.get(
        status,
        status_map['requested'],
    )


def get_report_detail_export_readiness(
    report: Report,
    artifact_access: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    artifact_format = get_report_artifact_format(report.output_format)
    access = dict(artifact_access or _probe_report_file(report.file_path))
    file_exists = bool(access.get('exists'))
    storage_reachable = bool(access.get('reachable', True))

    file_status = 'Not generated'
    file_tone = 'amber'
    file_description = (
        'Checks whether the file_path metadata still points to an existing report artifact in configured storage.'
    )

    if report.file_path and file_exists:
        file_status = 'Available'
        file_tone = 'blue'

    if report.file_path and storage_reachable and not file_exists:
        file_status = 'Missing file'
        file_tone = 'red'

    if report.file_path and not storage_reachable:
        file_status = 'Storage unavailable'
        file_tone = 'amber'
        file_description = (
            'KAORI could not verify the stored artifact because its storage backend is temporarily unavailable.'
        )

    download_status = 'Waiting'
    download_tone = 'amber'
    download_description = (
        'Download is enabled only for Ready reports with an existing generated artifact in configured storage.'
    )

    if report.status in ['ready', 'archived'] and report.file_path and file_exists:
        download_status = 'Ready'
        download_tone = 'green'

    if (
        report.status in ['ready', 'archived']
        and report.file_path
        and storage_reachable
        and not file_exists
    ):
        download_status = 'Blocked'
        download_tone = 'red'

    if report.status in ['ready', 'archived'] and report.file_path and not storage_reachable:
        download_status = 'Paused'
        download_tone = 'amber'
        download_description = (
            'Download is paused until KAORI can reach the artifact storage backend and verify the file.'
        )

    renderer_status = 'Available'
    renderer_tone = 'blue'

    if report.status == 'generating':
        renderer_status = 'Running'
        renderer_tone = 'purple'

    if report.status == 'failed':
        renderer_status = 'Failed'
        renderer_tone = 'red'

    renderer_context = {
        'pdf': (
            'Analytics PDF renderer',
            'The canonical WeasyPrint workflow renders the shared Analytics document model into PDF.',
        ),
        'xlsx': (
            'Inventory Excel renderer',
            'The reusable Inventory builder renders Inventory, Metadata, and Field Dictionary sheets into XLSX.',
        ),
        'csv': (
            'Canonical CSV renderer',
            'The CSV renderer exports the shared Analytics document model or Inventory profile without a parallel data contract.',
        ),
    }[artifact_format.value]

    return [
        {
            'label': 'Report request',
            'description': 'Metadata, scope, period, output format, and selected sections are persisted.',
            'status': 'Ready',
            'tone': 'blue',
        },
        {
            'label': renderer_context[0],
            'description': renderer_context[1],
            'status': renderer_status,
            'tone': renderer_tone,
        },
        {
            'label': 'Generated file',
            'description': file_description,
            'status': file_status,
            'tone': file_tone,
        },
        {
            'label': 'Download action',
            'description': download_description,
            'status': download_status,
            'tone': download_tone,
        },
    ]


def get_report_detail_recommended_actions(
    report: Report,
    artifact_access: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    storage_href = '/reports/storage'
    generated_href = '/reports/generated'
    generate_href = f'/reports/generate?report_type={report.report_type}'

    artifact_format = get_report_artifact_format(report.output_format)
    access = dict(artifact_access or _probe_report_file(report.file_path))
    file_exists = bool(access.get('exists'))
    storage_reachable = bool(access.get('reachable', True))

    if report.status == 'ready':
        actions = [
            {
                'label': 'Review artifact metadata',
                'description': 'Confirm backend, object key, file size, and availability in the Artifact Output section.',  # noqa: E501
                'href': '#file-output',
            },
            {
                'label': 'Regenerate from current request',
                'description': 'Use Regenerate Artifact in the action bar when the stored artifact needs to be refreshed.',  # noqa: E501
                'href': '#report-actions',
            },
            {
                'label': 'Run storage integrity check',
                'description': 'Open Reports Storage to validate artifact references across local/S3 backends.',
                'href': storage_href,
            },
        ]

        if report.file_path and not storage_reachable:
            actions.insert(
                0,
                {
                    'label': 'Review Report Storage',
                    'description': (
                        'KAORI could not verify this artifact. Restore storage connectivity, run a storage check, and then retry.'
                    ),
                    'href': storage_href,
                },
            )
        elif file_exists:
            actions.insert(
                0,
                {
                    'label': f'Download {artifact_format.label}',
                    'description': 'Download the verified report artifact from configured storage.',
                    'href': f'/reports/generated/{report.id}/download-artifact',
                },
            )
        elif not file_exists:
            actions.insert(
                0,
                {
                    'label': 'Recreate missing artifact',
                    'description': 'This Ready report no longer has a reachable artifact. Regenerate it before downloading.',  # noqa: E501
                    'href': '#report-actions',
                },
            )

        return actions

    if report.status == 'failed':
        return [
            {
                'label': 'Review failure reason',
                'description': 'Check the recorded error message before retrying artifact generation.',
                'href': '#status',
            },
            {
                'label': f'Retry {artifact_format.label} generation',
                'description': 'Generate the artifact again after fixing the cause of the failure.',
                'href': '#report-actions',
            },
            {
                'label': 'Confirm storage backend',
                'description': 'Verify the configured report storage backend is reachable and writable by the application.',  # noqa: E501
                'href': storage_href,
            },
            {
                'label': 'Create a fresh report request',
                'description': 'Generate a new request from the same report type if this record should not be reused.',
                'href': generate_href,
            },
        ]

    if report.status == 'generating':
        return [
            {
                'label': 'Wait for export completion',
                'description': 'The report is currently being rendered and will become downloadable after completion.',
                'href': '#status',
            },
            {
                'label': 'Refresh report detail',
                'description': 'Reload this detail page after the export process completes.',
                'href': f'/reports/generated/{report.id}',
            },
            {
                'label': 'Review generated reports list',
                'description': 'Return to the generated reports list to monitor lifecycle state across reports.',
                'href': generated_href,
            },
        ]

    if report.status == 'archived':
        actions = [
            {
                'label': 'Download archived artifact',
                'description': 'Download remains available when the archived report artifact exists in configured storage.',  # noqa: E501
                'href': f'/reports/generated/{report.id}/download-artifact' if file_exists else '#file-output',
            },
            {
                'label': 'Restore report if needed',
                'description': 'Use Restore Report to move this record back to Ready when the artifact is still available.',  # noqa: E501
                'href': '#report-actions',
            },
            {
                'label': 'Review archive state',
                'description': 'Confirm whether the archived report still has a valid generated file in configured storage.',  # noqa: E501
                'href': '#file-output',
            },
            {
                'label': 'Check retention policy',
                'description': 'Open Reports Storage to inspect current read-only retention and cleanup policy status.',
                'href': storage_href,
            },
        ]

        if not file_exists:
            actions.insert(
                0,
                {
                    'label': 'Archived artifact missing',
                    'description': 'Restore is blocked until the artifact is regenerated or recovered.',  # noqa: E501
                    'href': '#file-output',
                },
            )

        return actions

    return [
        {
            'label': 'Generate Artifact',
            'description': 'Render this stored report request into its configured downloadable artifact.',
            'href': '#report-actions',
        },
        {
            'label': 'Review selected sections',
            'description': 'Confirm the report request contains the required operational sections before generation.',
            'href': '#sections',
        },
        {
            'label': 'Confirm report scope',
            'description': 'Check cluster, namespace, period, and output format metadata.',
            'href': '#metadata',
        },
        {
            'label': 'Review storage settings',
            'description': 'Open Reports Storage before generation if artifact backend configuration needs review.',
            'href': storage_href,
        },
    ]


def archive_report_record(
    report_id: int,
) -> tuple[bool, str]:
    report = db.session.get(
        Report,
        report_id,
    )

    if report is None:
        return False, 'Report not found.'

    if report.status == 'generating':
        return False, 'Report is currently generating and cannot be archived.'

    if report.status == 'archived':
        return True, 'Report is already archived.'

    report.status = 'archived'
    db.session.commit()

    return True, 'Report archived successfully. Stored artifact metadata was retained.'


def restore_archived_report_record(
    report_id: int,
) -> tuple[bool, str]:
    report = db.session.get(
        Report,
        report_id,
    )

    if report is None:
        return False, 'Report not found.'

    if report.status != 'archived':
        return False, 'Only archived reports can be restored.'

    if not report.file_path:
        return False, 'Archived report has no storage metadata. Regenerate the artifact instead.'

    if not _report_file_exists(
        report.file_path,
    ):
        return False, 'Archived report artifact is missing in configured storage. Regenerate the artifact instead.'

    report.status = 'ready'
    db.session.commit()

    return True, 'Archived report restored successfully.'


def _format_sections(
    sections: list[str],
) -> list[dict[str, str]]:
    section_label_map = {option['value']: option['label'] for option in _get_known_section_options()}

    return [
        {
            'value': section,
            'label': section_label_map.get(
                section,
                section.replace(
                    '_',
                    ' ',
                ).title(),
            ),
        }
        for section in sections
    ]


def _get_known_section_options() -> list[dict[str, str]]:
    return [
        {
            'value': 'executive_summary',
            'label': 'Executive Summary',
        },
        {
            'value': 'analytics_summary',
            'label': 'Analytics Summary',
        },
        {
            'value': 'resource_snapshot',
            'label': 'Resource Snapshot',
        },
        {
            'value': 'cpu_utilization',
            'label': 'CPU Utilization',
        },
        {
            'value': 'memory_utilization',
            'label': 'Memory Utilization',
        },
        {
            'value': 'storage_utilization',
            'label': 'Storage Utilization',
        },
        {
            'value': 'pod_utilization',
            'label': 'Pod Utilization',
        },
        {
            'value': 'node_resource_detail',
            'label': 'Node Resource Detail',
        },
        {
            'value': 'worker_capacity_summary',
            'label': 'Worker Capacity Summary',
        },
        {
            'value': 'resource_allocation_headroom',
            'label': 'Resource Allocation & Headroom',
        },
        {
            'value': 'capacity_pressure_risk',
            'label': 'Capacity & Pressure Risk',
        },
        {
            'value': 'storage_capacity',
            'label': 'Storage Capacity',
        },
        {
            'value': 'filesystem_summary',
            'label': 'Filesystem Summary',
        },
        {
            'value': 'persistent_volume_summary',
            'label': 'Persistent Volume Summary',
        },
        {
            'value': 'persistent_volume_claims',
            'label': 'Persistent Volume Claims',
        },
        {
            'value': 'tenant_quota',
            'label': 'Tenant Quota',
        },
        {
            'value': 'tenant_quota_summary',
            'label': 'Tenant Quota Summary',
        },
        {
            'value': 'workload_resource_mapping',
            'label': 'Workload Resource Mapping',
        },
        {
            'value': 'request_limit_coverage',
            'label': 'Request & Limit Coverage',
        },
        {
            'value': 'namespace_breakdown',
            'label': 'Namespace Breakdown',
        },
        {
            'value': 'forecast_summary',
            'label': 'Forecast Summary',
        },
        {
            'value': 'cpu_forecast',
            'label': 'CPU Forecast',
        },
        {
            'value': 'memory_forecast',
            'label': 'Memory Forecast',
        },
        {
            'value': 'storage_forecast',
            'label': 'Storage Forecast',
        },
        {
            'value': 'pod_forecast',
            'label': 'Pod Forecast',
        },
        {
            'value': 'capacity_projection',
            'label': 'Capacity Projection',
        },
        {
            'value': 'top_namespace_consumers',
            'label': 'Top Namespace Consumers',
        },
        {
            'value': 'top_workload_consumers',
            'label': 'Top Workload Consumers',
        },
        {
            'value': 'top_pod_consumers',
            'label': 'Top Pod Consumers',
        },
        {
            'value': 'resource_hotspots',
            'label': 'Resource Hotspots',
        },
        {
            'value': 'active_alerts',
            'label': 'Active Alerts',
        },
        {
            'value': 'alert_severity_summary',
            'label': 'Alert Severity Summary',
        },
        {
            'value': 'anomaly_context',
            'label': 'Anomaly Context',
        },
        {
            'value': 'affected_resources',
            'label': 'Affected Resources',
        },
        {
            'value': 'storage_risk',
            'label': 'Storage Risk',
        },
        {
            'value': 'risk_overview',
            'label': 'Risk Overview',
        },
        {
            'value': 'operational_recommendations',
            'label': 'Operational Recommendations',
        },
    ]


def format_report_type(
    value: str,
) -> str:
    return REPORT_TYPE_LABELS.get(
        value,
        value.replace(
            '_',
            ' ',
        ).title(),
    )


def _format_file_size(
    value: int | None,
) -> str:
    if value is None:
        return 'Not available'

    if value < 1024:
        return f'{value} B'

    if value < 1024 * 1024:
        return f'{value / 1024:.2f} KB'

    return f'{value / (1024 * 1024):.2f} MB'


def _get_active_storage_backend_name() -> str:
    try:
        return get_configured_storage_backend_name()
    except Exception:
        return 'local'


def _parse_storage_location(
    file_path: str | None,
) -> dict[str, str]:
    if not file_path:
        return {
            'backend': 'none',
            'backend_label': 'Not generated',
            'object_key': '',
            'display': 'Not generated yet',
        }

    value = str(
        file_path,
    ).strip()

    if ':' not in value:
        return {
            'backend': 'invalid',
            'backend_label': 'Invalid Storage URI',
            'object_key': value,
            'display': value,
        }

    backend, object_key = value.split(
        ':',
        1,
    )
    backend = backend.lower().strip()
    object_key = object_key.strip().lstrip('/')

    backend_labels = {
        'local': 'Local Filesystem',
        's3': 'S3-compatible Storage',
    }

    return {
        'backend': backend or 'invalid',
        'backend_label': backend_labels.get(
            backend,
            backend.replace(
                '-',
                ' ',
            ).title()
            if backend
            else 'Invalid Storage URI',
        ),
        'object_key': object_key or value,
        'display': value,
    }


def _count_missing_artifacts() -> int:
    candidate_reports = (
        db.session.execute(
            select(
                Report,
            ).where(
                Report.status.in_(
                    [
                        'ready',
                        'archived',
                    ]
                )
            )
        )
        .scalars()
        .all()
    )

    missing_count = 0

    for report in candidate_reports:
        if not report.file_path:
            missing_count += 1
            continue

        if not _report_file_exists(
            report.file_path,
        ):
            missing_count += 1

    return missing_count


def _report_file_exists(
    file_path: str | None,
) -> bool:
    return bool(
        _probe_report_file(
            file_path,
        )['exists']
    )


def _probe_report_file(
    file_path: str | None,
) -> dict[str, Any]:
    if not file_path:
        return {
            'exists': False,
            'reachable': True,
            'backend': 'none',
            'backend_label': 'Report Storage',
            'state': 'not_generated',
        }

    backend_name = 'unknown'

    try:
        backend_name, _object_key = parse_report_storage_uri(
            file_path,
        )
        file_exists = report_file_exists(
            file_path,
        )
    except Exception:  # External storage failures must not break report detail rendering.
        current_app.logger.warning(
            'Unable to verify generated report artifact in storage backend.',
            exc_info=True,
        )
        return {
            'exists': False,
            'reachable': False,
            'backend': backend_name,
            'backend_label': _format_storage_backend_label(backend_name),
            'state': 'unavailable',
        }

    return {
        'exists': bool(file_exists),
        'reachable': True,
        'backend': backend_name,
        'backend_label': _format_storage_backend_label(backend_name),
        'state': 'available' if file_exists else 'missing',
    }


def _format_storage_backend_label(
    backend_name: str,
) -> str:
    normalized_backend = str(backend_name or '').lower().strip()

    if normalized_backend == 's3':
        return 'S3-Compatible Storage'

    if normalized_backend == 'local':
        return 'Local Storage'

    return 'Report Storage'


def get_report_artifact_access_notice(
    report: Report,
    artifact_access: Mapping[str, Any],
) -> dict[str, str] | None:
    if not report.file_path or bool(artifact_access.get('reachable', True)):
        return None

    backend_label = str(
        artifact_access.get('backend_label')
        or 'Report Storage'
    )

    return {
        'title': 'Artifact Storage Is Temporarily Unavailable',
        'description': (
            f'KAORI loaded the report record, but could not verify its artifact in {backend_label}. '
            'Download is paused to avoid a failed request. Restore storage connectivity or review Reports Storage, then retry.'
        ),
        'action_label': 'Review Report Storage',
        'action_href': '/reports/storage',
        'icon': 'cloud-off',
    }


def _get_file_state(
    report: Report,
    artifact_access: Mapping[str, Any],
) -> dict[str, str]:
    file_exists = bool(artifact_access.get('exists'))
    storage_reachable = bool(artifact_access.get('reachable', True))

    if report.file_path and not storage_reachable:
        return {
            'label': 'Storage unavailable',
            'description': (
                'KAORI could not verify this report artifact because its storage backend is temporarily unavailable.'
            ),
            'tone': 'amber',
            'icon': 'cloud-off',
        }

    if report.status == 'ready' and report.file_path and file_exists:
        return {
            'label': 'Available',
            'description': 'Generated report artifact exists in configured storage.',
            'tone': 'green',
            'icon': 'check-circle-2',
        }

    if report.status == 'ready' and report.file_path and not file_exists:
        return {
            'label': 'Missing file',
            'description': 'Report is Ready, but the generated report artifact no longer exists in configured storage.',
            'tone': 'red',
            'icon': 'triangle-alert',
        }

    if report.status == 'ready' and not report.file_path:
        return {
            'label': 'File path missing',
            'description': 'Report is Ready, but file_path metadata is empty.',
            'tone': 'red',
            'icon': 'triangle-alert',
        }

    if report.status == 'archived' and report.file_path and file_exists:
        return {
            'label': 'Archived artifact',
            'description': 'Archived report artifact exists in configured storage and remains downloadable for historical reference.',  # noqa: E501
            'tone': 'gray',
            'icon': 'archive',
        }

    if report.status == 'archived' and report.file_path and not file_exists:
        return {
            'label': 'Archived missing',
            'description': 'Archived report has storage metadata, but the generated artifact is missing in configured storage.',  # noqa: E501
            'tone': 'red',
            'icon': 'triangle-alert',
        }

    if report.status == 'archived' and not report.file_path:
        return {
            'label': 'Archived without artifact',
            'description': 'Archived report does not have generated artifact metadata.',
            'tone': 'gray',
            'icon': 'archive',
        }

    if report.status == 'generating':
        return {
            'label': 'Generating',
            'description': 'Report artifact is being generated.',
            'tone': 'purple',
            'icon': 'loader-circle',
        }

    if report.status == 'failed':
        return {
            'label': 'Not available',
            'description': 'Generated artifact is not available because generation failed.',
            'tone': 'red',
            'icon': 'triangle-alert',
        }

    return {
        'label': 'Not generated',
        'description': 'Generated artifact has not been created yet.',
        'tone': 'amber',
        'icon': 'clock-3',
    }


def _get_cluster_options() -> list[dict[str, str]]:
    clusters = (
        db.session.execute(
            select(
                Cluster,
            ).order_by(
                Cluster.name.asc(),
            )
        )
        .scalars()
        .all()
    )

    options = [
        {
            'value': '',
            'label': 'Any Cluster',
        },
    ]

    for cluster in clusters:
        options.append(
            {
                'value': str(
                    cluster.id,
                ),
                'label': cluster.name,
            }
        )

    return options


def _get_cluster_map(
    reports: Sequence[Report],
) -> dict[str, str]:
    cluster_ids = {
        str(
            report.cluster_id,
        )
        for report in reports
        if report.cluster_id is not None
    }

    if not cluster_ids:
        return {}

    clusters = (
        db.session.execute(
            select(
                Cluster,
            ).where(
                Cluster.id.in_(
                    cluster_ids,
                )
            )
        )
        .scalars()
        .all()
    )

    return {
        str(
            cluster.id,
        ): cluster.name
        for cluster in clusters
    }


def _get_user_map(
    reports: Sequence[Report],
) -> dict[int, dict[str, Any]]:
    user_ids = {report.generated_by_id for report in reports if report.generated_by_id is not None}

    if not user_ids:
        return {}

    users = (
        db.session.execute(
            select(
                User,
            ).where(
                User.id.in_(
                    user_ids,
                )
            )
        )
        .scalars()
        .all()
    )

    return {
        user.id: {
            'label': user.display_label,
            'username': user.username,
            'auth_source': user.auth_source,
            'is_deleted': user.deleted_at is not None,
            'is_inactive': not user.account_is_active and user.deleted_at is None,
            'status_label': _get_user_status_label(
                user,
            ),
            'status_tone': _get_user_status_tone(
                user,
            ),
        }
        for user in users
    }


def _build_report_owner_label(
    report: Report,
    user_map: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    if report.generated_by_id is None:
        return {
            'label': report.generated_by_display_name_snapshot or report.generated_by_username_snapshot or 'System',
            'username': report.generated_by_username_snapshot or 'system',
            'auth_source': report.generated_by_auth_source_snapshot or 'system',
            'status_label': 'System',
            'status_tone': 'slate',
            'is_deleted': False,
            'is_inactive': False,
            'is_missing': False,
        }

    user_meta = user_map.get(
        report.generated_by_id,
    )

    if user_meta:
        return user_meta

    return {
        'label': report.generated_by_display_name_snapshot or report.generated_by_username_snapshot or 'Unknown user',
        'username': report.generated_by_username_snapshot or 'unknown',
        'auth_source': report.generated_by_auth_source_snapshot or 'unknown',
        'status_label': 'User record unavailable',
        'status_tone': 'amber',
        'is_deleted': False,
        'is_inactive': False,
        'is_missing': True,
    }


def _get_user_status_label(
    user: User,
) -> str:
    if user.deleted_at is not None:
        return 'Deleted user'

    if not user.account_is_active:
        return 'Inactive user'

    return 'Active user'


def _get_user_status_tone(
    user: User,
) -> str:
    if user.deleted_at is not None:
        return 'rose'

    if not user.account_is_active:
        return 'amber'

    return 'emerald'


def _count_reports() -> int:
    return (
        db.session.scalar(
            select(
                func.count(
                    Report.id,
                )
            )
        )
        or 0
    )


def _count_reports_by_status(
    statuses: list[str],
) -> int:
    return (
        db.session.scalar(
            select(
                func.count(
                    Report.id,
                )
            ).where(
                Report.status.in_(
                    statuses,
                )
            )
        )
        or 0
    )


def _format_report_domain(
    report_domain: str | None,
) -> str:
    labels = {
        'kubernetes': 'KAORI Kubernetes Reports',
        'server': 'KAORI Server Reports',
        'hci': 'KAORI HCI Reports',
    }
    normalized = str(report_domain or 'kubernetes').strip().lower()
    return labels.get(normalized, normalized.replace('_', ' ').title())


def _format_source_badge(
    report_domain: str | None,
    source_kind: str | None,
) -> str:
    normalized_domain = str(report_domain or 'kubernetes').strip().lower()
    if normalized_domain == 'server':
        return 'Server'
    if normalized_domain == 'hci':
        return 'HCI'

    if (source_kind or 'kubernetes') == 'kubernetes':
        return 'Kubernetes'

    return _format_source_kind(source_kind)


def _format_source_kind(
    source_kind: str | None,
) -> str:
    labels = {
        'kubernetes': 'Kubernetes',
        'server': 'Server',
        'vm': 'VM',
        'hci': 'HCI',
    }

    return labels.get(
        source_kind or 'kubernetes',
        (source_kind or 'kubernetes')
        .replace(
            '_',
            ' ',
        )
        .title(),
    )


def _format_period(
    value: str,
) -> str:
    labels = {
        'snapshot': 'Current Inventory Snapshot',
        '24h': 'Last 24 hours',
        '7d': 'Last 7 days',
        '30d': 'Last 30 days',
        '90d': 'Last 90 days',
        'month': 'This month',
    }

    return labels.get(
        value,
        value,
    )


def _format_datetime(
    value: datetime | None,
) -> str:
    if value is None:
        return '-'

    return value.strftime(
        '%d %b %Y %H:%M',
    )


def _safe_int(
    value: str,
    default: int,
) -> int:
    try:
        return int(
            value,
        )
    except ValueError:
        return default
