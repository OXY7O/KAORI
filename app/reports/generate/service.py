from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from werkzeug.datastructures import ImmutableMultiDict, MultiDict

from app.extensions import db
from app.models.cluster import Cluster
from app.models.report import Report
from app.models.user import User
from app.reports.export.constants import (
    DEFAULT_REPORT_DOMAIN,
    DEFAULT_REPORT_SOURCE_KIND,
    REAL_DATA_REPORT_TYPES,
    REAL_DATA_SECTION_MAP,
    REPORT_DOMAIN_DESCRIPTIONS,
    REPORT_DOMAIN_LABELS,
    SOURCE_KIND_LABELS,
)
from app.reports.storage.health import build_local_storage_health, build_s3_storage_health
from app.reports.storage.service import get_configured_storage_backend_name

REPORT_TYPE_OPTIONS: list[dict[str, Any]] = [
    {
        'value': 'analytics_overview',
        'label': 'Analytics Overview Report',
        'description': 'High-level analytics summary across utilization, capacity, forecast, and alerts.',
        'icon': 'layout-dashboard',
        'default_sections': [
            'executive_summary',
            'analytics_summary',
            'resource_snapshot',
            'risk_overview',
            'operational_recommendations',
        ],
    },
    {
        'value': 'resource_utilization',
        'label': 'Resource Utilization Report',
        'description': 'CPU, memory, storage, pod utilization, and node resource detail.',
        'icon': 'activity',
        'default_sections': [
            'executive_summary',
            'cpu_utilization',
            'memory_utilization',
            'storage_utilization',
            'pod_utilization',
            'node_resource_detail',
            'operational_recommendations',
        ],
    },
    {
        'value': 'capacity_analysis',
        'label': 'Capacity Analysis Report',
        'description': 'Worker capacity, allocation, headroom, and pressure risk.',
        'icon': 'database',
        'default_sections': [
            'executive_summary',
            'worker_capacity_summary',
            'resource_allocation_headroom',
            'capacity_pressure_risk',
            'operational_recommendations',
        ],
    },
    {
        'value': 'storage_analysis',
        'label': 'Storage Analysis Report',
        'description': 'Filesystem, persistent volume, PVC, capacity, usage, and free space summary.',
        'icon': 'hard-drive',
        'default_sections': [
            'executive_summary',
            'filesystem_summary',
            'persistent_volume_summary',
            'persistent_volume_claims',
            'storage_risk',
            'operational_recommendations',
        ],
    },
    {
        'value': 'workload_analysis',
        'label': 'Workload Analysis Report',
        'description': 'Workload resource requests, limits, mapping, and namespace resource behavior.',
        'icon': 'boxes',
        'default_sections': [
            'executive_summary',
            'tenant_quota_summary',
            'request_limit_coverage',
            'workload_resource_mapping',
            'governance_findings',
            'operational_recommendations',
        ],
    },
    {
        'value': 'resource_forecast',
        'label': 'Resource Forecast Report',
        'description': 'Forecast CPU, memory, storage, and pod growth using historical metrics.',
        'icon': 'line-chart',
        'default_sections': [
            'executive_summary',
            'forecast_summary',
            'cpu_forecast',
            'memory_forecast',
            'storage_forecast',
            'pod_forecast',
            'capacity_projection',
            'operational_recommendations',
        ],
    },
    {
        'value': 'top_consumers',
        'label': 'Top Consumers Report',
        'description': 'Top namespaces, workloads, and pods consuming cluster resources.',
        'icon': 'users',
        'default_sections': [
            'executive_summary',
            'top_namespace_consumers',
            'top_workload_consumers',
            'top_pod_consumers',
            'resource_hotspots',
            'operational_recommendations',
        ],
    },
    {
        'value': 'alerts_anomalies',
        'label': 'Alerts & Anomalies Report',
        'description': 'Alert visibility, anomaly context, source health, routing, ownership, incident readiness, and recommendation notes.',
        'icon': 'triangle-alert',
        'default_sections': [
            'executive_summary',
            'active_alerts',
            'alert_severity_summary',
            'source_health',
            'routing_grouping',
            'silence_inhibition',
            'ownership_runbook',
            'incident_readiness',
            'anomaly_context',
            'affected_resources',
            'operational_recommendations',
        ],
    },
]

PERIOD_OPTIONS: list[dict[str, str]] = [
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

OUTPUT_FORMAT_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'pdf',
        'label': 'PDF',
    },
]


