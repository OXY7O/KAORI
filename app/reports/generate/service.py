from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from werkzeug.datastructures import ImmutableMultiDict, MultiDict

from app.common.celery_queue_health import get_queue_readiness
from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.inventory import NamespaceInventory
from app.models.report import Report
from app.models.user import User
from app.reports.catalog import (
    OUTPUT_FORMAT_OPTIONS,
    REPORT_TYPE_OPTIONS,
    REQUIRES_SELECTED_CLUSTER_REPORT_TYPES,
    get_allowed_output_formats,
    get_default_output_format,
    get_report_type_spec,
)
from app.reports.catalog import (
    normalize_report_type as normalize_catalog_report_type,
)
from app.reports.export.constants import DEFAULT_REPORT_DOMAIN, DEFAULT_REPORT_SOURCE_KIND
from app.reports.jobs.queue import get_reports_queue_name
from app.reports.storage.service import get_configured_storage_backend_name, get_report_storage_backend_status

PERIOD_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'snapshot',
        'label': 'Current Inventory Snapshot',
    },
    {
        'value': '24h',
        'label': 'Last 24 hours',
    },
    {
        'value': '7d',
        'label': 'Last 7 days',
    },
    {
        'value': '30d',
        'label': 'Last 30 days',
    },
    {
        'value': '90d',
        'label': 'Last 90 days',
    },
    {
        'value': 'month',
        'label': 'This month',
    },
]


def report_requires_selected_cluster(
    report_type: str,
) -> bool:
    return report_type in REQUIRES_SELECTED_CLUSTER_REPORT_TYPES


