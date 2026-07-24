from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import url_for
from sqlalchemy import func, select

from app.extensions.db import db
from app.models.report import Report, ReportSchedule, ReportTemplate
from app.reports.export.constants import (
    DEFAULT_REPORT_DOMAIN,
    DEFAULT_REPORT_SOURCE_KIND,
    REPORT_DOMAIN_DESCRIPTIONS,
    REPORT_DOMAIN_LABELS,
    SOURCE_KIND_LABELS,
)
from app.reports.generate.service import REPORT_TYPE_OPTIONS
from app.reports.storage.health import (
    build_local_storage_health,
    build_s3_storage_health,
)
from app.reports.storage.service import get_configured_storage_backend_name

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

IMPLEMENTED_REPORT_TYPES = {
    'analytics_overview',
    'resource_utilization',
    'capacity_analysis',
    'storage_analysis',
    'workload_analysis',
    'resource_forecast',
    'top_consumers',
    'alerts_anomalies',
}

SERVER_REPORT_TYPE_COVERAGE = [
    {
        'name': 'VM Inventory Report',
        'description': 'Virtual machine catalog, ownership, power state, operating system, CPU, memory, disk, and placement summary.',
        'icon': 'monitor-cog',
    },
    {
        'name': 'VM Capacity Report',
        'description': 'Allocated versus consumed CPU, memory, storage, and growth indicators for virtualized workloads.',
        'icon': 'gauge',
    },
    {
        'name': 'HCI Cluster Health Report',
        'description': 'Host availability, cluster posture, storage pool status, replication signals, and operational risk highlights.',
        'icon': 'network',
    },
    {
        'name': 'Datastore & Volume Report',
        'description': 'Datastore utilization, free capacity, thin provisioning exposure, and storage pressure overview.',
        'icon': 'database',
    },
    {
        'name': 'Host Utilization Report',
        'description': 'Hypervisor host usage, contention indicators, consolidation opportunity, and noisy neighbor signals.',
        'icon': 'server-cog',
    },
    {
        'name': 'VM Placement & Risk Report',
        'description': 'Placement quality, affinity context, HA/DR readiness, and VM concentration risk across host groups.',
        'icon': 'git-fork',
    },
]

SCHEDULE_STATUS = 'Ready'


def get_reports_overview_payload() -> dict[str, Any]:
    report_counts = get_report_counts()
    storage_context = get_storage_context()
    report_type_coverage = get_report_type_coverage()

    return {
        'page_title': 'Reports Overview',
        'page_subtitle': (
            'Generate readable infrastructure reports from inventory, analytics, schedules, templates, and artifact lifecycle data across container platform resources today and server/HCI resources next.'
        ),
        'selected_cluster_label': 'All Clusters',
        'report_engine_status': 'Ready',
        'storage_status': storage_context['display_status'],
        'summary_cards': get_summary_cards(report_counts),
        'recent_reports': get_recent_reports(),
        'report_type_coverage': report_type_coverage,
        'report_architecture_context': get_report_architecture_context(),
        'pipeline_status': get_pipeline_status(storage_context),
        'reporting_context': get_reporting_context(storage_context),
        'current_status': get_current_status(report_counts, storage_context, report_type_coverage),
        'reporting_operating_model': get_reporting_operating_model(
            report_counts, storage_context, report_type_coverage
        ),
        'data_collection_status': get_data_collection_status(),
        'storage_context': storage_context,
    }