SINGLE_CLUSTER_REQUIRED_REPORT_TYPES = {
    'resource_utilization',
    'capacity_analysis',
    'storage_analysis',
    'workload_analysis',
    'resource_forecast',
    'top_consumers',
    'alerts_anomalies',
}


def report_requires_specific_cluster(
    report_type: str,
) -> bool:
    return report_type in SINGLE_CLUSTER_REQUIRED_REPORT_TYPES


SECTION_OPTIONS: list[dict[str, str]] = [
    {
        'value': 'executive_summary',
        'label': 'Executive Summary',
        'description': 'High-level report summary and key operational findings.',
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
    selected_report_type = _get_report_type_context(
        form_state['report_type'],
    )
    cluster_options = _get_cluster_options()

    return {
        'page_title': 'Generate Report',
        'page_subtitle': (
            'Configure scope, source domain, period, and selected sections before creating standalone infrastructure report requests.'
        ),
        'clusters': cluster_options,
        'has_clusters': len(cluster_options) > 1,
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
            SINGLE_CLUSTER_REQUIRED_REPORT_TYPES,
        ),
        'form_state': form_state,
        'errors': errors or [],
        'readiness': _get_generation_readiness(
            storage_context,
        ),
        'storage_context': storage_context,
        'data_source_context': _get_data_source_context(),
        'report_architecture_context': _get_report_architecture_context(),
        'report_type_guide_groups': _get_report_type_guide_groups(),
        'report_output_readiness': _get_report_output_readiness(),
        'recommended_actions': _get_recommended_actions(),
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
        'period': '30d',
        'output_format': 'pdf',
        'sections': _get_default_sections(
            normalized_report_type,
        ),
    }


def normalize_report_type(
    value: str | None,
) -> str:
    allowed_report_types = {item['value'] for item in REPORT_TYPE_OPTIONS}
    normalized_value = (value or REPORT_TYPE_OPTIONS[0]['value']).strip()

    if normalized_value not in allowed_report_types:
        return REPORT_TYPE_OPTIONS[0]['value']

    return normalized_value


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
                'requires_cluster': report_requires_specific_cluster(
                    item['value'],
                ),
                'cluster_scope_label': 'Specific cluster required'
                if report_requires_specific_cluster(
                    item['value'],
                )
                else 'All clusters supported',
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
        'requires_cluster': report_requires_specific_cluster(
            fallback['value'],
        ),
        'cluster_scope_label': 'Specific cluster required'
        if report_requires_specific_cluster(
            fallback['value'],
        )
        else 'All clusters supported',
    }