SECTION_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'executive_summary',
        'label': 'Executive Summary',
        'description': 'High-level report summary and key operational findings.',
    },
    {
        'value': 'executive_brief',
        'label': 'Executive Brief',
        'description': 'Current operational position, priority findings, decisions, and evidence scope.',
    },
    {
        'value': 'resource_posture',
        'label': 'Resource Posture',
        'description': 'CPU, memory, storage, pod, and node headroom posture.',
    },
    {
        'value': 'trend_forecast',
        'label': 'Trend & Forecast',
        'description': 'Historical direction, forecast pressure, confidence, and limitations.',
    },
    {
        'value': 'capacity_pressure',
        'label': 'Capacity Pressure',
        'description': 'Headroom, saturation risk, breach projection, and capacity actions.',
    },
    {
        'value': 'alerts_anomalies',
        'label': 'Alerts & Anomalies',
        'description': 'Active alerts, affected resources, anomalies, and response priorities.',
    },
    {
        'value': 'reporting_summary',
        'label': 'Reporting Summary',
        'description': 'Generation activity, schedules, storage readiness, and notes.',
    },
    {
        'value': 'inventory_snapshot',
        'label': 'Inventory Snapshot',
        'description': 'Committed cluster, node, workload, pod, and resource inventory.',
    },
    {
        'value': 'data_freshness_reliability',
        'label': 'Data Freshness & Reliability',
        'description': 'Source recency, completeness, reliability, and data-quality issues.',
    },
    {
        'value': 'recommendation_plan',
        'label': 'Recommendation Plan',
        'description': 'Evidence-backed actions with owners, target windows, and validation gates.',
    },
    {
        'value': 'methodology_evidence_boundary',
        'label': 'Methodology & Evidence Boundary',
        'description': 'Sources, methodology, inclusions, exclusions, and status language.',
    },
    {
        'value': 'analytics_summary',
        'label': 'Analytics Summary',
        'description': 'Overall analytics context and resource health summary.',
    },
    {
        'value': 'resource_snapshot',
        'label': 'Resource Snapshot',
        'description': 'Cluster resource posture at report generation time.',
    },
    {
        'value': 'cpu_utilization',
        'label': 'CPU Utilization',
        'description': 'CPU capacity, usage, and utilization pattern.',
    },
    {
        'value': 'memory_utilization',
        'label': 'Memory Utilization',
        'description': 'Memory capacity, usage, and utilization pattern.',
    },
    {
        'value': 'storage_utilization',
        'label': 'Storage Utilization',
        'description': 'Storage capacity, usage, available space, and utilization.',
    },
    {
        'value': 'pod_utilization',
        'label': 'Pod Utilization',
        'description': 'Pod allocation and pod capacity usage context.',
    },
    {
        'value': 'node_resource_detail',
        'label': 'Node Resource Detail',
        'description': 'Per-node resource detail and pressure context.',
    },
    {
        'value': 'worker_capacity_summary',
        'label': 'Worker Capacity Summary',
        'description': 'Schedulable worker node capacity summary.',
    },
    {
        'value': 'resource_allocation_headroom',
        'label': 'Resource Allocation & Headroom',
        'description': 'Available headroom and allocation efficiency.',
    },
    {
        'value': 'capacity_pressure_risk',
        'label': 'Capacity & Pressure Risk',
        'description': 'Capacity risk and node pressure indicators.',
    },
    {
        'value': 'storage_capacity',
        'label': 'Storage Capacity',
        'description': 'Storage capacity and allocation summary.',
    },
    {
        'value': 'filesystem_summary',
        'label': 'Filesystem Summary',
        'description': 'Node filesystem usage and available capacity.',
    },
    {
        'value': 'persistent_volume_summary',
        'label': 'Persistent Volume Summary',
        'description': 'Persistent volume allocation and usage context.',
    },
    {
        'value': 'persistent_volume_claims',
        'label': 'Persistent Volume Claims',
        'description': 'PVC requested, used, and free capacity summary.',
    },
    {
        'value': 'tenant_quota',
        'label': 'Tenant Quota',
        'description': 'Namespace quota, request, and limit summary.',
    },
    {
        'value': 'tenant_quota_summary',
        'label': 'Tenant Quota Summary',
        'description': 'Tenant quota posture and allocation context.',
    },
    {
        'value': 'workload_resource_mapping',
        'label': 'Workload Resource Mapping',
        'description': 'Workload requests, limits, and usage mapping.',
    },
    {
        'value': 'request_limit_coverage',
        'label': 'Request & Limit Coverage',
        'description': 'Workloads with or without configured requests and limits.',
    },
    {
        'value': 'namespace_breakdown',
        'label': 'Namespace Breakdown',
        'description': 'Namespace-level workload and resource summary.',
    },
    {
        'value': 'governance_findings',
        'label': 'Governance Findings',
        'description': 'Detected workload governance gaps, severity, and remediation filters.',
    },
    {
        'value': 'forecast_summary',
        'label': 'Forecast Summary',
        'description': 'Resource growth forecast overview.',
    },
    {
        'value': 'cpu_forecast',
        'label': 'CPU Forecast',
        'description': 'Projected CPU utilization trend.',
    },
    {
        'value': 'memory_forecast',
        'label': 'Memory Forecast',
        'description': 'Projected memory utilization trend.',
    },
    {
        'value': 'storage_forecast',
        'label': 'Storage Forecast',
        'description': 'Projected storage consumption trend.',
    },
    {
        'value': 'pod_forecast',
        'label': 'Pod Forecast',
        'description': 'Projected pod allocation trend.',
    },
    {
        'value': 'capacity_projection',
        'label': 'Capacity Projection',
        'description': 'Projected capacity risk and future pressure.',
    },
    {
        'value': 'top_namespace_consumers',
        'label': 'Top Namespace Consumers',
        'description': 'Namespaces with highest resource consumption.',
    },
    {
        'value': 'top_workload_consumers',
        'label': 'Top Workload Consumers',
        'description': 'Workloads with highest resource consumption.',
    },
    {
        'value': 'top_pod_consumers',
        'label': 'Top Pod Consumers',
        'description': 'Pods with highest resource consumption.',
    },
    {
        'value': 'resource_hotspots',
        'label': 'Resource Hotspots',
        'description': 'Resource concentration and noisy-neighbor context.',
    },
    {
        'value': 'active_alerts',
        'label': 'Active Alerts',
        'description': 'Current active alerts from alert sources.',
    },
    {
        'value': 'alert_severity_summary',
        'label': 'Alert Severity Summary',
        'description': 'Alert severity and impact summary.',
    },
    {
        'value': 'anomaly_context',
        'label': 'Anomaly Context',
        'description': 'Detected anomaly context and affected metrics.',
    },
    {
        'value': 'affected_resources',
        'label': 'Affected Resources',
        'description': 'Resources affected by alerts or anomalies.',
    },
    {
        'value': 'storage_risk',
        'label': 'Storage Risk',
        'description': 'Storage risk and capacity warning context.',
    },
    {
        'value': 'source_health',
        'label': 'Alert Source Health',
        'description': 'Alertmanager, Prometheus fallback, resolved source, and source confidence state.',
    },
    {
        'value': 'routing_grouping',
        'label': 'Alert Routing & Grouping',
        'description': 'Receiver groups, grouping keys, fingerprints, and namespace spread from Alertmanager context.',
    },
    {
        'value': 'silence_inhibition',
        'label': 'Silence & Inhibition Visibility',
        'description': 'Active silence impact, matched alerts, and inhibited alert context when Alertmanager metadata is available.',
    },
    {
        'value': 'ownership_runbook',
        'label': 'Ownership & Runbook Readiness',
        'description': 'Owner, runbook, and contact metadata coverage for operational response.',
    },
    {
        'value': 'incident_readiness',
        'label': 'Incident Readiness',
        'description': 'Incident response score derived from alert signals, source health, routing, silence, inhibition, and ownership readiness.',
    },
    {
        'value': 'forecast_risk_summary',
        'label': 'Forecast Risk Summary',
        'description': 'Forecast risk level, signal quality, and capacity planning attention areas.',
    },
    {
        'value': 'resource_trend_summary',
        'label': 'Resource Trend Summary',
        'description': 'CPU, memory, storage, and pod trend direction used by forecast analysis.',
    },
    {
        'value': 'forecast_projection',
        'label': 'Forecast Projection',
        'description': 'Projected resource pressure, forecast horizon, and estimated growth direction.',
    },
    {
        'value': 'threshold_eta',
        'label': 'Threshold ETA',
        'description': 'Estimated timing for threshold risk when forecast data is available.',
    },
    {
        'value': 'risk_overview',
        'label': 'Risk Overview',
        'description': 'High-level risk posture across analytics signals.',
    },
    {
        'value': 'inventory_assets',
        'label': 'Inventory Data',
        'description': 'Primary Excel table containing committed asset identities and fields.',
    },
    {
        'value': 'inventory_metadata',
        'label': 'Workbook Metadata',
        'description': 'Export scope, source, data cut-off, ownership, and workbook-standard metadata.',
    },
    {
        'value': 'inventory_field_dictionary',
        'label': 'Field Dictionary',
        'description': 'Column definitions, data types, sources, and missing-value rules.',
    },
    {
        'value': 'operational_recommendations',
        'label': 'Operational Recommendations',
        'description': 'Recommended actions based on report findings.',
    },
]


