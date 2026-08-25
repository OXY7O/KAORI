from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import current_app, url_for
from sqlalchemy import func, select

from app.common.celery_queue_health import get_queue_readiness
from app.extensions.db import db
from app.integrations.delivery.notification_channels.service import notification_channel_summary
from app.models.report import Report, ReportSchedule, ReportTemplate
from app.reports.catalog import (
    REPORT_COVERAGE_DOMAINS,
    REPORT_FAMILY_ANALYTICS,
    REPORT_FAMILY_INVENTORY,
    REPORT_TYPE_OPTIONS,
    REPORT_TYPE_SPECS,
)
from app.reports.export.constants import (
    DEFAULT_REPORT_DOMAIN,
    DEFAULT_REPORT_SOURCE_KIND,
    REPORT_DOMAIN_DESCRIPTIONS,
    REPORT_DOMAIN_LABELS,
    SOURCE_KIND_LABELS,
)
from app.reports.jobs.queue import get_reports_queue_name
from app.reports.storage.health import (
    build_local_storage_health,
    build_s3_storage_health,
)
from app.reports.storage.service import (
    get_configured_storage_backend_name,
    get_report_storage_backend_status,
)
from app.reports.storage.state import format_storage_check_age, format_storage_check_source

PENDING_REPORT_STATUSES = [
    'requested',
    'generating',
]

READY_REPORT_STATUSES = [
    'ready',
]

FAILED_REPORT_STATUSES = [
    'failed',
]

ARCHIVED_REPORT_STATUSES = [
    'archived',
]

IMPLEMENTED_REPORT_TYPES = frozenset(spec.value for spec in REPORT_TYPE_SPECS)


def get_reports_overview_payload() -> dict[str, Any]:
    report_counts = get_report_counts()
    storage_context = get_storage_context()
    report_type_coverage = get_report_type_coverage()
    worker_context = get_queue_readiness(get_reports_queue_name())

    # Reports Overview intentionally loads only the state rendered by the active landing page.
    # Legacy pipeline/context builders remain available for rolling-deployment compatibility,
    # but they no longer trigger extra notification/provider work on every overview request.
    return {
        'page_title': 'Reports Overview',
        'page_subtitle': (
            'Review reporting readiness, artifacts, automation, and report coverage across managed infrastructure.'
        ),
        'selected_cluster_label': 'All Infrastructure Scopes',
        'report_engine_status': worker_context['label'],
        'storage_status': storage_context['display_status'],
        'summary_cards': get_summary_cards(report_counts),
        'reporting_operations': get_reporting_operations(report_counts, storage_context, worker_context),
        'artifact_statistics': get_artifact_statistics(report_counts),
        'artifact_portfolio': get_artifact_portfolio(),
        'automation_summary': get_automation_summary(report_counts, report_type_coverage),
        'report_type_coverage': report_type_coverage,
        'reporting_coverage': get_reporting_coverage_summary(),
        'report_type_summary': get_report_type_summary(report_type_coverage),
        'storage_context': storage_context,
        'worker_context': worker_context,
    }


def get_report_architecture_context() -> dict[str, str]:
    return {
        'active_domain_label': REPORT_DOMAIN_LABELS.get(DEFAULT_REPORT_DOMAIN, 'KAORI Kubernetes Reports'),
        'active_source_label': SOURCE_KIND_LABELS.get(DEFAULT_REPORT_SOURCE_KIND, 'Container Platform'),
        'future_domain_label': REPORT_DOMAIN_LABELS.get('server', 'KAORI Server Reports'),
        'future_domain_description': REPORT_DOMAIN_DESCRIPTIONS.get('server', ''),
        'summary': (
            'Reports are assembled from reusable sections and whichever KAORI integrations are connected, '
            'validated, and authorized for the selected infrastructure scope.'
        ),
    }


def get_report_counts() -> dict[str, int]:
    return {
        'total': count_reports(),
        'ready': count_reports_by_status(READY_REPORT_STATUSES),
        'pending': count_reports_by_status(PENDING_REPORT_STATUSES),
        'failed': count_reports_by_status(FAILED_REPORT_STATUSES),
        'archived': count_reports_by_status(ARCHIVED_REPORT_STATUSES),
        'generated_this_month': count_reports_generated_this_month(),
        'schedules': count_report_schedules(),
        'active_schedules': count_active_report_schedules(),
        'custom_templates': count_custom_report_templates(),
    }


