from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.reports.export.constants import ANALYTICS_OVERVIEW_SECTION_KEYS

REPORT_FAMILY_ANALYTICS = 'analytics'
REPORT_FAMILY_INVENTORY = 'inventory'

FORMAT_PDF = 'pdf'
FORMAT_XLSX = 'xlsx'
FORMAT_CSV = 'csv'


@dataclass(frozen=True, slots=True)
class OutputFormatSpec:
    value: str
    label: str
    extension: str
    mimetype: str


@dataclass(frozen=True, slots=True)
class ReportTypeSpec:
    value: str
    label: str
    description: str
    icon: str
    family: str
    default_format: str
    allowed_formats: tuple[str, ...]
    default_sections: tuple[str, ...]
    period_mode: str
    requires_cluster: bool = True


OUTPUT_FORMAT_SPECS: dict[str, OutputFormatSpec] = {
    FORMAT_PDF: OutputFormatSpec(
        value=FORMAT_PDF,
        label='PDF',
        extension='.pdf',
        mimetype='application/pdf',
    ),
    FORMAT_XLSX: OutputFormatSpec(
        value=FORMAT_XLSX,
        label='Excel Workbook (.xlsx)',
        extension='.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ),
    FORMAT_CSV: OutputFormatSpec(
        value=FORMAT_CSV,
        label='CSV (.csv)',
        extension='.csv',
        mimetype='text/csv',
    ),
}

_ANALYTICS_FORMATS = (FORMAT_PDF, FORMAT_CSV)
_INVENTORY_FORMATS = (FORMAT_XLSX, FORMAT_CSV)
_INVENTORY_SECTIONS = (
    'inventory_assets',
    'inventory_metadata',
    'inventory_field_dictionary',
)

REPORT_TYPE_SPECS: tuple[ReportTypeSpec, ...] = (
    ReportTypeSpec(
        value='analytics_overview',
        label='Analytics Overview Report',
        description='High-level analytics summary across utilization, capacity, forecast, and alerts.',
        icon='layout-dashboard',
        family=REPORT_FAMILY_ANALYTICS,
        default_format=FORMAT_PDF,
        allowed_formats=_ANALYTICS_FORMATS,
        default_sections=tuple(ANALYTICS_OVERVIEW_SECTION_KEYS),
        period_mode='range',
    ),
    ReportTypeSpec(
        value='resource_utilization',
        label='Resource Utilization Report',
        description='CPU, memory, storage, pod utilization, and node resource detail.',
        icon='activity',
        family=REPORT_FAMILY_ANALYTICS,
        default_format=FORMAT_PDF,
        allowed_formats=_ANALYTICS_FORMATS,
        default_sections=(
            'executive_summary',
            'cpu_utilization',
            'memory_utilization',
            'storage_utilization',
            'pod_utilization',
            'node_resource_detail',
            'operational_recommendations',
        ),
        period_mode='range',
    ),
    ReportTypeSpec(
        value='capacity_analysis',
        label='Capacity Analysis Report',
        description='Worker capacity, allocation, headroom, and pressure risk.',
        icon='database',
        family=REPORT_FAMILY_ANALYTICS,
        default_format=FORMAT_PDF,
        allowed_formats=_ANALYTICS_FORMATS,
        default_sections=(
            'executive_summary',
            'worker_capacity_summary',
            'resource_allocation_headroom',
            'capacity_pressure_risk',
            'operational_recommendations',
        ),
        period_mode='range',
    ),
    ReportTypeSpec(
        value='storage_analysis',
        label='Storage Analysis Report',
        description='Filesystem, persistent volume, PVC, capacity, usage, and free space summary.',
        icon='hard-drive',
        family=REPORT_FAMILY_ANALYTICS,
        default_format=FORMAT_PDF,
        allowed_formats=_ANALYTICS_FORMATS,
        default_sections=(
            'executive_summary',
            'filesystem_summary',
            'persistent_volume_summary',
            'persistent_volume_claims',
            'storage_risk',
            'operational_recommendations',
        ),
        period_mode='range',
    ),
    ReportTypeSpec(
        value='workload_analysis',
        label='Workload Analysis Report',
        description='Workload resource requests, limits, mapping, and namespace resource behavior.',
        icon='boxes',
        family=REPORT_FAMILY_ANALYTICS,
        default_format=FORMAT_PDF,
        allowed_formats=_ANALYTICS_FORMATS,
        default_sections=(
            'executive_summary',
            'tenant_quota_summary',
            'request_limit_coverage',
            'workload_resource_mapping',
            'governance_findings',
            'operational_recommendations',
        ),
        period_mode='range',
    ),
    ReportTypeSpec(
        value='resource_forecast',
        label='Resource Forecast Report',
        description='Forecast CPU, memory, storage, and pod growth using historical metrics.',
        icon='line-chart',
        family=REPORT_FAMILY_ANALYTICS,
        default_format=FORMAT_PDF,
        allowed_formats=_ANALYTICS_FORMATS,
        default_sections=(
            'executive_summary',
            'forecast_summary',
            'cpu_forecast',
            'memory_forecast',
            'storage_forecast',
            'pod_forecast',
            'capacity_projection',
            'operational_recommendations',
        ),
        period_mode='range',
    ),
    ReportTypeSpec(
        value='top_consumers',
        label='Top Consumers Report',
        description='Top namespaces, workloads, and pods consuming cluster resources.',
        icon='users',
        family=REPORT_FAMILY_ANALYTICS,
        default_format=FORMAT_PDF,
        allowed_formats=_ANALYTICS_FORMATS,
        default_sections=(
            'executive_summary',
            'top_namespace_consumers',
            'top_workload_consumers',
            'top_pod_consumers',
            'resource_hotspots',
            'operational_recommendations',
        ),
        period_mode='range',
    ),
    ReportTypeSpec(
        value='alerts_anomalies',
        label='Alerts & Anomalies Report',
        description='Alert visibility, anomaly context, source health, routing, ownership, incident readiness, and recommendation notes.',
        icon='triangle-alert',
        family=REPORT_FAMILY_ANALYTICS,
        default_format=FORMAT_PDF,
        allowed_formats=_ANALYTICS_FORMATS,
        default_sections=(
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
        ),
        period_mode='range',
    ),
    ReportTypeSpec(
        value='inventory_overview',
        label='Inventory Overview',
        description='Committed Kubernetes asset totals by inventory category.',
        icon='layout-dashboard',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='node_inventory',
        label='Nodes Inventory',
        description='Node identities, readiness, platform, capacity, addressing, and collection evidence.',
        icon='server-cog',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='namespace_inventory',
        label='Namespaces Inventory',
        description='Namespace identities, lifecycle state, controls, and service-account posture.',
        icon='folder-tree',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='workload_inventory',
        label='Workloads Inventory',
        description='Workload identities, readiness, replica state, runtime status, and update strategy.',
        icon='boxes',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='pod_inventory',
        label='Pods Inventory',
        description='Pod identities, ownership, phase, readiness, placement, restarts, and attached evidence.',
        icon='box',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='service_inventory',
        label='Services Inventory',
        description='Service identities, types, addresses, ports, selectors, and exposure fields.',
        icon='waypoints',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='ingress_inventory',
        label='Ingresses Inventory',
        description='Ingress identities, class, hosts, addresses, backend counts, and TLS references.',
        icon='route',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='configuration_inventory',
        label='Configuration Inventory',
        description='ConfigMap and Secret metadata, key names, immutability, and payload size without values.',
        icon='file-key-2',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='storage_inventory',
        label='Storage Inventory',
        description='StorageClass, persistent-volume, and persistent-volume-claim identities and lifecycle fields.',
        icon='database-zap',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
    ReportTypeSpec(
        value='tls_inventory',
        label='TLS Certificate Inventory',
        description='Certificate validity, usage references, hostname coverage, and collection evidence without private keys.',
        icon='shield-check',
        family=REPORT_FAMILY_INVENTORY,
        default_format=FORMAT_XLSX,
        allowed_formats=_INVENTORY_FORMATS,
        default_sections=_INVENTORY_SECTIONS,
        period_mode='snapshot',
    ),
)

_REPORT_TYPE_BY_VALUE = {item.value: item for item in REPORT_TYPE_SPECS}

OUTPUT_FORMAT_OPTIONS: list[dict[str, str]] = [
    {'value': spec.value, 'label': spec.label}
    for spec in OUTPUT_FORMAT_SPECS.values()
]

REPORT_TYPE_OPTIONS: list[dict[str, Any]] = [
    {
        'value': spec.value,
        'label': spec.label,
        'description': spec.description,
        'icon': spec.icon,
        'family': spec.family,
        'primary_format': spec.default_format,
        'allowed_formats': list(spec.allowed_formats),
        'default_sections': list(spec.default_sections),
        'period_mode': spec.period_mode,
        'requires_cluster': spec.requires_cluster,
    }
    for spec in REPORT_TYPE_SPECS
]

REQUIRES_SELECTED_CLUSTER_REPORT_TYPES = frozenset(
    spec.value for spec in REPORT_TYPE_SPECS if spec.requires_cluster
)

ANALYTICS_REPORT_TYPES = frozenset(
    spec.value for spec in REPORT_TYPE_SPECS if spec.family == REPORT_FAMILY_ANALYTICS
)
INVENTORY_REPORT_TYPES = frozenset(
    spec.value for spec in REPORT_TYPE_SPECS if spec.family == REPORT_FAMILY_INVENTORY
)


class ReportContractError(ValueError):
    """Raised when a report violates the canonical KAORI reporting contract."""


def get_report_type_spec(report_type: str) -> ReportTypeSpec:
    try:
        return _REPORT_TYPE_BY_VALUE[report_type]
    except KeyError as exc:
        raise ReportContractError(f'Unsupported report type: {report_type!r}.') from exc


def get_report_type_label(report_type: str) -> str:
    return get_report_type_spec(report_type).label


def normalize_report_type(value: str | None) -> str:
    normalized = str(value or REPORT_TYPE_SPECS[0].value).strip()
    return normalized if normalized in _REPORT_TYPE_BY_VALUE else REPORT_TYPE_SPECS[0].value


def get_allowed_output_formats(report_type: str) -> tuple[str, ...]:
    return get_report_type_spec(report_type).allowed_formats


def get_default_output_format(report_type: str) -> str:
    return get_report_type_spec(report_type).default_format


def validate_report_contract(
    *,
    report_type: str,
    output_format: str,
    cluster_id: str | None,
) -> None:
    spec = get_report_type_spec(report_type)
    normalized_format = str(output_format or '').strip().lower()

    if spec.requires_cluster and not str(cluster_id or '').strip():
        raise ReportContractError(
            'A selected Kubernetes cluster is required. Cross-cluster report generation is disabled.'
        )
    if normalized_format not in spec.allowed_formats:
        allowed = ', '.join(value.upper() for value in spec.allowed_formats)
        raise ReportContractError(
            f'{spec.label} supports only {allowed} output.'
        )


def require_selected_cluster(report: Any) -> str:
    cluster_id = str(getattr(report, 'cluster_id', '') or '').strip()
    if not cluster_id:
        raise ReportContractError(
            'A selected Kubernetes cluster is required. Cross-cluster report generation is disabled.'
        )
    return cluster_id


def validate_report_instance(report: Any) -> None:
    validate_report_contract(
        report_type=str(getattr(report, 'report_type', '') or ''),
        output_format=str(getattr(report, 'output_format', '') or ''),
        cluster_id=getattr(report, 'cluster_id', None),
    )