def _get_section_option_map() -> dict[str, dict[str, str]]:
    return {item['value']: item for item in SECTION_OPTIONS}


def _get_section_options_for_report_type(
    report_type: str,
) -> list[dict[str, str]]:
    section_option_map = _get_section_option_map()

    return [
        section_option_map[section]
        for section in _get_default_sections(
            report_type,
        )
        if section in section_option_map
    ]


def _get_section_options_by_report_type() -> dict[str, list[dict[str, str]]]:
    return {
        item['value']: _get_section_options_for_report_type(
            item['value'],
        )
        for item in REPORT_TYPE_OPTIONS
    }


def _get_selected_section_options(
    report_type: str,
    sections: list[str],
) -> list[dict[str, str]]:
    section_option_map = _get_section_option_map()
    allowed_sections = _get_allowed_sections_for_report_type(
        report_type,
    )

    return [
        section_option_map[section]
        for section in sections
        if section in allowed_sections and section in section_option_map
    ]


def _get_default_sections_by_report_type() -> dict[str, list[str]]:
    return {
        item['value']: list(
            item['default_sections'],
        )
        for item in REPORT_TYPE_OPTIONS
    }


def _get_allowed_sections_for_report_type(
    report_type: str,
) -> set[str]:
    return set(
        _get_default_sections(
            report_type,
        )
    )