def _get_storage_generation_context() -> dict[str, Any]:
    try:
        backend_name = get_configured_storage_backend_name()

        if backend_name == 's3':
            s3_health = build_s3_storage_health()
            is_ready = bool(
                s3_health.get(
                    'configuration_complete',
                    False,
                )
            )

            return {
                'backend': backend_name,
                'label': 'S3-compatible storage',
                'status': 'Ready' if is_ready else 'Needs Review',
                'tone': 'blue' if is_ready else 'amber',
                'description': 'Generated PDFs will be stored with s3: object references.'
                if is_ready
                else 'S3 storage is selected but bucket/dependency configuration needs review.',
                'ready': is_ready,
            }

        local_health = build_local_storage_health()
        is_ready = bool(
            local_health.get(
                'root_writable',
                False,
            )
        )

        return {
            'backend': 'local',
            'label': 'Local filesystem',
            'status': 'Ready' if is_ready else 'Needs Review',
            'tone': 'blue' if is_ready else 'amber',
            'description': 'Generated PDFs will be stored with local: object references.'
            if is_ready
            else 'Local storage is selected but the report storage root needs write permission review.',
            'ready': is_ready,
        }
    except Exception as exc:
        return {
            'backend': 'unknown',
            'label': 'Storage backend',
            'status': 'Needs Review',
            'tone': 'amber',
            'description': f'Storage readiness could not be evaluated: {exc}',
            'ready': False,
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

    if not sections:
        sections = _get_default_sections(
            report_type,
        )

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
        'period': form.get(
            'period',
            '30d',
        ),
        'output_format': form.get(
            'output_format',
            'pdf',
        ),
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
        report_requires_specific_cluster(
            form_state['report_type'],
        )
        and not form_state['cluster_id']
    ):
        errors.append(
            'This report type requires a specific cluster. Please select a cluster before generating the report.',
        )

    if form_state['period'] not in allowed_periods:
        errors.append(
            'Please select a valid report period.',
        )

    if form_state['output_format'] not in allowed_output_formats:
        errors.append(
            'Please select a valid output format.',
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

    return errors


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

    options = [
        {
            'value': '',
            'label': 'All Clusters',
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


def _get_generation_readiness(
    storage_context: dict[str, Any],
) -> list[dict[str, str]]:
    storage_tone = str(
        storage_context.get(
            'tone',
            'amber',
        )
    )

    return [
        {
            'label': 'Report request record',
            'description': 'Generate action creates a report request record with status Requested.',
            'status': 'Ready',
            'tone': 'blue',
        },
        {
            'label': 'PDF export engine',
            'description': 'Generated Reports can render and download structured PDF output for supported report types.',
            'status': 'Ready',
            'tone': 'blue',
        },
        {
            'label': 'Storage backend',
            'description': str(
                storage_context.get(
                    'description',
                    'Storage backend needs review.',
                )
            ),
            'status': str(
                storage_context.get(
                    'status',
                    'Needs Review',
                )
            ),
            'tone': storage_tone,
        },
        {
            'label': 'Scheduled generation',
            'description': 'Report schedules can reuse this generation contract through Run now or the CLI worker.',
            'status': 'Ready',
            'tone': 'blue',
        },
    ]


def _get_data_source_context() -> list[str]:
    return [
        'KubeReport report types currently use Kubernetes inventory and analytics data as the primary source domain.',
        'ServerReport covers server/VM inventory with Node Exporter metrics, while HCIReport covers HCI provider API data.',
        'Generate creates a report request first; PDF rendering and artifact download happen from Generated Reports.',
        'Metrics-backed real-data reports require a specific source scope when the report type depends on one selected cluster or infrastructure domain.',
        'PDF artifacts use the active Reports Storage backend with local: or s3: storage references.',
    ]


def _get_report_architecture_context() -> dict[str, Any]:
    return {
        'current_domain': DEFAULT_REPORT_DOMAIN,
        'current_domain_label': REPORT_DOMAIN_LABELS.get(DEFAULT_REPORT_DOMAIN, 'KubeReport'),
        'current_source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'current_source_label': SOURCE_KIND_LABELS.get(DEFAULT_REPORT_SOURCE_KIND, 'Kubernetes'),
        'description': (
            'The report generator is domain-aware. KubeReport currently owns container platform reports, '
            'while ServerReport and HCIReport separate server/VM and HCI report families. '
            'Both domains share the same request, template, schedule, PDF, and artifact lifecycle.'
        ),
        'capabilities': [
            {
                'label': 'Shared report lifecycle',
                'description': 'Generate, Generated Reports, Templates, Schedules, and Storage use the same lifecycle contract across report families.',
                'icon': 'workflow',
            },
            {
                'label': 'Protected base templates',
                'description': 'System templates define the supported report types. Users customize by cloning templates or selecting report sections.',
                'icon': 'shield-check',
            },
            {
                'label': 'Domain-aware storage',
                'description': 'Artifacts are stored with domain and source prefixes so KubeReport, ServerReport, and HCIReport files do not mix.',
                'icon': 'archive',
            },
        ],
        'domains': [
            {
                'value': domain,
                'label': label,
                'description': REPORT_DOMAIN_DESCRIPTIONS.get(domain, ''),
                'status': 'Ready' if domain == DEFAULT_REPORT_DOMAIN else 'Reserved',
            }
            for domain, label in REPORT_DOMAIN_LABELS.items()
        ],
    }


def _get_report_type_guide_groups() -> list[dict[str, Any]]:
    kubereport_items = [
        {
            'label': 'Analytics Overview',
            'description': 'High-level summary for analytics landing page information.',
            'icon': 'layout-dashboard',
        },
        {
            'label': 'Resource Utilization',
            'description': 'CPU, memory, storage, pod, and node usage details.',
            'icon': 'activity',
        },
        {
            'label': 'Capacity Analysis',
            'description': 'Worker capacity, headroom, allocation, and pressure risk information.',
            'icon': 'database',
        },
        {
            'label': 'Storage Analysis',
            'description': 'Filesystem, PV, PVC, used/free capacity, and storage risk.',
            'icon': 'hard-drive',
        },
        {
            'label': 'Workload Analysis',
            'description': 'Workload requests, limits, quota, and namespace mapping.',
            'icon': 'boxes',
        },
        {
            'label': 'Resource Forecast',
            'description': 'Future resource growth and projected utilization.',
            'icon': 'line-chart',
        },
        {
            'label': 'Top Consumers',
            'description': 'Highest resource consuming namespaces, workloads, and pods.',
            'icon': 'users',
        },
        {
            'label': 'Alerts & Anomalies',
            'description': 'Alert visibility, source health, routing context, ownership readiness, incident readiness, and recommendations.',
            'icon': 'triangle-alert',
        },
    ]

    serverreport_items = [
        {
            'label': 'VM Inventory Report',
            'description': 'Reserved report type for VM catalog, ownership, operating system, allocation, and lifecycle state.',
            'icon': 'server',
            'status': 'Reserved',
        },
        {
            'label': 'VM Capacity Report',
            'description': 'Reserved report type for VM CPU, memory, disk allocation, utilization, and capacity pressure.',
            'icon': 'gauge',
            'status': 'Reserved',
        },
        {
            'label': 'HCI Cluster Health Report',
            'description': 'Reserved report type for hyperconverged cluster health, node condition, fault domains, and resilience.',
            'icon': 'network',
            'status': 'Reserved',
        },
        {
            'label': 'Datastore & Volume Report',
            'description': 'Reserved report type for datastore capacity, volume allocation, free space, and growth risk.',
            'icon': 'database',
            'status': 'Reserved',
        },
        {
            'label': 'Host Utilization Report',
            'description': 'Reserved report type for physical host utilization, consolidation, imbalance, and headroom.',
            'icon': 'cpu',
            'status': 'Reserved',
        },
        {
            'label': 'VM Placement & Risk Report',
            'description': 'Reserved report type for VM placement, anti-affinity, host dependency, and operational risk.',
            'icon': 'git-branch',
            'status': 'Reserved',
        },
    ]

    for item in kubereport_items:
        item['status'] = 'Default system template'

    return [
        {
            'key': 'kubereport',
            'label': 'KubeReport',
            'description': 'Container platform report types backed by Kubernetes inventory and analytics data.',
            'items': kubereport_items,
        },
        {
            'key': 'serverreport',
            'label': 'ServerReport',
            'description': 'Reserved server, VM, and HCI report types for the future infrastructure inventory domain.',
            'items': serverreport_items,
        },
    ]


def _get_report_output_readiness() -> list[dict[str, Any]]:
    section_option_values = {item['value'] for item in SECTION_OPTIONS}

    rows: list[dict[str, Any]] = []

    for report_type in REPORT_TYPE_OPTIONS:
        value = str(
            report_type.get(
                'value',
                '',
            )
            or ''
        )
        default_sections = [
            str(
                section,
            )
            for section in report_type.get(
                'default_sections',
                [],
            )
        ]
        real_sections = REAL_DATA_SECTION_MAP.get(
            value,
            set(),
        )
        missing_section_options = [section for section in default_sections if section not in section_option_values]
        missing_renderer_contract = [section for section in default_sections if section not in real_sections]
        is_real_data = value in REAL_DATA_REPORT_TYPES
        is_ready = is_real_data and not missing_section_options and not missing_renderer_contract

        rows.append(
            {
                'label': str(
                    report_type.get(
                        'label',
                        value,
                    )
                ),
                'report_type': value,
                'scope': 'Specific cluster'
                if report_requires_specific_cluster(
                    value,
                )
                else 'All clusters',
                'sections': len(
                    default_sections,
                ),
                'renderer': 'Real-data PDF output' if is_real_data else 'Structured PDF output',
                'status': 'Ready' if is_ready else 'Review',
                'tone': 'blue' if is_ready else 'amber',
                'note': 'Selected default sections are supported by the PDF output renderer.'
                if is_ready
                else 'Some sections need output mapping review before this report type is considered fully ready.',
                'missing_sections': missing_section_options,
                'missing_renderer_contract': missing_renderer_contract,
            }
        )

    return rows


def _get_recommended_actions() -> list[dict[str, str]]:
    return [
        {
            'label': 'Start with Analytics Overview',
            'description': 'Use Analytics Overview as the first end-to-end validation because it supports All Clusters.',
            'href': '/reports/generate?report_type=analytics_overview',
        },
        {
            'label': 'Use a specific cluster for Prometheus-backed reports',
            'description': 'Utilization, capacity, storage, workload, forecast, top consumers, and alerts reports require one selected cluster.',
            'href': '#report-configuration',
        },
        {
            'label': 'Review generated records',
            'description': 'After submit, open Generated Reports to render PDF, download, archive, or restore report artifacts.',
            'href': '/reports/generated',
        },
        {
            'label': 'Verify storage readiness',
            'description': 'Open Reports Storage to verify local/S3 readiness before relying on generated artifacts.',
            'href': '/reports/storage',
        },
    ]
