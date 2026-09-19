from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import abort
from sqlalchemy import (
    Select,
    and_,
    func,
    or_,
    select,
)

from app.common.job_execution_presentation import present_job_execution
from app.common.pagination import (
    PER_PAGE_OPTIONS,
    build_pagination_window,
    normalize_per_page,
    positive_int,
)
from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.job import JobExecution
from app.models.object_storage import ObjectStorageSystem
from app.models.report import Report
from app.models.user import User
from app.reports.catalog import REPORT_TYPE_SPECS
from app.reports.export.artifacts import get_report_artifact_format
from app.reports.generate.service import REPORT_TYPE_OPTIONS
from app.reports.scope import (
    KUBERNETES_CLUSTER_ASSET_TYPE,
    OBJECT_STORAGE_SYSTEM_ASSET_TYPE,
    resolve_report_scope,
)
from app.reports.storage.service import (
    get_configured_storage_backend_name,
    get_report_storage_backend_status,
    probe_report_artifact,
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
    'queued',
    'generating',
]

ARCHIVABLE_STATUSES = (
    'requested',
    'failed',
    'ready',
)


def get_generated_reports_payload(
    query_args: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    backend_status = get_report_storage_backend_status()
    selected_filters = get_selected_filters(
        query_args,
    )

    reports, total_items = get_reports(
        selected_filters,
        backend_status=backend_status,
    )

    focus_report_id = _safe_int(selected_filters.get('focus', ''), 0)
    for item in reports:
        item['is_focused'] = bool(focus_report_id and item['id'] == focus_report_id)

    summary_cards = get_summary_cards()
    has_pending_reports = _has_pending_reports_for_filters(selected_filters)
    unavailable_artifacts = sum(
        1 for item in reports if item.get('file_path') and not bool(item.get('storage_reachable', True))
    )
    if not bool(backend_status.get('available', False)):
        storage_notice = str(backend_status.get('description') or '').strip() or (
            'Report storage needs review. Report records remain available while storage-dependent operations follow '
            'the active backend readiness state.'
        )
    elif unavailable_artifacts:
        storage_notice = (
            f'{unavailable_artifacts} artifact(s) on this page could not be verified because '
            'their storage backend is unreachable. Report records remain available; download '
            'actions stay paused until connectivity returns.'
        )
    else:
        storage_notice = None

    return {
        'page_title': 'Generated Reports',
        'page_subtitle': (
            'Review PDF publications, XLSX analytical workbooks, and CSV exports across worker execution, artifact '
            'readiness, storage availability, and lifecycle state from generation through retention.'
        ),
        'summary_cards': summary_cards,
        'filter_options': get_filter_options(),
        'selected_filters': selected_filters,
        'active_filter_count': get_active_filter_count(selected_filters),
        'reports': reports,
        'pagination': get_pagination(
            selected_filters,
            total_items,
        ),
        'backend_status': backend_status,
        'storage_notice': storage_notice,
        'focus_report_id': focus_report_id,
        'has_pending_reports': has_pending_reports,
        'poll_interval_seconds': 8,
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
    job_execution = present_job_execution(job) if job else None
    should_poll = report.status in PENDING_STATUSES or bool(job_execution and job_execution['is_active'])

    return {
        'page_title': 'Report Detail',
        'page_subtitle': 'Review report request metadata, selected sections, lifecycle status, retained artifact evidence, and export readiness from one record.',
        'report': report_detail,
        'job_execution': job_execution,
        'artifact_access_notice': get_report_artifact_access_notice(
            report,
            artifact_access,
        ),
        'poll_interval_seconds': 8 if should_poll else None,
    }


def get_summary_cards() -> list[dict[str, str]]:
    status_counts = _get_report_status_counts()
    total_reports = sum(status_counts.values())
    ready_reports = status_counts.get('ready', 0)
    pending_reports = sum(status_counts.get(status, 0) for status in PENDING_STATUSES)
    failed_reports = status_counts.get('failed', 0)

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
            'caption': 'Reports in Ready lifecycle state',
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
        'scopes': _get_scope_options(),
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
                'value': 'queued',
                'label': 'Queued',
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
        'output_formats': [
            {
                'value': '',
                'label': 'All Formats',
            },
            {
                'value': 'pdf',
                'label': 'PDF',
            },
            {
                'value': 'csv',
                'label': 'CSV',
            },
            {
                'value': 'xlsx',
                'label': 'XLSX',
            },
        ],
        'periods': [
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
                'value': str(option),
                'label': str(option),
            }
            for option in PER_PAGE_OPTIONS
        ],
    }