def get_report_architecture_context() -> dict[str, str]:
    return {
        'active_domain_label': REPORT_DOMAIN_LABELS.get(DEFAULT_REPORT_DOMAIN, 'KAORI Kubernetes Reports'),
        'active_source_label': SOURCE_KIND_LABELS.get(DEFAULT_REPORT_SOURCE_KIND, 'Container Platform'),
        'future_domain_label': REPORT_DOMAIN_LABELS.get('server', 'KAORI Server Reports'),
        'future_domain_description': REPORT_DOMAIN_DESCRIPTIONS.get('server', ''),
        'summary': 'KAORI Kubernetes Reports owns Kubernetes reporting, KAORI Server Reports owns server/VM reporting with Node Exporter signals, and KAORI HCI Reports owns HCI provider API reporting.',
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
    return [
        {
            'label': 'Total Reports',
            'value': str(report_counts['total']),
            'caption': 'All report records',
            'icon': 'files',
            'tone': 'blue',
        },
        {
            'label': 'Generated This Month',
            'value': str(report_counts['generated_this_month']),
            'caption': 'Reports created this month',
            'icon': 'calendar-days',
            'tone': 'green',
        },
        {
            'label': 'Ready Reports',
            'value': str(report_counts['ready']),
            'caption': 'Available for download',
            'icon': 'check-circle-2',
            'tone': 'purple',
        },
        {
            'label': 'Enabled Schedules',
            'value': str(report_counts['active_schedules']),
            'caption': 'Enabled recurring definitions',
            'icon': 'calendar-clock',
            'tone': 'purple',
        },
    ]


def get_recent_reports(limit: int = 5) -> list[dict[str, Any]]:
    reports = db.session.scalars(select(Report).order_by(Report.created_at.desc()).limit(limit)).all()

    return [serialize_recent_report(report) for report in reports]


def serialize_recent_report(report: Report) -> dict[str, Any]:
    status = str(report.status or 'requested').lower()

    return {
        'id': report.id,
        'name': report.name,
        'report_type': report.report_type,
        'report_type_label': format_report_type(report.report_type),
        'status': status,
        'status_label': format_status_label(status),
        'status_tone': get_status_tone(status),
        'period': report.period,
        'scope': report.namespace or 'All namespaces',
        'created_at': report.created_at,
        'file_size': format_file_size(report.file_size_bytes),
        'href': url_for('reports.generated_report_detail', report_id=report.id),
    }


def get_report_type_coverage() -> dict[str, Any]:
    kubernetes_items: list[dict[str, str]] = []

    for option in REPORT_TYPE_OPTIONS:
        report_type = str(option.get('value', ''))
        is_ready = report_type in IMPLEMENTED_REPORT_TYPES

        kubernetes_items.append(
            {
                'name': str(option.get('label', report_type)),
                'description': str(option.get('description', 'Operational report type.')),
                'icon': str(option.get('icon', 'file-text')),
                'status': 'Available' if is_ready else 'Reserved',
                'tone': 'blue' if is_ready else 'gray',
            }
        )

    server_items = [
        {
            **item,
            'status': 'Reserved',
            'tone': 'gray',
        }
        for item in SERVER_REPORT_TYPE_COVERAGE
    ]

    return {
        'kubernetes': {
            'label': 'KAORI Kubernetes Reports Infrastructure Reports',
            'description': 'Infrastructure report types currently backed by container platform inventory, metrics, alerts, and report templates.',
            'items': kubernetes_items,
            'available_count': sum(1 for item in kubernetes_items if item['status'] == 'Available'),
            'total_count': len(kubernetes_items),
        },
        'server': {
            'label': 'KAORI Server Reports Infrastructure Reports',
            'description': 'Infrastructure report types reserved for future VM, physical server, and HCI domains while reusing the same template, schedule, and storage model.',
            'items': server_items,
            'available_count': 0,
            'total_count': len(server_items),
        },
    }


def get_storage_context() -> dict[str, Any]:
    backend_name = get_configured_storage_backend_name()
    local_health = build_local_storage_health()
    s3_health = build_s3_storage_health()

    if backend_name == 's3':
        status = 'selected'
        display_status = 'S3-Compatible Storage'
        tone = 'green'
        description = 'S3-compatible object storage is selected as the report artifact backend. Detailed bucket, endpoint, credential, and datastore validation is handled on the Storage page.'
        active_detail = 'S3-compatible object storage'
    else:
        root_writable = bool(local_health.get('root_writable', False))
        status = 'selected' if root_writable else 'path_review'
        display_status = 'Local Storage' if root_writable else 'Local Storage Review'
        tone = 'green' if root_writable else 'amber'
        description = (
            'Local filesystem storage is selected as the report artifact backend. Detailed path and retention validation is handled on the Storage page.'
            if root_writable
            else 'Local filesystem storage is selected, but the configured report path should be reviewed on the Storage page.'
        )
        active_detail = 'local filesystem storage'

    return {
        'backend': backend_name,
        'label': 'S3-compatible storage' if backend_name == 's3' else 'Local filesystem',
        'status': status,
        'display_status': display_status,
        'tone': tone,
        'description': description,
        'active_detail': active_detail,
        'local': local_health,
        's3': s3_health,
    }


def get_pipeline_status(storage_context: dict[str, Any]) -> list[dict[str, str]]:
    storage_tone = str(storage_context.get('tone', 'amber'))

    return [
        {
            'name': 'Container Platform Data Collection',
            'description': 'Container platform inventory, workload metadata, Prometheus metrics, and Alertmanager signals are available for infrastructure reports.',
            'status': 'Ready',
            'tone': 'blue',
            'icon': 'boxes',
        },
        {
            'name': 'Server & HCI Data Collection',
            'description': 'Server/VM collectors belong to KAORI Server Reports, while HCI provider collectors belong to KAORI HCI Reports. Both reuse this reporting workflow.',
            'status': 'Reserved',
            'tone': 'gray',
            'icon': 'server-cog',
        },
        {
            'name': 'Report Request',
            'description': 'Manual generation persists the report contract, selected sections, scope, output format, and owner snapshot.',
            'status': 'Ready',
            'tone': 'blue',
            'icon': 'send',
        },
        {
            'name': 'PDF Export Engine',
            'description': 'PDF rendering creates readable documents with cover, reader overview, metadata, and data sections from the selected template.',
            'status': 'Ready',
            'tone': 'blue',
            'icon': 'file-check-2',
        },
        {
            'name': 'Storage Backend',
            'description': str(storage_context.get('description', 'Report storage backend status is unavailable.')),
            'status': str(storage_context.get('display_status', 'Storage Review')),
            'tone': storage_tone,
            'icon': 'hard-drive',
        },
        {
            'name': 'Schedule Worker',
            'description': 'Recurring report automation is available through the UI Run now action and the flask run-report-schedules CLI worker.',
            'status': SCHEDULE_STATUS,
            'tone': 'blue',
            'icon': 'calendar-clock',
        },
    ]


def get_reporting_context(storage_context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            'title': 'Infrastructure domain ownership',
            'description': 'The reporting engine is domain-aware. KAORI Kubernetes Reports, KAORI Server Reports, and KAORI HCI Reports keep Kubernetes, server/VM, and HCI source families separated from the start.',
            'icon': 'workflow',
            'bullets': [
                'KAORI Kubernetes Reports source family: Kubernetes, Prometheus, and Alertmanager.',
                'KAORI Server Reports source family: server/VM inventory and Node Exporter. KAORI HCI Reports source family: HCI API.',
            ],
        },
        {
            'title': 'Readable report contract',
            'description': 'Reports are designed as standalone documents, not dashboard screenshots. Each generated PDF should include scope, reader guidance, metadata, and selected report sections.',
            'icon': 'book-open-check',
            'bullets': [
                'Base templates provide standard infrastructure reporting sections.',
                'Custom templates can clone a base template or select only required sections.',
            ],
        },
        {
            'title': 'Storage and lifecycle',
            'description': f'Generated artifacts are stored through the active {storage_context["active_detail"]} backend with domain-aware object prefixes.',
            'icon': 'archive',
            'bullets': [
                'Local and S3-compatible storage use the same artifact naming model.',
                'Retention and cleanup policy are defined separately from manual archive/restore actions.',
            ],
        },
        {
            'title': 'Automation boundary',
            'description': 'Schedules can be executed from the UI or CLI. Webhook and notification delivery remain a channel integration layer, not part of the core report generation contract.',
            'icon': 'calendar-clock',
            'bullets': [
                'UI: create schedules and run them immediately.',
                'CLI: process due schedules with flask run-report-schedules.',
            ],
        },
    ]