def count_reports() -> int:
    return int(db.session.scalar(select(func.count(Report.id))) or 0)


def count_reports_by_status(statuses: list[str]) -> int:
    return int(db.session.scalar(select(func.count(Report.id)).where(Report.status.in_(statuses))) or 0)


def count_reports_generated_this_month() -> int:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return int(db.session.scalar(select(func.count(Report.id)).where(Report.created_at >= month_start)) or 0)


def count_report_schedules() -> int:
    return int(db.session.scalar(select(func.count(ReportSchedule.id))) or 0)


def count_active_report_schedules() -> int:
    return int(db.session.scalar(select(func.count(ReportSchedule.id)).where(ReportSchedule.is_enabled.is_(True))) or 0)


def count_custom_report_templates() -> int:
    return int(db.session.scalar(select(func.count(ReportTemplate.id))) or 0)


def get_summary_cards(report_counts: dict[str, int]) -> list[dict[str, str]]:
    generated_count = report_counts['ready'] + report_counts['archived']
    return [
        {
            'label': 'Generated',
            'value': str(generated_count),
            'caption': 'Ready or archived artifacts',
            'icon': 'files',
            'tone': 'info',
        },
        {
            'label': 'Ready',
            'value': str(report_counts['ready']),
            'caption': 'Available artifacts',
            'icon': 'circle-check',
            'tone': 'normal',
        },
        {
            'label': 'In Progress',
            'value': str(report_counts['pending']),
            'caption': 'Requested or generating',
            'icon': 'loader-circle',
            'tone': 'info',
        },
        {
            'label': 'Failed',
            'value': str(report_counts['failed']),
            'caption': 'Requires review',
            'icon': 'triangle-alert',
            'tone': 'critical' if report_counts['failed'] else 'normal',
        },
    ]


def get_reporting_operations(
    report_counts: dict[str, int],
    storage_context: dict[str, Any],
    worker_context: dict[str, Any],
) -> list[dict[str, Any]]:
    storage_ready = bool(storage_context.get('ready', False))
    storage_state = str(storage_context.get('state') or 'unknown')
    if storage_ready:
        storage_status_label = 'Connected'
    elif storage_state == 'degraded':
        storage_status_label = 'Degraded'
    elif storage_state == 'misconfigured':
        storage_status_label = 'Needs Review'
    else:
        storage_status_label = 'Disconnected'
    active_schedules = int(report_counts.get('active_schedules', 0))

    return [
        {
            'label': 'Generation Queue',
            'value': 'Operational' if worker_context.get('ready') else str(worker_context.get('label', 'Review')),
            'status': str(worker_context.get('label', 'Unknown')),
            'tone': str(worker_context.get('tone', 'unknown')),
            'icon': 'workflow',
            'caption': (
                f'{int(worker_context.get("worker_count", 0))} worker(s) listening on the Reports queue.'
                if worker_context.get('ready')
                else str(worker_context.get('description', 'Reports queue readiness could not be verified.'))
            ),
            'action_label': 'Generate Report',
            'href': url_for('reports.generate_report'),
        },
        {
            'label': 'Active Schedules',
            'value': str(active_schedules),
            'status': 'Enabled' if active_schedules else 'No Active Schedules',
            'tone': 'normal' if active_schedules else 'unknown',
            'icon': 'calendar-clock',
            'caption': f'{int(report_counts.get("schedules", 0))} total schedule definition(s).',
            'action_label': 'Open Schedules',
            'href': url_for('reports.schedules'),
        },
        {
            'label': 'Artifact Storage',
            'value': str(storage_context.get('label', 'Report Storage')),
            'status': storage_status_label,
            'tone': 'normal' if storage_ready else 'warning',
            'icon': 'hard-drive' if storage_ready else 'cloud-off',
            'caption': f'{storage_context.get("checked_label", "Readiness checked")} · shared readiness state.',
            'action_label': 'Open Storage',
            'href': url_for('reports.storage'),
        },
    ]