def get_selected_filters(
    query_args: Mapping[str, str] | None = None,
) -> dict[str, str]:
    if query_args is None:
        query_args = {}

    scope = str(query_args.get('scope', '') or '').strip()
    legacy_cluster_id = str(query_args.get('cluster_id', '') or '').strip()
    if not scope and legacy_cluster_id:
        scope = f'{KUBERNETES_CLUSTER_ASSET_TYPE}:{legacy_cluster_id}'

    return {
        'scope': scope,
        'report_type': query_args.get(
            'report_type',
            '',
        ),
        'status': query_args.get(
            'status',
            '',
        ),
        'output_format': query_args.get(
            'output_format',
            '',
        ),
        'period': query_args.get(
            'period',
            '30d',
        ),
        'focus': query_args.get(
            'focus',
            '',
        ),
        'search': query_args.get(
            'search',
            '',
        ),
        'page': str(positive_int(query_args.get('page'), 1)),
        'per_page': str(normalize_per_page(query_args.get('per_page'))),
    }


def get_active_filter_count(selected_filters: Mapping[str, str]) -> int:
    filter_keys = {'scope', 'report_type', 'status', 'output_format', 'search'}
    active_count = sum(1 for key in filter_keys if str(selected_filters.get(key, '') or '').strip())
    return active_count + int(str(selected_filters.get('period', '30d') or '30d') != '30d')


def get_reports(
    selected_filters: dict[str, str],
    *,
    backend_status: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], int]:
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

    pagination = build_pagination_window(
        total_items=total_items,
        page=selected_filters.get('page'),
        per_page=selected_filters.get('per_page'),
    )

    statement = (
        statement.order_by(
            Report.created_at.desc(),
            Report.id.desc(),
        )
        .offset(pagination.offset)
        .limit(pagination.per_page)
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
            verify_artifact=False,
            active_backend_status=backend_status,
        )
        for report in report_items
    ], total_items


def _has_pending_reports_for_filters(selected_filters: dict[str, str]) -> bool:
    selected_status = selected_filters.get('status', '')
    if selected_status and selected_status not in PENDING_STATUSES:
        return False

    pending_filters = dict(selected_filters)
    pending_filters['status'] = selected_status if selected_status in PENDING_STATUSES else ''
    statement = _apply_filters(select(Report), pending_filters).where(Report.status.in_(PENDING_STATUSES)).limit(1)
    return db.session.execute(statement).first() is not None


