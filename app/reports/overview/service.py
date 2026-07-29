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
        'name': 'Server Inventory Report',
        'description': (
            'Physical and virtual server inventory, ownership, operating system, lifecycle, '
            'and placement summary.'
        ),
        'icon': 'server',
    },
    {
        'name': 'Server Utilization Report',
        'description': 'CPU, memory, filesystem, and load behavior from server inventory and Node Exporter metrics.',
        'icon': 'activity',
    },
    {
        'name': 'Server Capacity Report',
        'description': (
            'Allocated versus consumed compute, memory, and storage with capacity risk '
            'and growth indicators.'
        ),
        'icon': 'gauge',
    },
    {
        'name': 'VM Inventory Report',
        'description': (
            'Virtual machine catalog, ownership, power state, operating system, CPU, memory, '
            'disk, and placement summary.'
        ),
        'icon': 'monitor-cog',
    },
    {
        'name': 'VM Placement & Risk Report',
        'description': (
            'Placement quality, affinity context, availability readiness, and concentration '
            'risk across host groups.'
        ),
        'icon': 'git-fork',
    },
]

HCI_REPORT_TYPE_COVERAGE = [
    {
        'name': 'HCI Cluster Health Report',
        'description': (
            'Cluster posture, host availability, storage pool status, replication signals, '
            'and operational risk.'
        ),
        'icon': 'network',
    },
    {
        'name': 'HCI Host Utilization Report',
        'description': (
            'Hypervisor host usage, contention indicators, consolidation opportunity, '
            'and noisy-neighbor signals.'
        ),
        'icon': 'server-cog',
    },
    {
        'name': 'Datastore & Volume Report',
        'description': (
            'Datastore utilization, free capacity, thin provisioning exposure, '
            'and storage pressure overview.'
        ),
        'icon': 'database',
    },
    {
        'name': 'HCI VM Placement Report',
        'description': 'VM distribution, affinity, resilience, and placement risk from the connected HCI provider API.',
        'icon': 'waypoints',
    },
]


SCHEDULE_STATUS = 'Ready'