def get_current_status(
    report_counts: dict[str, int],
    storage_context: dict[str, Any],
    report_type_coverage: dict[str, Any],
) -> list[dict[str, str]]:
    kubernetes_coverage = report_type_coverage['kubernetes']

    return [
        {
            'label': 'Generated Reports',
            'value': str(report_counts['total']),
            'description': f'{report_counts["ready"]} ready, {report_counts["pending"]} in progress, {report_counts["archived"]} archived.',
            'tone': 'blue' if report_counts['total'] else 'gray',
            'icon': 'files',
        },
        {
            'label': 'KAORI Kubernetes Reports Coverage',
            'value': f'{kubernetes_coverage["available_count"]}/{kubernetes_coverage["total_count"]}',
            'description': 'Available infrastructure report types with implemented PDF contracts.',
            'tone': 'green',
            'icon': 'clipboard-check',
        },
        {
            'label': 'Storage Backend',
            'value': str(storage_context.get('display_status', 'Storage Review')),
            'description': str(storage_context.get('description', 'Report storage backend status is unavailable.')),
            'tone': str(storage_context.get('tone', 'amber')),
            'icon': 'hard-drive',
        },
        {
            'label': 'Template Library',
            'value': str(report_counts['custom_templates']),
            'description': 'Custom templates stored in addition to protected base templates.',
            'tone': 'blue' if report_counts['custom_templates'] else 'gray',
            'icon': 'layout-template',
        },
        {
            'label': 'Schedule Automation',
            'value': str(report_counts['active_schedules']),
            'description': f'{report_counts["schedules"]} total schedules, {report_counts["active_schedules"]} enabled for recurring generation.',
            'tone': 'green' if report_counts['active_schedules'] else 'gray',
            'icon': 'calendar-clock',
        },
        {
            'label': 'KAORI Server Reports Coverage',
            'value': 'Reserved',
            'description': 'Server/VM report types map to KAORI Server Reports, while HCI report types map to KAORI HCI Reports provider sources.',
            'tone': 'gray',
            'icon': 'server-cog',
        },
    ]