def get_pagination(
    selected_filters: dict[str, str],
    total_items: int,
) -> dict[str, Any]:
    pagination = build_pagination_window(
        total_items=total_items,
        page=selected_filters.get('page'),
        per_page=selected_filters.get('per_page'),
    )

    return {
        **pagination.as_dict(),
        'per_page_options': list(PER_PAGE_OPTIONS),
        'label': (f'Showing {pagination.start_item}–{pagination.end_item} of {pagination.total_items} Reports'),
    }


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
                Report.status.in_(ARCHIVABLE_STATUSES),
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
    scope = selected_filters.get('scope', '')
    report_type = selected_filters.get(
        'report_type',
        '',
    )
    status = selected_filters.get(
        'status',
        '',
    )
    output_format = selected_filters.get(
        'output_format',
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

    if scope:
        asset_type, separator, asset_id = scope.partition(':')
        if separator and asset_id:
            if asset_type == KUBERNETES_CLUSTER_ASSET_TYPE:
                statement = statement.where(
                    or_(
                        and_(
                            Report.scope_asset_type == KUBERNETES_CLUSTER_ASSET_TYPE,
                            Report.scope_asset_id == asset_id,
                        ),
                        and_(
                            Report.scope_asset_type.is_(None),
                            Report.cluster_id == asset_id,
                        ),
                    )
                )
            else:
                statement = statement.where(
                    Report.scope_asset_type == asset_type,
                    Report.scope_asset_id == asset_id,
                )

    if report_type:
        statement = statement.where(
            Report.report_type == report_type,
        )

    if status:
        statement = statement.where(
            Report.status == status,
        )

    if output_format:
        statement = statement.where(
            Report.output_format == output_format,
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
                Report.scope_asset_label_snapshot.ilike(
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
    *,
    verify_artifact: bool = True,
    active_backend_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status_meta = _get_status_meta(
        report.status,
    )

    artifact_access = (
        _probe_report_file(report.file_path)
        if verify_artifact
        else _summarize_report_file_reference(
            report.file_path,
            active_backend_status=active_backend_status,
        )
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
    active_backend_status = dict(active_backend_status or get_report_storage_backend_status())
    can_generate_artifact = report.status in ['requested', 'failed', 'ready'] and bool(
        active_backend_status.get('write_available', False)
    )
    can_download_artifact = report.status in ['ready', 'archived'] and bool(report.file_path) and file_exists
    scope = resolve_report_scope(report)
    scope_asset_type = str(getattr(report, 'scope_asset_type', '') or '')
    scope_label = (
        'Object Storage System' if scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE else 'Kubernetes Cluster'
    )
    scope_value = (
        scope.label
        if scope is not None
        else (getattr(report, 'scope_asset_label_snapshot', None) or 'Asset Selection Missing')
    )
    secondary_scope = (
        'System Scope'
        if scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE
        else (report.namespace or 'All Namespaces')
    )

    return {
        'id': report.id,
        'name': report.name,
        'report_type': format_report_type(
            report.report_type,
        ),
        'raw_report_type': report.report_type,
        'report_icon': _get_report_visual_icon(report.report_type),
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
        'namespace': secondary_scope,
        'scope': scope_value,
        'scope_label': scope_label,
        'scope_asset_type': scope_asset_type or 'kubernetes_cluster',
        'scope_asset_id': getattr(report, 'scope_asset_id', None) or report.cluster_id or '',
        'secondary_scope': secondary_scope,
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
            f'Regenerate {artifact_format.label}' if report.status == 'ready' else f'Generate {artifact_format.label}'
        ),
        'can_archive_report': report.status in ARCHIVABLE_STATUSES,
        'can_restore_report': report.status == 'archived' and bool(artifact_access['reachable']) and file_exists,
        'can_download_artifact': can_download_artifact,
    }


def _summarize_report_file_reference(
    file_path: str | None,
    *,
    active_backend_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return list-safe artifact state without per-row object-storage HEAD checks.

    Generated Reports is a registry view. Exact object existence is verified on the
    detail/download/storage paths where it is actionable. Keeping the list metadata-
    first avoids one remote exists() request per visible report and prevents periodic
    HTMX refreshes from repeatedly probing object storage.
    """

    if not file_path:
        return {
            'exists': False,
            'reachable': True,
            'backend': 'none',
            'backend_label': 'Report Storage',
            'state': 'not_generated',
            'verified': False,
        }

    storage_location = _parse_storage_location(file_path)
    backend_name = str(storage_location.get('backend') or '').lower().strip()
    if not backend_name or backend_name == 'unknown':
        return {
            'exists': False,
            'reachable': True,
            'backend': 'invalid',
            'backend_label': 'Invalid storage reference',
            'state': 'invalid',
            'verified': False,
        }

    if active_backend_status is not None and backend_name == _get_active_storage_backend_name():
        backend_status = dict(active_backend_status)
    else:
        backend_status = get_report_storage_backend_status(backend_name)

    reachable = bool(backend_status.get('reachable', False))
    return {
        # For the registry, a retained URI is enough to expose the download action.
        # The download route performs the authoritative existence probe.
        'exists': bool(file_path and reachable),
        'reachable': reachable,
        'backend': backend_name,
        'backend_label': (storage_location.get('backend_label') or _format_storage_backend_label(backend_name)),
        'state': 'referenced' if reachable else 'unavailable',
        'verified': False,
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
        'namespace': report_item['secondary_scope'],
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
        'can_archive_report': report.status in ARCHIVABLE_STATUSES,
        'can_restore_report': report_item['can_restore_report'],
        'can_download_artifact': report_item['can_download_artifact'],
    }


def archive_report_record(
    report_id: int,
) -> tuple[bool, str]:
    report = db.session.get(
        Report,
        report_id,
    )

    if report is None:
        return False, 'Report not found.'

    if report.status == 'archived':
        return True, 'Report is already archived.'

    if report.status not in ARCHIVABLE_STATUSES:
        return False, f'{STATUS_LABELS.get(report.status, report.status.title())} reports cannot be archived.'

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
        return (
            False,
            'Archived report has no storage metadata. Recover the retained storage reference before restoring this historical record.',
        )

    artifact_access = _probe_report_file(report.file_path)
    if not bool(artifact_access.get('reachable', True)):
        return False, 'Archived report storage is temporarily unavailable. Restore connectivity and retry.'

    if not bool(artifact_access.get('exists', False)):
        return (
            False,
            'Archived report artifact is missing in configured storage. Recover the retained artifact before restoring this historical record.',
        )

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


def _get_report_visual_icon(value: str) -> str:
    """Return a stable Lucide icon for Generated Reports presentation."""

    normalized = (value or '').strip().lower()

    if 'inventory' in normalized:
        return 'boxes'
    if 'alert' in normalized or 'anomal' in normalized:
        return 'siren'
    if 'forecast' in normalized:
        return 'trending-up'
    if 'capacity' in normalized:
        return 'gauge'
    if 'storage' in normalized:
        return 'hard-drive'
    if 'workload' in normalized:
        return 'layers-3'
    if 'consumer' in normalized:
        return 'bar-chart-3'
    if 'utilization' in normalized:
        return 'activity'
    if 'tls' in normalized or 'certificate' in normalized or 'governance' in normalized:
        return 'shield-check'
    if 'analytics' in normalized or 'overview' in normalized:
        return 'chart-no-axes-combined'

    return 'file-text'


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
        return 'Not Available'

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


def _probe_report_file(
    file_path: str | None,
) -> dict[str, Any]:
    return probe_report_artifact(file_path)


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

    backend_label = str(artifact_access.get('backend_label') or 'Report Storage')

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
            'label': 'Storage Unavailable',
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
            'label': 'Missing File',
            'description': 'Report is Ready, but the generated report artifact no longer exists in configured storage.',
            'tone': 'red',
            'icon': 'triangle-alert',
        }

    if report.status == 'ready' and not report.file_path:
        return {
            'label': 'File Path Missing',
            'description': 'Report is Ready, but file_path metadata is empty.',
            'tone': 'red',
            'icon': 'triangle-alert',
        }

    if report.status == 'archived' and report.file_path and file_exists:
        return {
            'label': 'Archived Artifact',
            'description': 'Archived report artifact exists in configured storage and remains downloadable for historical reference.',  # noqa: E501
            'tone': 'gray',
            'icon': 'archive',
        }

    if report.status == 'archived' and report.file_path and not file_exists:
        return {
            'label': 'Archived Artifact Missing',
            'description': 'Archived report has storage metadata, but the generated artifact is missing in configured storage.',  # noqa: E501
            'tone': 'red',
            'icon': 'triangle-alert',
        }

    if report.status == 'archived' and not report.file_path:
        return {
            'label': 'Archived Without Artifact',
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
            'label': 'Not Available',
            'description': 'Generated artifact is not available because generation failed.',
            'tone': 'red',
            'icon': 'triangle-alert',
        }

    return {
        'label': 'Not Generated',
        'description': 'Generated artifact has not been created yet.',
        'tone': 'amber',
        'icon': 'clock-3',
    }


def _get_scope_options() -> list[dict[str, str]]:
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
    object_storage_systems = (
        db.session.execute(
            select(
                ObjectStorageSystem,
            ).order_by(
                ObjectStorageSystem.name.asc(),
            )
        )
        .scalars()
        .all()
    )

    options = [
        {
            'value': '',
            'label': 'All Infrastructure Assets',
        },
    ]

    for cluster in clusters:
        options.append(
            {
                'value': f'{KUBERNETES_CLUSTER_ASSET_TYPE}:{cluster.id}',
                'label': f'Kubernetes · {cluster.name}',
            }
        )

    for system in object_storage_systems:
        options.append(
            {
                'value': f'{OBJECT_STORAGE_SYSTEM_ASSET_TYPE}:{system.id}',
                'label': f'Object Storage · {system.name}',
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


def _get_report_status_counts() -> dict[str, int]:
    rows = db.session.execute(
        select(
            Report.status,
            func.count(Report.id),
        ).group_by(Report.status)
    ).all()
    return {str(status): int(count or 0) for status, count in rows}


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
        '24h': 'Last 24 Hours',
        '7d': 'Last 7 Days',
        '30d': 'Last 30 Days',
        '90d': 'Last 90 Days',
        'month': 'This Month',
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