def get_reports_overview_payload() -> dict[str, Any]:
    report_counts = get_report_counts()
    storage_context = get_storage_context()
    report_type_coverage = get_report_type_coverage()
    pipeline_status = get_pipeline_status(storage_context)
    current_status = get_current_status(report_counts, storage_context, report_type_coverage)

    return {
        'page_title': 'Reports Overview',
        'page_subtitle': 'Generate governed infrastructure reports from connected KAORI data sources.',
        'selected_cluster_label': 'All Infrastructure Scopes',
        'report_engine_status': 'Ready',
        'storage_status': storage_context['display_status'],
        'summary_cards': get_summary_cards(report_counts),
        'recent_reports': get_recent_reports(),
        'report_type_coverage': report_type_coverage,
        'report_type_summary': get_report_type_summary(report_type_coverage),
        'report_architecture_context': get_report_architecture_context(),
        'pipeline_status': pipeline_status,
        'pipeline_summary': get_pipeline_summary(pipeline_status),
        'reporting_context': get_reporting_context(storage_context),
        'current_status': current_status,
        'current_status_summary': get_current_status_summary(current_status),
        'reporting_operating_model': get_reporting_operating_model(
            report_counts, storage_context, report_type_coverage
        ),
        'data_collection_status': get_data_collection_status(storage_context),
        'related_information': get_related_information(),
        'storage_context': storage_context,
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
    return [
        {
            'label': 'Total Reports',
            'value': str(report_counts['total']),
            'caption': 'All Report Records',
            'icon': 'files',
            'tone': 'blue',
        },
        {
            'label': 'Generated This Month',
            'value': str(report_counts['generated_this_month']),
            'caption': 'Reports Created This Month',
            'icon': 'calendar-days',
            'tone': 'green',
        },
        {
            'label': 'Ready Reports',
            'value': str(report_counts['ready']),
            'caption': 'Available for Download',
            'icon': 'check-circle-2',
            'tone': 'purple',
        },
        {
            'label': 'Enabled Schedules',
            'value': str(report_counts['active_schedules']),
            'caption': 'Enabled Recurring Definitions',
            'icon': 'calendar-clock',
            'tone': 'purple',
        },
    ]


def get_recent_reports(limit: int = 5) -> list[dict[str, Any]]:
    reports = db.session.scalars(select(Report).order_by(Report.created_at.desc()).limit(limit)).all()

    return [serialize_recent_report(report) for report in reports]


def serialize_recent_report(report: Report) -> dict[str, Any]:
    status = str(report.status or 'requested').lower()
    report_type_option = next(
        (
            option
            for option in REPORT_TYPE_OPTIONS
            if str(option.get('value', '')) == str(report.report_type or '')
        ),
        {},
    )

    return {
        'id': report.id,
        'name': report.name,
        'report_type': report.report_type,
        'report_type_label': format_report_type(report.report_type),
        'icon': str(report_type_option.get('icon', 'file-text')),
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
                'tone': 'normal' if is_ready else 'unknown',
            }
        )

    server_items = [
        {**item, 'status': 'Planned', 'tone': 'info'}
        for item in SERVER_REPORT_TYPE_COVERAGE
    ]
    hci_items = [
        {**item, 'status': 'Reserved', 'tone': 'unknown'}
        for item in HCI_REPORT_TYPE_COVERAGE
    ]

    domains = [
        {
            'key': 'kubernetes',
            'label': 'Kubernetes Reports',
            'description': (
                'Available report contracts backed by Kubernetes inventory, Prometheus metrics, '
                'and Alertmanager context.'
            ),
            'icon': 'boxes',
            'status': 'Available',
            'tone': 'normal',
            'items': kubernetes_items,
            'available_count': sum(1 for item in kubernetes_items if item['status'] == 'Available'),
            'total_count': len(kubernetes_items),
        },
        {
            'key': 'server',
            'label': 'Server & VM Reports',
            'description': (
                'Planned report contracts for physical servers, virtual machines, '
                'and Node Exporter signals.'
            ),
            'icon': 'server-cog',
            'status': 'Planned',
            'tone': 'info',
            'items': server_items,
            'available_count': 0,
            'total_count': len(server_items),
        },
        {
            'key': 'hci',
            'label': 'HCI Reports',
            'description': (
                'Reserved report contracts for HCI clusters, hosts, datastores, '
                'and VM placement from provider APIs.'
            ),
            'icon': 'network',
            'status': 'Reserved',
            'tone': 'unknown',
            'items': hci_items,
            'available_count': 0,
            'total_count': len(hci_items),
        },
    ]

    return {
        'domains': domains,
        'available_count': sum(domain['available_count'] for domain in domains),
        'total_count': sum(domain['total_count'] for domain in domains),
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


def get_report_type_summary(report_type_coverage: dict[str, Any]) -> dict[str, str]:
    available = int(report_type_coverage.get('available_count', 0))
    total = int(report_type_coverage.get('total_count', 0))
    return {
        'available': str(available),
        'total': str(total),
        'label': f'{available} Available Types',
        'description': f'{total} report contracts across current and future infrastructure domains.',
    }


def get_pipeline_status(storage_context: dict[str, Any]) -> list[dict[str, str]]:
    storage_tone = 'normal' if str(storage_context.get('tone')) == 'green' else 'warning'

    return [
        {
            'name': 'Source Collection',
            'description': (
                'Connected infrastructure integrations provide inventory, metrics, alerts, '
                'and source metadata.'
            ),
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'database-zap',
        },
        {
            'name': 'Scope & Template Contract',
            'description': (
                'The request stores audience, scope, report type, selected sections, output format, '
                'and owner context.'
            ),
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'layout-template',
        },
        {
            'name': 'Report Generation',
            'description': (
                'The export engine builds a standalone PDF with reader guidance, metadata, evidence, '
                'and selected sections.'
            ),
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'file-check-2',
        },
        {
            'name': 'Artifact Storage',
            'description': str(storage_context.get('description', 'Report storage backend status is unavailable.')),
            'status': str(storage_context.get('display_status', 'Storage Review')),
            'tone': storage_tone,
            'icon': 'hard-drive',
        },
        {
            'name': 'Schedule Automation',
            'description': (
                'Recurring generation is available through saved schedules, Run Now, '
                'and the schedule worker.'
            ),
            'status': SCHEDULE_STATUS,
            'tone': 'normal',
            'icon': 'calendar-clock',
        },
        {
            'name': 'Delivery Channels',
            'description': (
                'Email, webhook, and notification delivery remain planned channel integrations '
                'over generated artifacts.'
            ),
            'status': 'Planned',
            'tone': 'info',
            'icon': 'send-horizontal',
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


def get_reporting_context(storage_context: dict[str, Any]) -> list[dict[str, Any]]:
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
                'storage, and future provider domains.'
            ),
        },
        {
            'title': 'Governed Artifact Lifecycle',
            'description': (
                f'Generated PDFs use the active {storage_context["active_detail"]} backend with '
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
                'Manual generation and recurring schedules are available now; notification and webhook '
                'channels can be added as separate delivery integrations.'
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
) -> list[dict[str, str]]:
    type_summary = get_report_type_summary(report_type_coverage)
    storage_tone = 'normal' if str(storage_context.get('tone')) == 'green' else 'warning'

    return [
        {
            'label': 'Report Engine',
            'value': 'Ready',
            'description': 'Manual generation and PDF export contracts are available.',
            'tone': 'normal',
            'icon': 'file-check-2',
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
) -> dict[str, Any]:
    type_summary = get_report_type_summary(report_type_coverage)
    return {
        'title': 'Reporting Operating Model',
        'description': 'How KAORI composes, governs, stores, and automates infrastructure reports.',
        'cards': [
            {
                'label': 'Compose from Integrations',
                'value': type_summary['available'],
                'description': (
                    'Available report types are populated from connected and validated '
                    'infrastructure sources.'
                ),
                'icon': 'plug-zap',
                'tone': 'normal',
            },
            {
                'label': 'Govern with Templates',
                'value': str(report_counts['custom_templates']),
                'description': (
                    'Protected base templates and custom templates define sections, audience, '
                    'and document structure.'
                ),
                'icon': 'layout-template',
                'tone': 'info',
            },
            {
                'label': 'Store as Artifacts',
                'value': str(storage_context.get('label', 'Storage')),
                'description': (
                    'Generated PDFs follow one naming, archive, and retention contract across '
                    'supported storage backends.'
                ),
                'icon': 'archive',
                'tone': 'normal' if str(storage_context.get('tone')) == 'green' else 'warning',
            },
            {
                'label': 'Automate and Deliver',
                'value': str(report_counts['active_schedules']),
                'description': (
                    'Schedules are available now; email, webhook, and notification channels '
                    'remain planned integrations.'
                ),
                'icon': 'send-horizontal',
                'tone': 'info',
            },
        ],
    }


def get_data_collection_status(storage_context: dict[str, Any]) -> list[dict[str, Any]]:
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
                'Cluster, node, namespace, workload, pod, service, ingress, storage, '
                'and configuration inventory.'
            ),
        },
        {
            'stage': 'ready',
            'stage_label': 'Ready Now',
            'name': 'Prometheus / Thanos',
            'category': 'Metrics Source',
            'status': 'Ready',
            'tone': 'normal',
            'icon': 'activity',
            'description': (
                'Utilization, capacity, storage, workload, forecast, and top-consumer evidence '
                'for report sections.'
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
                'Local report artifact storage using the shared naming, archive, download, '
                'and retention model.'
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
                'AWS S3, MinIO, or another S3-compatible backend for generated reports '
                'and operational evidence.'
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
                'Physical server and VM inventory combined with Node Exporter metrics '
                'for server report families.'
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
                'External secret, credential, and access-policy evidence for future '
                'security-focused reports.'
            ),
        },
        {
            'stage': 'planned',
            'stage_label': 'Planned',
            'name': 'Email, Webhook & Notifications',
            'category': 'Delivery Channel',
            'status': 'Planned',
            'tone': 'info',
            'icon': 'send-horizontal',
            'description': (
                'Delivery integrations for distributing completed reports after artifact '
                'generation succeeds.'
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