def get_reporting_coverage_summary() -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {
        REPORT_FAMILY_ANALYTICS: {
            'key': REPORT_FAMILY_ANALYTICS,
            'label': 'Analytics Reports',
            'description': 'Time-range analysis and operational evidence.',
            'icon': 'chart-no-axes-combined',
            'formats': ['PDF', 'CSV'],
            'items': [],
        },
        REPORT_FAMILY_INVENTORY: {
            'key': REPORT_FAMILY_INVENTORY,
            'label': 'Inventory Reports',
            'description': 'Point-in-time infrastructure asset evidence.',
            'icon': 'boxes',
            'formats': ['XLSX', 'CSV'],
            'items': [],
        },
    }

    for spec in REPORT_TYPE_SPECS:
        group = groups.get(spec.family)
        if group is None:
            continue
        label = str(spec.label)
        if label.endswith(' Report'):
            label = label[:-7]
        group['items'].append(
            {
                'label': label,
                'value': spec.value,
                'icon': spec.icon,
            }
        )

    for group in groups.values():
        group['contract_count'] = len(group['items'])

    return [groups[REPORT_FAMILY_ANALYTICS], groups[REPORT_FAMILY_INVENTORY]]


def get_artifact_statistics(report_counts: dict[str, int]) -> list[dict[str, str]]:
    completed = int(report_counts.get('ready', 0)) + int(report_counts.get('archived', 0))
    failed = int(report_counts.get('failed', 0))
    resolved = completed + failed
    completion_rate = f'{round((completed / resolved) * 100)}%' if resolved else '—'
    footprint_bytes = int(
        db.session.scalar(
            select(func.coalesce(func.sum(Report.file_size_bytes), 0)).where(
                Report.status.in_(READY_REPORT_STATUSES + ARCHIVED_REPORT_STATUSES)
            )
        )
        or 0
    )

    return [
        {
            'label': 'Requests This Month',
            'value': str(report_counts.get('generated_this_month', 0)),
            'caption': 'Report requests created this calendar month',
            'icon': 'calendar-range',
        },
        {
            'label': 'Completion Rate',
            'value': completion_rate,
            'caption': 'Ready or archived among resolved requests',
            'icon': 'badge-check',
        },
        {
            'label': 'Artifact Footprint',
            'value': format_file_size(footprint_bytes),
            'caption': 'Stored ready and archived artifacts',
            'icon': 'database',
        },
        {
            'label': 'Custom Templates',
            'value': str(report_counts.get('custom_templates', 0)),
            'caption': 'Reusable operator-defined templates',
            'icon': 'layout-template',
        },
    ]


def get_artifact_portfolio() -> dict[str, list[dict[str, str]]]:
    generated_statuses = READY_REPORT_STATUSES + ARCHIVED_REPORT_STATUSES
    family_by_type = {spec.value: spec.family for spec in REPORT_TYPE_SPECS}

    type_rows = db.session.execute(
        select(Report.report_type, func.count(Report.id))
        .where(Report.status.in_(generated_statuses))
        .group_by(Report.report_type)
    ).all()
    family_counts = {REPORT_FAMILY_ANALYTICS: 0, REPORT_FAMILY_INVENTORY: 0}
    for report_type, count in type_rows:
        family = family_by_type.get(str(report_type))
        if family in family_counts:
            family_counts[family] += int(count or 0)

    format_rows = db.session.execute(
        select(Report.output_format, func.count(Report.id))
        .where(Report.status.in_(generated_statuses))
        .group_by(Report.output_format)
    ).all()
    format_counts = {str(fmt or '').upper(): int(count or 0) for fmt, count in format_rows}

    return {
        'families': [
            {
                'label': 'Analytics',
                'value': str(family_counts[REPORT_FAMILY_ANALYTICS]),
                'icon': 'chart-no-axes-combined',
            },
            {'label': 'Inventory', 'value': str(family_counts[REPORT_FAMILY_INVENTORY]), 'icon': 'boxes'},
        ],
        'formats': [
            {'label': 'PDF', 'value': str(format_counts.get('PDF', 0))},
            {'label': 'CSV', 'value': str(format_counts.get('CSV', 0))},
            {'label': 'XLSX', 'value': str(format_counts.get('XLSX', 0))},
        ],
    }


def get_automation_summary(
    report_counts: dict[str, int],
    report_type_coverage: dict[str, Any],
) -> dict[str, str]:
    return {
        'active_schedules': str(report_counts.get('active_schedules', 0)),
        'total_schedules': str(report_counts.get('schedules', 0)),
        'custom_templates': str(report_counts.get('custom_templates', 0)),
        'available_contracts': str(report_type_coverage.get('available_count', 0)),
    }


