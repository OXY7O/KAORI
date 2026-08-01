from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from werkzeug.datastructures import ImmutableMultiDict, MultiDict

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.inventory import NamespaceInventory
from app.models.report import Report
from app.models.user import User
from app.reports.export.constants import (
    ANALYTICS_OVERVIEW_SECTION_KEYS,
    DEFAULT_REPORT_DOMAIN,
    DEFAULT_REPORT_SOURCE_KIND,
)
from app.reports.storage.health import build_local_storage_health, build_s3_storage_health
from app.reports.storage.service import get_configured_storage_backend_name

REPORT_TYPE_OPTIONS: list[dict[str, Any]] = [
    {
        'value': 'analytics_overview',
        'label': 'Analytics Overview Report',
        'description': 'High-level analytics summary across utilization, capacity, forecast, and alerts.',
        'icon': 'layout-dashboard',
        'default_sections': list(ANALYTICS_OVERVIEW_SECTION_KEYS),
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

for report_type_option in REPORT_TYPE_OPTIONS:
    report_type_option['family'] = 'analytics'

_INVENTORY_REPORT_SECTIONS = [
    'executive_summary',
    'inventory_summary',
    'inventory_distribution',
    'inventory_assets',
    'operational_recommendations',
]

REPORT_TYPE_OPTIONS.extend(
    [
        {
            'value': 'node_inventory',
            'label': 'Node Inventory Report',
            'description': 'Node asset register covering role, readiness, platform capacity, and addresses.',
            'icon': 'server-cog',
            'family': 'inventory',
            'default_sections': list(_INVENTORY_REPORT_SECTIONS),
        },
        {
            'value': 'namespace_inventory',
            'label': 'Namespace Inventory Report',
            'description': 'Namespace asset register covering status, controls, and service account posture.',
            'icon': 'folder-tree',
            'family': 'inventory',
            'default_sections': list(_INVENTORY_REPORT_SECTIONS),
        },
        {
            'value': 'workload_inventory',
            'label': 'Workload Inventory Report',
            'description': 'Workload asset register covering kind, readiness, runtime status, and update strategy.',
            'icon': 'boxes',
            'family': 'inventory',
            'default_sections': list(_INVENTORY_REPORT_SECTIONS),
        },
        {
            'value': 'pod_inventory',
            'label': 'Pod Inventory Report',
            'description': 'Pod asset register covering phase, readiness, placement, and restart count.',
            'icon': 'box',
            'family': 'inventory',
            'default_sections': list(_INVENTORY_REPORT_SECTIONS),
        },
        {
            'value': 'service_inventory',
            'label': 'Service Inventory Report',
            'description': 'Service asset register covering type, network exposure, ports, and addresses.',
            'icon': 'waypoints',
            'family': 'inventory',
            'default_sections': list(_INVENTORY_REPORT_SECTIONS),
        },
        {
            'value': 'ingress_inventory',
            'label': 'Ingress Inventory Report',
            'description': 'Ingress asset register covering class, host, address, and TLS exposure.',
            'icon': 'route',
            'family': 'inventory',
            'default_sections': list(_INVENTORY_REPORT_SECTIONS),
        },
        {
            'value': 'storage_inventory',
            'label': 'Storage Inventory Report',
            'description': 'Storage asset register covering StorageClasses, PVs, PVCs, capacity, and binding state.',
            'icon': 'database-zap',
            'family': 'inventory',
            'default_sections': list(_INVENTORY_REPORT_SECTIONS),
        },
    ]
)

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
        'value': 'inventory_summary',
        'label': 'Inventory Summary',
        'description': 'Snapshot totals, selected scope, status coverage, and collection time.',
    },
    {
        'value': 'inventory_distribution',
        'label': 'Asset Distribution',
        'description': 'Asset distribution by cluster, status, and Kubernetes resource type.',
    },
    {
        'value': 'inventory_assets',
        'label': 'Asset Inventory',
        'description': 'Asset-level records from the latest committed Kubernetes inventory snapshot.',
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
    namespace_options_by_cluster = _get_namespace_options_by_cluster()

    return {
        'page_title': 'Generate Report',
        'page_subtitle': (
            'Build a governed report from connected data, selected scope, and reusable sections.'
        ),
        'clusters': cluster_options,
        'has_clusters': len(cluster_options) > 1,
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
            SINGLE_CLUSTER_REQUIRED_REPORT_TYPES,
        ),
        'form_state': form_state,
        'preview_report_name': form_state['name'].strip() or build_default_report_name(form_state),
        'errors': errors or [],
        'readiness': _get_generation_readiness(
            storage_context=storage_context,
            form_state=form_state,
            selected_report_type=selected_report_type,
            has_clusters=len(cluster_options) > 1,
        ),
        'storage_context': storage_context,
        'generation_flow': _get_generation_flow(),
        'report_type_guide_groups': _get_report_type_guide_groups(),
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
        'period': _get_default_period(normalized_report_type),
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
                'cluster_scope_label': 'Specific Cluster Required'
                if report_requires_specific_cluster(
                    item['value'],
                )
                else 'All Clusters Supported',
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
        'cluster_scope_label': 'Specific Cluster Required'
        if report_requires_specific_cluster(
            fallback['value'],
        )
        else 'All Clusters Supported',
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
            'Select a specific cluster before choosing a namespace.',
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
    for item in REPORT_TYPE_OPTIONS:
        if item['value'] == report_type and item.get('family') == 'inventory':
            return 'snapshot'
    return '30d'


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


def _get_namespace_options_by_cluster() -> dict[str, list[str]]:
    query = db.session.query(
        NamespaceInventory.cluster_id,
        NamespaceInventory.namespace,
    )
    query = filter_current_generation(
        query,
        NamespaceInventory,
    )
    rows = (
        query.order_by(
            NamespaceInventory.cluster_id.asc(),
            NamespaceInventory.namespace.asc(),
        )
        .all()
    )

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


def _get_generation_readiness(
    *,
    storage_context: dict[str, Any],
    form_state: dict[str, Any],
    selected_report_type: dict[str, Any],
    has_clusters: bool,
) -> list[dict[str, str]]:
    requires_specific_cluster = bool(
        selected_report_type.get(
            'requires_cluster',
            False,
        )
    )
    cluster_selected = bool(
        str(
            form_state.get(
                'cluster_id',
                '',
            )
            or ''
        ).strip()
    )
    selected_sections = form_state.get(
        'sections',
        [],
    )
    selected_section_count = (
        len(selected_sections)
        if isinstance(
            selected_sections,
            list,
        )
        else 0
    )

    if not has_clusters:
        scope_status = 'Setup Required'
        scope_tone = 'amber'
        scope_description = 'Register at least one Kubernetes cluster before creating report requests.'
    elif requires_specific_cluster and not cluster_selected:
        scope_status = 'Select Cluster'
        scope_tone = 'amber'
        scope_description = 'This report type requires one specific validated cluster.'
    else:
        scope_status = 'Ready'
        scope_tone = 'blue'
        scope_description = (
            'The selected report type supports the current cluster scope.'
        )

    section_status = (
        f'{selected_section_count} Selected'
        if selected_section_count
        else 'Selection Required'
    )
    section_tone = 'blue' if selected_section_count else 'amber'
    section_description = (
        'At least one report section is selected for this request.'
        if selected_section_count
        else 'Select at least one report section before creating the request.'
    )

    return [
        {
            'key': 'scope',
            'label': 'Request Scope',
            'description': scope_description,
            'status': scope_status,
            'tone': scope_tone,
            'icon': 'crosshair',
        },
        {
            'key': 'sections',
            'label': 'Section Selection',
            'description': section_description,
            'status': section_status,
            'tone': section_tone,
            'icon': 'list-checks',
        },
        {
            'key': 'pdf',
            'label': 'PDF Generation',
            'description': 'Create the request first, then render the PDF from Generated Reports.',
            'status': 'Ready',
            'tone': 'blue',
            'icon': 'file-text',
        },
        {
            'key': 'storage',
            'label': 'Artifact Storage',
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
            'tone': str(
                storage_context.get(
                    'tone',
                    'amber',
                )
            ),
            'icon': 'hard-drive',
        },
    ]


def _get_generation_flow() -> list[tuple[str, str]]:
    return [
        (
            'Configure Request',
            'Choose the report type, scope, period, output format, and sections.',
        ),
        (
            'Create Request',
            'KAORI saves a governed report record with Requested status.',
        ),
        (
            'Generate PDF',
            'Open Generated Reports and start PDF rendering for the request.',
        ),
        (
            'Store and Download',
            'KAORI stores the artifact in the active backend and makes it available for download.',
        ),
    ]


def _get_report_type_guide_groups() -> list[dict[str, Any]]:
    def guide_items(family: str) -> list[dict[str, str]]:
        return [
            {
                'label': str(item['label']).removesuffix(' Report'),
                'description': str(item['description']),
                'icon': str(item['icon']),
                'status': 'System Template',
            }
            for item in REPORT_TYPE_OPTIONS
            if item.get('family') == family
        ]

    server_report_items = [
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

    return [
        {
            'key': 'kubernetes_analytics',
            'label': 'Kubernetes Analytics',
            'description': 'Metrics-backed reports for utilization, capacity, forecast, alerts, and operational analysis.',
            'items': guide_items('analytics'),
        },
        {
            'key': 'kubernetes_inventory',
            'label': 'Kubernetes Inventory',
            'description': 'Snapshot reports focused on one Kubernetes asset type at a time.',
            'items': guide_items('inventory'),
        },
        {
            'key': 'server',
            'label': 'KAORI Server Reports',
            'description': 'Server, VM, and HCI report types become available when their data providers are connected and validated.',
            'items': server_report_items,
        },
    ]


def _get_recommended_actions() -> list[dict[str, str]]:
    return [
        {
            'label': 'Start with a Kubernetes Report',
            'description': 'Use Analytics Overview for metrics or select an Inventory report for a current asset snapshot.',
            'href': '#report-configuration',
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