def get_generate_report_payload(
    form_state: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    default_report_type = REPORT_TYPE_OPTIONS[0]['value']

    if form_state is None:
        form_state = build_default_form_state(
            report_type=default_report_type,
        )

    storage_context = _get_storage_generation_context()
    worker_context = get_queue_readiness(get_reports_queue_name())
    selected_report_type = _get_report_type_context(
        form_state['report_type'],
    )
    cluster_options = _get_cluster_options()
    namespace_options_by_cluster = _get_namespace_options_by_cluster()

    return {
        'page_title': 'Generate Report',
        'page_subtitle': ('Build a governed report from connected data, selected scope, and reusable sections.'),
        'clusters': cluster_options,
        'has_clusters': bool(cluster_options),
        'namespace_options_by_cluster': namespace_options_by_cluster,
        'selected_namespace_options': namespace_options_by_cluster.get(
            str(form_state.get('cluster_id') or ''),
            [],
        ),
        'report_type_options': REPORT_TYPE_OPTIONS,
        'period_options': PERIOD_OPTIONS,
        'output_format_options': OUTPUT_FORMAT_OPTIONS,
        'section_options': SECTION_OPTIONS,
        'section_options_by_report_type': _get_section_options_by_report_type(),
        'default_sections_by_report_type': _get_default_sections_by_report_type(),
        'selected_section_options': _get_selected_section_options(
            form_state['report_type'],
            form_state['sections'],
        ),
        'selected_report_type': selected_report_type,
        'single_cluster_required_report_types': sorted(
            REQUIRES_SELECTED_CLUSTER_REPORT_TYPES,
        ),
        'form_state': form_state,
        'preview_report_name': form_state['name'].strip() or build_default_report_name(form_state),
        'errors': errors or [],
        'storage_context': storage_context,
        'generation_allowed': bool(storage_context.get('ready', False)),
        'worker_context': worker_context,
    }


def create_report_request(
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
    user_id: int | None,
) -> tuple[bool, list[str], Report | None]:
    form_state = get_form_state_from_form(
        form,
    )

    errors = validate_form_state(
        form_state,
    )

    if errors:
        return False, errors, None

    storage_status = get_report_storage_backend_status()
    if not bool(storage_status.get('write_available', False)):
        return (
            False,
            [
                'Artifact storage is unavailable. Report metadata remains accessible, but new report generation is paused until storage connectivity is restored.'
            ],
            None,
        )

    cluster_id = _parse_cluster_id(
        form_state['cluster_id'],
    )

    report_name = form_state['name'].strip()

    if not report_name:
        report_name = build_default_report_name(
            form_state,
        )

    namespace = form_state['namespace'].strip() or None

    report = Report()
    report.name = report_name
    report.report_type = form_state['report_type']
    report.report_domain = DEFAULT_REPORT_DOMAIN
    report.source_kind = DEFAULT_REPORT_SOURCE_KIND
    report.cluster_id = cluster_id
    report.namespace = namespace
    report.period = form_state['period']
    report.output_format = form_state['output_format']
    report.status = 'requested'
    report.sections = form_state['sections']
    report.generated_by_id = user_id

    if user_id is not None:
        user = db.session.get(
            User,
            user_id,
        )

        if user is not None:
            report.generated_by_username_snapshot = user.username
            report.generated_by_display_name_snapshot = user.display_label
            report.generated_by_auth_source_snapshot = user.auth_source

    report.file_path = None
    report.file_size_bytes = None
    report.error_message = None

    db.session.add(
        report,
    )
    db.session.commit()

    return True, [], report


def build_default_form_state(
    *,
    report_type: str | None = None,
) -> dict[str, Any]:
    normalized_report_type = normalize_report_type(
        report_type,
    )

    return {
        'name': '',
        'cluster_id': '',
        'namespace': '',
        'report_type': normalized_report_type,
        'period': _get_default_period(normalized_report_type),
        'output_format': get_report_primary_output_format(normalized_report_type),
        'sections': _get_default_sections(
            normalized_report_type,
        ),
    }


def get_report_primary_output_format(report_type: str) -> str:
    return get_default_output_format(normalize_report_type(report_type))


def get_report_allowed_output_formats(report_type: str) -> tuple[str, ...]:
    return get_allowed_output_formats(normalize_report_type(report_type))


def normalize_report_type(
    value: str | None,
) -> str:
    return normalize_catalog_report_type(value)


def _get_report_type_context(
    report_type: str,
) -> dict[str, Any]:
    normalized_report_type = normalize_report_type(
        report_type,
    )

    for item in REPORT_TYPE_OPTIONS:
        if item['value'] == normalized_report_type:
            return {
                'value': item['value'],
                'label': item['label'],
                'description': item['description'],
                'icon': item['icon'],
                'section_count': len(
                    item['default_sections'],
                ),
                'family': str(item['family']),
                'primary_format': str(item['primary_format']),
                'allowed_formats': list(item['allowed_formats']),
                'requires_cluster': report_requires_selected_cluster(
                    item['value'],
                ),
                'cluster_scope_label': 'Selected Cluster Required',
            }

    fallback = REPORT_TYPE_OPTIONS[0]

    return {
        'value': fallback['value'],
        'label': fallback['label'],
        'description': fallback['description'],
        'icon': fallback['icon'],
        'section_count': len(
            fallback['default_sections'],
        ),
        'family': str(fallback['family']),
        'primary_format': str(fallback['primary_format']),
        'allowed_formats': list(fallback['allowed_formats']),
        'requires_cluster': report_requires_selected_cluster(
            fallback['value'],
        ),
        'cluster_scope_label': 'Selected Cluster Required',
    }


def _get_storage_generation_context() -> dict[str, Any]:
    try:
        backend_name = get_configured_storage_backend_name()
        backend_status = get_report_storage_backend_status(backend_name)
        is_ready = bool(backend_status.get('write_available', False))
        return {
            'backend': backend_name,
            'label': str(backend_status.get('label') or 'Report storage'),
            'status': str(backend_status.get('status') or 'Needs Review'),
            'tone': str(backend_status.get('tone') or ('blue' if is_ready else 'amber')),
            'description': str(backend_status.get('description') or ''),
            'ready': is_ready,
            'state': str(backend_status.get('state') or 'unknown'),
            'checked_at': backend_status.get('checked_at'),
            'source': str(backend_status.get('source') or 'direct'),
        }
    except Exception:
        return {
            'backend': 'unknown',
            'label': 'Storage backend',
            'status': 'Needs Review',
            'tone': 'amber',
            'description': 'Storage readiness could not be evaluated. Review Reports Storage and server logs.',
            'ready': False,
            'state': 'unknown',
            'checked_at': None,
            'source': 'fallback',
        }


def get_form_state_from_form(
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
) -> dict[str, Any]:
    report_type = normalize_report_type(
        form.get(
            'report_type',
            REPORT_TYPE_OPTIONS[0]['value'],
        )
    )

    sections = form.getlist(
        'sections',
    )

    if not sections:
        sections = _get_default_sections(
            report_type,
        )

    allowed_sections_for_report = _get_allowed_sections_for_report_type(
        report_type,
    )

    sections = [section for section in sections if section in allowed_sections_for_report]

    report_context = _get_report_type_context(report_type)
    if report_context.get('family') == 'inventory':
        sections = _get_default_sections(report_type)
    elif not sections:
        sections = _get_default_sections(
            report_type,
        )

    period = str(
        form.get(
            'period',
            _get_default_period(report_type),
        )
        or ''
    ).strip()
    if _get_default_period(report_type) == 'snapshot':
        period = 'snapshot'
    elif period == 'snapshot':
        period = '30d'

    return {
        'name': form.get(
            'name',
            '',
        ),
        'cluster_id': form.get(
            'cluster_id',
            '',
        ),
        'namespace': form.get(
            'namespace',
            '',
        ),
        'report_type': report_type,
        'period': period,
        'output_format': str(
            form.get('output_format', get_report_primary_output_format(report_type))
            or get_report_primary_output_format(report_type)
        )
        .strip()
        .lower(),
        'sections': sections,
    }


def validate_form_state(
    form_state: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    allowed_report_types = {item['value'] for item in REPORT_TYPE_OPTIONS}

    allowed_periods = {item['value'] for item in PERIOD_OPTIONS}

    allowed_output_formats = {item['value'] for item in OUTPUT_FORMAT_OPTIONS}

    allowed_sections = {item['value'] for item in SECTION_OPTIONS}

    if form_state['report_type'] not in allowed_report_types:
        errors.append(
            'Please select a valid report type.',
        )

    cluster_count = (
        db.session.scalar(
            select(func.count(Cluster.id)),
        )
        or 0
    )

    if cluster_count == 0:
        errors.append(
            'Add at least one Kubernetes cluster before creating reports or report schedules.',
        )

    if (
        report_requires_selected_cluster(
            form_state['report_type'],
        )
        and not form_state['cluster_id']
    ):
        errors.append(
            'A selected Kubernetes cluster is required for every report artifact.',
        )

    if form_state['period'] not in allowed_periods:
        errors.append(
            'Please select a valid report period.',
        )

    if form_state['output_format'] not in allowed_output_formats:
        errors.append(
            'Please select a valid output format.',
        )

    allowed_formats_for_report = get_report_allowed_output_formats(form_state['report_type'])
    if (
        form_state['output_format'] in allowed_output_formats
        and form_state['output_format'] not in allowed_formats_for_report
    ):
        allowed_label = ' or '.join(value.upper() for value in allowed_formats_for_report)
        errors.append(
            f'This report type supports only {allowed_label} output.',
        )

    if not form_state['sections']:
        errors.append(
            'Please select at least one report section.',
        )

    invalid_sections = [section for section in form_state['sections'] if section not in allowed_sections]

    if invalid_sections:
        errors.append(
            'One or more selected report sections are invalid.',
        )

    allowed_sections_for_report = _get_allowed_sections_for_report_type(
        form_state['report_type'],
    )

    incompatible_sections = [
        section for section in form_state['sections'] if section not in allowed_sections_for_report
    ]

    if incompatible_sections:
        errors.append(
            'One or more selected sections are not available for this report type.',
        )

    cluster_exists = None
    if form_state['cluster_id']:
        cluster_exists = db.session.scalar(
            select(
                Cluster.id,
            ).where(
                Cluster.id == form_state['cluster_id'],
            )
        )

        if cluster_exists is None:
            errors.append(
                'Please select a valid cluster.',
            )

    namespace = (form_state.get('namespace') or '').strip()
    if namespace and not form_state['cluster_id']:
        errors.append(
            'Select a Kubernetes cluster before choosing a namespace.',
        )
    elif namespace and cluster_exists is not None:
        namespace_query = filter_current_generation(
            NamespaceInventory.query,
            NamespaceInventory,
        ).filter(
            NamespaceInventory.cluster_id == form_state['cluster_id'],
            NamespaceInventory.namespace == namespace,
        )

        if namespace_query.with_entities(NamespaceInventory.id).first() is None:
            errors.append(
                'Please select a namespace available in the current inventory snapshot for this cluster.',
            )

    return errors


def _get_default_period(report_type: str) -> str:
    return 'snapshot' if get_report_type_spec(report_type).period_mode == 'snapshot' else '30d'


def build_default_report_name(
    form_state: dict[str, Any],
) -> str:
    report_type_label = _get_label_by_value(
        REPORT_TYPE_OPTIONS,
        form_state['report_type'],
    )

    period_label = _get_label_by_value(
        PERIOD_OPTIONS,
        form_state['period'],
    )

    return f'{report_type_label} - {period_label}'


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

    options: list[dict[str, str]] = []

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


def _get_namespace_options_by_cluster() -> dict[str, list[str]]:
    query = db.session.query(
        NamespaceInventory.cluster_id,
        NamespaceInventory.namespace,
    )
    query = filter_current_generation(
        query,
        NamespaceInventory,
    )
    rows = query.order_by(
        NamespaceInventory.cluster_id.asc(),
        NamespaceInventory.namespace.asc(),
    ).all()

    options: dict[str, list[str]] = {}
    for cluster_id, namespace in rows:
        cluster_key = str(cluster_id)
        options.setdefault(cluster_key, []).append(namespace)

    return options


def _parse_cluster_id(
    value: str,
) -> str | None:
    if not value:
        return None

    return value


def _get_default_sections(
    report_type: str,
) -> list[str]:
    for item in REPORT_TYPE_OPTIONS:
        if item['value'] == report_type:
            return list(
                item['default_sections'],
            )

    return [
        'executive_summary',
        'operational_recommendations',
    ]


def _get_label_by_value(
    options: list[dict[str, Any]],
    value: str,
) -> str:
    for option in options:
        if option['value'] == value:
            return option['label']

    return value