def get_report_type_coverage() -> dict[str, Any]:
    published_by_domain: dict[str, list[dict[str, str]]] = {}
    for option in REPORT_TYPE_OPTIONS:
        report_type = str(option.get('value', ''))
        if report_type not in IMPLEMENTED_REPORT_TYPES:
            continue
        domain_key = str(option.get('domain') or 'kubernetes')
        published_by_domain.setdefault(domain_key, []).append(
            {
                'name': str(option.get('label', report_type)),
                'description': str(option.get('description', 'Operational report type.')),
                'icon': str(option.get('icon', 'file-text')),
                'status': 'Published',
                'tone': 'normal',
            }
        )

    coverage_by_domain = {domain.key: domain for domain in REPORT_COVERAGE_DOMAINS}
    domain_order = ['kubernetes', 'object_storage', 'server', 'hci']
    domains: list[dict[str, Any]] = []

    for domain_key in domain_order:
        published_items = list(published_by_domain.get(domain_key, ()))
        coverage = coverage_by_domain.get(domain_key)
        published_names = {item['name'] for item in published_items}
        candidate_items: list[dict[str, str]] = []
        if coverage is not None:
            candidate_items = [
                {
                    'name': item.name,
                    'description': item.description,
                    'icon': item.icon,
                    'status': 'Candidate' if published_items else coverage.status,
                    'tone': 'info' if published_items else coverage.tone,
                }
                for item in coverage.items
                if item.name not in published_names
            ]

        if domain_key == 'kubernetes':
            label = 'Kubernetes Reports'
            description = (
                'Published report contracts backed by Kubernetes inventory, Metrics Source data, '
                'and Alertmanager context.'
            )
            icon = 'boxes'
        elif coverage is not None:
            label = coverage.label
            description = coverage.description
            icon = coverage.icon
        else:
            label = REPORT_DOMAIN_LABELS.get(domain_key, domain_key.replace('_', ' ').title())
            description = REPORT_DOMAIN_DESCRIPTIONS.get(domain_key, '')
            icon = 'file-text'

        if published_items:
            status = 'Published'
            tone = 'normal'
        elif coverage is not None:
            status = coverage.status
            tone = coverage.tone
        else:
            status = 'Reserved'
            tone = 'unknown'

        domains.append(
            {
                'key': domain_key,
                'label': label,
                'description': description,
                'icon': icon,
                'status': status,
                'tone': tone,
                'items': [*published_items, *candidate_items],
                'available_count': len(published_items),
                'published_count': len(published_items),
                'candidate_count': len(candidate_items),
                'total_count': len(published_items) + len(candidate_items),
            }
        )

    published_count = sum(int(domain['published_count']) for domain in domains)
    candidate_count = sum(int(domain['candidate_count']) for domain in domains)
    return {
        'domains': domains,
        'available_count': published_count,
        'published_count': published_count,
        'candidate_count': candidate_count,
        'domain_count': len(domains),
        'total_count': published_count + candidate_count,
    }


def get_storage_context() -> dict[str, Any]:
    backend_name = get_configured_storage_backend_name()
    local_health = build_local_storage_health()
    s3_health = build_s3_storage_health()
    backend_status = get_report_storage_backend_status(backend_name)
    is_ready = bool(backend_status.get('write_available', False))
    state = str(backend_status.get('state') or 'unknown')
    checked_label = format_storage_check_age(backend_status)

    try:
        monitor_interval = int(current_app.config.get('REPORT_STORAGE_HEALTH_INTERVAL_MINUTES', 1) or 1)
    except (TypeError, ValueError):
        monitor_interval = 1

    if backend_name == 's3':
        if is_ready:
            display_status = 'S3 Storage Connected'
        elif state == 'degraded':
            display_status = 'S3 Storage Degraded'
        elif state == 'misconfigured':
            display_status = 'S3 Storage Needs Review'
        else:
            display_status = 'S3 Storage Disconnected'
        active_detail = 'S3-compatible object storage'
    else:
        display_status = 'Local Storage Ready' if is_ready else 'Local Storage Review'
        active_detail = 'local filesystem storage'

    return {
        'backend': backend_name,
        'label': str(
            backend_status.get('label') or ('S3-compatible storage' if backend_name == 's3' else 'Local filesystem')
        ),
        'status': 'selected' if is_ready else 'unavailable',
        'state': state,
        'display_status': display_status,
        'tone': str(backend_status.get('tone') or ('green' if is_ready else 'amber')),
        'description': str(backend_status.get('description') or ''),
        'active_detail': active_detail,
        'ready': is_ready,
        'degraded': not is_ready,
        'checked_at': backend_status.get('checked_at'),
        'checked_label': checked_label,
        'source': str(backend_status.get('source') or 'direct'),
        'source_label': format_storage_check_source(backend_status),
        'stale': bool(backend_status.get('stale', False)),
        'monitor_interval_minutes': max(monitor_interval, 1),
        'local': local_health,
        's3': s3_health,
        'backend_status': backend_status,
    }