def get_reporting_operating_model(
    report_counts: dict[str, int],
    storage_context: dict[str, Any],
    report_type_coverage: dict[str, Any],
) -> dict[str, Any]:
    kubernetes_coverage = report_type_coverage['kubernetes']
    return {
        'title': 'Reporting Operating Model',
        'description': 'A concise view of how reports are produced, governed, stored, and prepared for future infrastructure domains.',
        'cards': [
            {
                'label': 'Protected base templates',
                'value': str(kubernetes_coverage['available_count']),
                'description': 'Base templates provide stable section contracts and cannot be edited or deleted directly.',
                'icon': 'shield-check',
                'tone': 'blue',
            },
            {
                'label': 'Custom templates',
                'value': str(report_counts['custom_templates']),
                'description': 'User-defined templates can clone base templates or select report sections for specific audiences.',
                'icon': 'copy-plus',
                'tone': 'purple',
            },
            {
                'label': 'Artifact storage',
                'value': str(storage_context.get('label', 'Storage')),
                'description': str(storage_context.get('description', 'Report storage backend status is unavailable.')),
                'icon': 'archive',
                'tone': str(storage_context.get('tone', 'amber')),
            },
            {
                'label': 'Delivery channels',
                'value': 'Coming Soon',
                'description': 'Webhook, email, and notification delivery are reserved as delivery-channel integrations on top of generated artifacts.',
                'icon': 'send-horizontal',
                'tone': 'gray',
            },
        ],
    }


def get_data_collection_status() -> list[dict[str, Any]]:
    return [
        {
            'title': 'Container Platform Data Collection',
            'status': 'Ready',
            'tone': 'blue',
            'icon': 'boxes',
            'items': [
                'Cluster, node, namespace, workload, pod, service, ingress, and storage inventory for container platforms.',
                'Prometheus-backed utilization, capacity, forecast, and top-consumer analytics for platform resources.',
                'Alertmanager and Prometheus alert/anomaly context for infrastructure reporting.',
            ],
        },
        {
            'title': 'Server & HCI Data Collection',
            'status': 'Reserved',
            'tone': 'gray',
            'icon': 'server-cog',
            'items': [
                'VM inventory, operating system, power state, placement, and ownership metadata.',
                'Hypervisor or HCI host utilization, datastore capacity, and cluster health signals.',
                'KAORI Server Reports and KAORI HCI Reports sections reuse the same template, schedule, and storage lifecycle.',
            ],
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