def get_report_type_summary(report_type_coverage: dict[str, Any]) -> dict[str, str]:
    available = int(report_type_coverage.get('available_count', 0))
    total = int(report_type_coverage.get('total_count', 0))
    candidate = int(report_type_coverage.get('candidate_count', max(total - available, 0)))
    return {
        'available': str(available),
        'total': str(total),
        'label': f'{available} Published Contracts',
        'description': (
            f'{candidate} candidate contract(s) remain unpublished across evidence-ready, planned, '
            'or reserved infrastructure domains.'
        ),
    }


def get_notification_delivery_context() -> dict[str, Any]:
    summary = notification_channel_summary()
    return {
        'label': 'Notification Channels',
        'status': str(summary['label']),
        'tone': str(summary['tone']),
        'ready': int(summary['eligible']) > 0,
        'eligible': int(summary['eligible']),
        'operational': int(summary['operational']),
        'providers': list(summary['provider_labels']),
        'description': 'Reusable Telegram, email, and Microsoft Teams destinations are managed under Integrations.',
    }


def get_pipeline_status(
    storage_context: dict[str, Any],
    notification_delivery: dict[str, Any] | None = None,
    worker_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    storage_tone = 'normal' if str(storage_context.get('tone')) == 'green' else 'warning'
    delivery = notification_delivery or get_notification_delivery_context()
    delivery_ready = bool(delivery.get('ready'))
    worker = worker_context or get_queue_readiness(get_reports_queue_name())

    return [
        {
            'name': 'Configure Report',
            'summary': 'Choose the report type, scope, period, sections, and canonical output format.',
            'description': (
                'The Generate Report form validates the selected report contract, required cluster scope, '
                'section selection, and active artifact storage before a request is created.'
            ),
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'sliders-horizontal',
        },
        {
            'name': 'Create & Queue Report Request',
            'summary': 'KAORI persists the request and dispatches one canonical report job.',
            'description': (
                'Generate Report and scheduled runs both save the report definition, create one JobExecution, '
                'and enqueue artifact generation on the configured Reports queue.'
            ),
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'clipboard-plus',
        },
        {
            'name': 'Start Worker Generation',
            'summary': 'The dedicated Reports worker claims the queued artifact job.',
            'description': str(worker['description']),
            'status': str(worker['label']),
            'tone': str(worker['tone']),
            'icon': str(worker['icon']),
        },
        {
            'name': 'Collect Data & Render Artifact',
            'summary': 'Connected evidence is collected and rendered by the canonical Analytics PDF or Inventory Excel engine.',
            'description': (
                'KAORI collects the selected report payloads from validated integrations, builds the chosen '
                'sections, and renders one standalone report artifact.'
            ),
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'file-cog',
        },
        {
            'name': 'Store Artifact',
            'summary': 'The report artifact is saved to the active Local or S3-compatible backend.',
            'description': str(storage_context.get('description', 'Report storage backend status is unavailable.')),
            'status': str(storage_context.get('display_status', 'Storage Review')),
            'tone': storage_tone,
            'icon': 'hard-drive',
        },
        {
            'name': 'Complete & Optional Delivery',
            'summary': 'The report becomes Ready; scheduled reports can notify selected platform channels.',
            'description': (
                'After storage succeeds, KAORI records the artifact metadata and marks the report Ready. '
                'When a schedule selects validated Notification Channels, KAORI sends a provider-neutral report event and report detail link. '
                'Manual reports remain available from Generated Reports.'
            ),
            'status': 'Delivery Ready' if delivery_ready else 'Channel Setup Required',
            'tone': 'normal' if delivery_ready else 'warning',
            'icon': 'send',
        },
    ]


def get_pipeline_summary(pipeline_status: list[dict[str, str]]) -> dict[str, int]:
    ready = sum(1 for item in pipeline_status if item.get('tone') == 'normal')
    review = sum(1 for item in pipeline_status if item.get('tone') == 'warning')
    planned = sum(1 for item in pipeline_status if item.get('tone') in {'info', 'unknown'})
    return {
        'ready': ready,
        'review': review,
        'planned': planned,
        'total': len(pipeline_status),
    }


def get_reporting_context(
    storage_context: dict[str, Any],
    notification_delivery: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    delivery = notification_delivery or get_notification_delivery_context()
    return [
        {
            'title': 'Integration-Driven Coverage',
            'description': (
                'A report can be generated for any supported infrastructure domain when its required '
                'KAORI integrations are connected and validated.'
            ),
            'icon': 'plug-zap',
            'detail': (
                'The available source set determines which report types and sections can be populated '
                'with current evidence.'
            ),
        },
        {
            'title': 'Reusable Report Contracts',
            'description': (
                'Base and custom templates define audience, sections, scope, and document structure '
                'without coupling reports to one dashboard page.'
            ),
            'icon': 'layout-template',
            'detail': (
                'The same generation workflow can support Kubernetes, server, VM, HCI, security, '
                'storage, and additional provider domains.'
            ),
        },
        {
            'title': 'Governed Artifact Lifecycle',
            'description': (
                f'Generated report artifacts use the active {storage_context["active_detail"]} backend with '
                'repeatable naming, ownership, archive, and retention boundaries.'
            ),
            'icon': 'archive',
            'detail': (
                'Storage selection is independent from report composition, so local filesystem '
                'and S3-compatible backends share one lifecycle model.'
            ),
        },
        {
            'title': 'Automation & Delivery',
            'description': (
                f'Manual generation and recurring schedules are available now. Notification Channels are '
                f'{str(delivery.get("status", "Configuration Required")).lower()} with '
                f'{int(delivery.get("eligible", 0))} eligible destination(s).'
            ),
            'icon': 'workflow',
            'detail': (
                'Generation remains the authoritative step, while delivery channels distribute '
                'the completed artifact to approved destinations.'
            ),
        },
    ]


def get_current_status(
    report_counts: dict[str, int],
    storage_context: dict[str, Any],
    report_type_coverage: dict[str, Any],
    worker_context: dict[str, Any],
) -> list[dict[str, str]]:
    type_summary = get_report_type_summary(report_type_coverage)
    storage_tone = 'normal' if str(storage_context.get('tone')) == 'green' else 'warning'

    return [
        {
            'label': 'Reports Worker',
            'value': str(worker_context['label']),
            'description': str(worker_context['description']),
            'tone': str(worker_context['tone']),
            'icon': str(worker_context['icon']),
        },
        {
            'label': 'Generated Artifacts',
            'value': str(report_counts['total']),
            'description': (
                f'{report_counts["ready"]} ready, {report_counts["pending"]} in progress, '
                f'{report_counts["failed"]} failed, and {report_counts["archived"]} archived.'
            ),
            'tone': 'normal' if report_counts['failed'] == 0 else 'warning',
            'icon': 'files',
        },
        {
            'label': 'Available Report Types',
            'value': type_summary['available'],
            'description': type_summary['description'],
            'tone': 'normal',
            'icon': 'clipboard-check',
        },
        {
            'label': 'Artifact Storage',
            'value': str(storage_context.get('display_status', 'Storage Review')),
            'description': str(storage_context.get('description', 'Report storage backend status is unavailable.')),
            'tone': storage_tone,
            'icon': 'hard-drive',
        },
        {
            'label': 'Custom Templates',
            'value': str(report_counts['custom_templates']),
            'description': 'Reusable user-defined templates in addition to protected base templates.',
            'tone': 'normal' if report_counts['custom_templates'] else 'unknown',
            'icon': 'copy-plus',
        },
        {
            'label': 'Schedule Automation',
            'value': str(report_counts['active_schedules']),
            'description': (
                f'{report_counts["schedules"]} total schedules and '
                f'{report_counts["active_schedules"]} currently enabled.'
            ),
            'tone': 'normal' if report_counts['active_schedules'] else 'unknown',
            'icon': 'calendar-clock',
        },
    ]


def get_current_status_summary(current_status: list[dict[str, str]]) -> dict[str, Any]:
    ready = sum(1 for item in current_status if item.get('tone') == 'normal')
    review = sum(1 for item in current_status if item.get('tone') == 'warning')
    neutral = sum(1 for item in current_status if item.get('tone') in {'unknown', 'info'})
    posture = 'Needs Review' if review else 'Ready'
    tone = 'warning' if review else 'normal'
    return {
        'ready': ready,
        'review': review,
        'neutral': neutral,
        'posture': posture,
        'tone': tone,
    }


def get_reporting_operating_model(
    report_counts: dict[str, int],
    storage_context: dict[str, Any],
    report_type_coverage: dict[str, Any],
    notification_delivery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    type_summary = get_report_type_summary(report_type_coverage)
    delivery = notification_delivery or get_notification_delivery_context()
    return {
        'title': 'Reporting Operating Model',
        'description': 'How KAORI composes, governs, stores, and automates infrastructure reports.',
        'cards': [
            {
                'label': 'Compose from Integrations',
                'value': type_summary['available'],
                'description': (
                    'Available report types are populated from connected and validated infrastructure sources.'
                ),
                'icon': 'plug-zap',
                'tone': 'normal',
            },
            {
                'label': 'Govern with Templates',
                'value': str(report_counts['custom_templates']),
                'description': (
                    'Protected base templates and custom templates define sections, audience, and document structure.'
                ),
                'icon': 'layout-template',
                'tone': 'info',
            },
            {
                'label': 'Store as Artifacts',
                'value': str(storage_context.get('label', 'Storage')),
                'description': (
                    'Generated report artifacts follow one naming, archive, and retention contract across '
                    'supported storage backends.'
                ),
                'icon': 'archive',
                'tone': 'normal' if str(storage_context.get('tone')) == 'green' else 'warning',
            },
            {
                'label': 'Automate and Deliver',
                'value': str(delivery.get('status', 'Configuration Required')),
                'description': (
                    f'{report_counts["active_schedules"]} active schedules can generate reports automatically. '
                    'Validated Telegram, email, and Microsoft Teams channels can be selected per report schedule.'
                ),
                'icon': 'send-horizontal',
                'tone': 'normal' if bool(delivery.get('ready')) else 'warning',
            },
        ],
    }


def get_data_collection_status(
    storage_context: dict[str, Any],
    notification_delivery: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    delivery = notification_delivery or get_notification_delivery_context()
    s3_context = storage_context.get('s3', {})
    s3_selected = storage_context.get('backend') == 's3'
    custom_endpoint = bool(s3_context.get('endpoint_url')) and s3_context.get('endpoint_url') != 'AWS default endpoint'
    s3_name = 'MinIO / S3-Compatible Storage' if custom_endpoint else 'S3-Compatible Storage'
    s3_status = str(storage_context.get('display_status')) if s3_selected else 'Available'
    s3_tone = 'normal' if s3_selected and str(storage_context.get('tone')) == 'green' else 'info'

    return [
        {
            'stage': 'ready',
            'stage_label': 'Ready Now',
            'name': 'Kubernetes API',
            'category': 'Inventory Source',
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'boxes',
            'description': (
                'Cluster, node, namespace, workload, pod, service, ingress, storage, and configuration inventory.'
            ),
        },
        {
            'stage': 'ready',
            'stage_label': 'Ready Now',
            'name': 'Metrics Source',
            'category': 'Metrics Source',
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'activity',
            'description': (
                'Utilization, capacity, storage, workload, forecast, and top-consumer evidence for report sections.'
            ),
        },
        {
            'stage': 'ready',
            'stage_label': 'Ready Now',
            'name': 'Alertmanager',
            'category': 'Alert Source',
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'siren',
            'description': 'Active alerts, routing, silence, inhibition, ownership, and incident-readiness context.',
        },
        {
            'stage': 'ready' if storage_context.get('backend') == 'local' else 'available',
            'stage_label': 'Ready Now' if storage_context.get('backend') == 'local' else 'Available',
            'name': 'Local Filesystem',
            'category': 'Artifact Storage',
            'status': 'Selected' if storage_context.get('backend') == 'local' else 'Available',
            'tone': 'normal' if storage_context.get('backend') == 'local' else 'info',
            'icon': 'folder-archive',
            'description': (
                'Local report artifact storage using the shared naming, archive, download, and retention model.'
            ),
        },
        {
            'stage': 'ready' if s3_selected else 'available',
            'stage_label': 'Ready Now' if s3_selected else 'Available',
            'name': s3_name,
            'category': 'Artifact Storage',
            'status': s3_status,
            'tone': s3_tone,
            'icon': 'database',
            'description': (
                'AWS S3, MinIO, or another S3-compatible backend for generated reports and operational evidence.'
            ),
        },
        {
            'stage': 'planned',
            'stage_label': 'Planned',
            'name': 'Server & VM Inventory',
            'category': 'Compute Source',
            'status': 'Planned',
            'tone': 'info',
            'icon': 'server-cog',
            'description': (
                'Physical server and VM inventory combined with Node Exporter metrics for server report families.'
            ),
        },
        {
            'stage': 'reserved',
            'stage_label': 'Reserved',
            'name': 'HCI Provider APIs',
            'category': 'HCI Source',
            'status': 'Reserved',
            'tone': 'unknown',
            'icon': 'network',
            'description': 'HCI cluster, host, datastore, storage pool, and VM placement data from provider APIs.',
        },
        {
            'stage': 'reserved',
            'stage_label': 'Reserved',
            'name': 'Vault & Secret Providers',
            'category': 'Security Source',
            'status': 'Reserved',
            'tone': 'unknown',
            'icon': 'key-round',
            'description': (
                'External secret, credential, and access-policy evidence for future security-focused reports.'
            ),
        },
        {
            'stage': 'ready' if bool(delivery.get('ready')) else 'available',
            'stage_label': 'Ready Now' if bool(delivery.get('ready')) else 'Available to Configure',
            'name': 'Notification Channels',
            'category': 'Delivery Integration',
            'status': str(delivery.get('status', 'Configuration Required')),
            'tone': 'normal' if bool(delivery.get('ready')) else 'warning',
            'icon': 'send',
            'description': (
                'Telegram, email, and Microsoft Teams destinations are configured once under Integrations and '
                'selected by channel identity on each report schedule.'
            ),
        },
    ]


def get_related_information() -> list[dict[str, str]]:
    return [
        {
            'label': 'Generate Report',
            'description': 'Select a report type, scope, period, sections, and output contract.',
            'icon': 'plus-circle',
            'href': url_for('reports.generate_report'),
        },
        {
            'label': 'Report Templates',
            'description': 'Review protected base templates and create reusable custom templates.',
            'icon': 'layout-template',
            'href': url_for('reports.report_templates'),
        },
        {
            'label': 'Report Schedules',
            'description': 'Create recurring generation definitions and run schedules on demand.',
            'icon': 'calendar-clock',
            'href': url_for('reports.schedules'),
        },
        {
            'label': 'Report Storage',
            'description': 'Review the active artifact backend, retention boundary, and storage health.',
            'icon': 'hard-drive',
            'href': url_for('reports.storage'),
        },
        {
            'label': 'Infrastructure Integrations',
            'description': 'Manage the provider connections that determine report data availability.',
            'icon': 'plug-zap',
            'href': url_for('integrations.overview'),
        },
    ]


def format_report_type(report_type: str) -> str:
    for option in REPORT_TYPE_OPTIONS:
        if option.get('value') == report_type:
            return str(option.get('label', report_type))

    return report_type.replace('_', ' ').title()


def format_status_label(status: str) -> str:
    return {
        'requested': 'Requested',
        'generating': 'Generating',
        'ready': 'Ready',
        'failed': 'Failed',
        'archived': 'Archived',
    }.get(status, status.title())


def serialize_recent_report(report: Report) -> dict[str, Any]:
    """Return the compact, storage-safe report summary shared by overview payloads."""
    return {
        'name': report.name,
        'report_type_label': str(report.report_type or '').replace('_', ' ').title(),
        'created_at': report.created_at.isoformat() if report.created_at is not None else None,
        'file_size_display': format_file_size(report.file_size_bytes),
        'status': report.status,
        'status_label': format_status_label(report.status),
        'status_tone': get_status_tone(report.status),
    }


def get_status_tone(status: str) -> str:
    return {
        'requested': 'blue',
        'generating': 'purple',
        'ready': 'green',
        'failed': 'red',
        'archived': 'gray',
    }.get(status, 'gray')


def format_file_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return '-'

    units = ['B', 'KB', 'MB', 'GB']
    size = float(size_bytes)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == 'B':
                return f'{int(size)} {unit}'

            return f'{size:.1f} {unit}'

        size /= 1024

    return f'{size_bytes} B'
