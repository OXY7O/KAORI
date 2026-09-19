from __future__ import annotations

REPORT_DOMAIN_KUBERNETES = 'kubernetes'
REPORT_DOMAIN_OBJECT_STORAGE = 'object_storage'
REPORT_DOMAIN_SERVER = 'server'
REPORT_DOMAIN_HCI = 'hci'

SOURCE_KIND_KUBERNETES = 'kubernetes'
SOURCE_KIND_OBJECT_STORAGE = 'object_storage'
SOURCE_KIND_SERVER = 'server'
SOURCE_KIND_VM = 'vm'
SOURCE_KIND_HCI = 'hci'

REPORT_DOMAIN_LABELS = {
    REPORT_DOMAIN_KUBERNETES: 'KAORI Kubernetes Reports',
    REPORT_DOMAIN_OBJECT_STORAGE: 'KAORI Object Storage Reports',
    REPORT_DOMAIN_SERVER: 'KAORI Server Reports',
    REPORT_DOMAIN_HCI: 'KAORI HCI Reports',
}

REPORT_DOMAIN_DESCRIPTIONS = {
    REPORT_DOMAIN_KUBERNETES: 'Kubernetes inventory, Metrics Source/Alertmanager analytics, governance, and operational reports.',
    REPORT_DOMAIN_OBJECT_STORAGE: 'Object Storage committed inventory, metrics analytics, forecast, and operational evidence reports.',
    REPORT_DOMAIN_SERVER: 'Server and VM infrastructure reports using server inventory plus Node Exporter metrics.',
    REPORT_DOMAIN_HCI: 'HCI cluster, host, datastore, and VM placement reports using HCI API integration.',
}

SOURCE_KIND_LABELS = {
    SOURCE_KIND_KUBERNETES: 'Kubernetes',
    SOURCE_KIND_OBJECT_STORAGE: 'Object Storage',
    SOURCE_KIND_SERVER: 'Server',
    SOURCE_KIND_VM: 'Virtual Machine',
    SOURCE_KIND_HCI: 'HCI',
}

REPORT_DOMAIN_SOURCE_KINDS = {
    REPORT_DOMAIN_KUBERNETES: [SOURCE_KIND_KUBERNETES],
    REPORT_DOMAIN_OBJECT_STORAGE: [SOURCE_KIND_OBJECT_STORAGE],
    REPORT_DOMAIN_SERVER: [SOURCE_KIND_SERVER, SOURCE_KIND_VM],
    REPORT_DOMAIN_HCI: [SOURCE_KIND_HCI],
}

DEFAULT_REPORT_DOMAIN = REPORT_DOMAIN_KUBERNETES
DEFAULT_REPORT_SOURCE_KIND = SOURCE_KIND_KUBERNETES

ANALYTICS_OVERVIEW_SECTION_KEYS = (
    'executive_brief',
    'resource_posture',
    'trend_forecast',
    'top_consumers',
    'capacity_pressure',
    'alerts_anomalies',
    'reporting_summary',
    'inventory_snapshot',
    'data_freshness_reliability',
    'recommendation_plan',
    'methodology_evidence_boundary',
)

SECTION_LABELS = {
    'executive_brief': 'Executive Brief',
    'resource_posture': 'Resource Posture',
    'trend_forecast': 'Trend & Forecast',
    'capacity_pressure': 'Capacity Pressure',
    'alerts_anomalies': 'Alerts & Anomalies',
    'reporting_summary': 'Reporting Summary',
    'inventory_snapshot': 'Inventory Snapshot',
    'data_freshness_reliability': 'Data Freshness & Reliability',
    'recommendation_plan': 'Recommendation Plan',
    'methodology_evidence_boundary': 'Methodology & Evidence Boundary',
    'executive_summary': 'Executive Summary',
    'analytics_summary': 'Analytics Summary',
    'resource_snapshot': 'Resource Snapshot',
    'risk_overview': 'Risk Overview',
    'operational_recommendations': 'Operational Recommendations',
    'cpu_utilization': 'CPU Utilization',
    'memory_utilization': 'Memory Utilization',
    'storage_utilization': 'Storage Utilization',
    'pod_utilization': 'Pod Utilization',
    'node_resource_detail': 'Node Resource Detail',
    'worker_capacity_summary': 'Worker Capacity Summary',
    'resource_allocation_headroom': 'Resource Allocation & Headroom',
    'capacity_pressure_risk': 'Capacity & Pressure Risk',
    'storage_capacity': 'Storage Capacity',
    'tenant_quota': 'Tenant Quota',
    'workload_resource_mapping': 'Workload Resource Mapping',
    'filesystem_summary': 'Filesystem Summary',
    'persistent_volume_summary': 'Persistent Volume Summary',
    'persistent_volume_claims': 'Persistent Volume Claims',
    'storage_risk': 'Storage Risk',
    'tenant_quota_summary': 'Tenant Quota Summary',
    'request_limit_coverage': 'Request & Limit Coverage',
    'namespace_breakdown': 'Namespace Breakdown',
    'governance_findings': 'Governance Findings',
    'forecast_summary': 'Forecast Summary',
    'forecast_risk_summary': 'Forecast Risk Summary',
    'resource_trend_summary': 'Resource Trend Summary',
    'cpu_forecast': 'CPU Forecast',
    'memory_forecast': 'Memory Forecast',
    'storage_forecast': 'Storage Forecast',
    'pod_forecast': 'Pod Forecast',
    'capacity_projection': 'Capacity Projection',
    'forecast_projection': 'Forecast Projection',
    'threshold_eta': 'Threshold ETA',
    'top_namespace_consumers': 'Top Namespace Consumers',
    'top_workload_consumers': 'Top Workload Consumers',
    'top_pod_consumers': 'Top Pod Consumers',
    'resource_hotspots': 'Resource Hotspots',
    'active_alerts': 'Active Alerts',
    'alert_severity_summary': 'Alert Severity Summary',
    'source_health': 'Alert Source Health',
    'routing_grouping': 'Alert Routing & Grouping',
    'silence_inhibition': 'Silence & Inhibition Visibility',
    'ownership_runbook': 'Ownership & Runbook Readiness',
    'incident_readiness': 'Incident Readiness',
    'anomaly_context': 'Anomaly Context',
    'affected_resources': 'Affected Resources',
    'object_storage_capacity_usage': 'Capacity & Usage',
    'object_storage_bucket_distribution': 'Bucket / Container Distribution',
    'object_storage_quota_headroom': 'Quota & Headroom',
    'object_storage_performance': 'Request Performance',
    'object_storage_forecast': 'Capacity Forecast',
    'object_storage_top_consumers': 'Top Consumers',
    'object_storage_risk_findings': 'Risk & Findings',
    'object_storage_inventory_assets': 'Object Storage Inventory Data',
    'object_storage_inventory_metadata': 'Workbook Metadata',
    'object_storage_inventory_field_dictionary': 'Field Dictionary',
    'inventory_assets': 'Inventory Data',
    'inventory_metadata': 'Workbook Metadata',
    'inventory_field_dictionary': 'Field Dictionary',
}

SECTION_DESCRIPTIONS = {
    'executive_brief': 'Current operational position, priority findings, decisions, and evidence scope.',
    'resource_posture': 'CPU, memory, storage, pod, and node posture with committed capacity headroom.',
    'trend_forecast': 'Historical resource direction, forecast pressure, confidence, and limitations.',
    'capacity_pressure': 'Current headroom, saturation risk, breach projection, and recommended capacity actions.',
    'alerts_anomalies': 'Active alert severity, affected resources, recent anomalies, and response priorities.',
    'reporting_summary': 'Report generation activity, schedules, storage readiness, and operational notes.',
    'inventory_snapshot': 'Committed cluster, node, workload, pod, and core resource inventory summary.',
    'data_freshness_reliability': 'Source recency, collection completeness, reliability, and data-quality issues.',
    'recommendation_plan': 'Prioritized evidence-backed actions with owners, target windows, and validation gates.',
    'methodology_evidence_boundary': 'Data sources, methodology, included evidence, exclusions, and status language.',
    'executive_summary': (
        'Summarizes report purpose, selected scope, key operational findings, and data context for the generated PDF.'
    ),
    'analytics_summary': ('Provides a consolidated analytics summary for the selected cluster, namespace, and period.'),
    'resource_snapshot': (
        'Captures a point-in-time resource snapshot including capacity, usage, and availability signals.'
    ),
    'risk_overview': ('Highlights operational risk areas that should be reviewed by platform or operations teams.'),
    'cpu_utilization': ('CPU capacity, usage, utilization status, and pressure context.'),
    'memory_utilization': ('Memory capacity, usage, utilization status, and pressure context.'),
    'storage_utilization': ('Storage capacity, usage, utilization status, and pressure context.'),
    'pod_utilization': ('Pod capacity, running pod usage, utilization status, and scheduling context.'),
    'node_resource_detail': ('Node-level resource detail, pressure signals, and allocation context.'),
    'worker_capacity_summary': ('Prepared section for worker-node allocatable capacity and schedulable headroom.'),
    'resource_allocation_headroom': ('Prepared section for request/limit allocation and available headroom analysis.'),
    'capacity_pressure_risk': (
        'Prepared section for capacity pressure, node pressure, and scheduling risk assessment.'
    ),
    'storage_capacity': ('Prepared section for storage capacity and storage consumption overview.'),
    'tenant_quota': ('Prepared section for namespace quota, limit, and request governance context.'),
    'workload_resource_mapping': (
        'Prepared section for workload resource request/limit coverage and ownership mapping.'
    ),
    'filesystem_summary': ('Prepared section for filesystem capacity and usage summary.'),
    'persistent_volume_summary': (
        'Prepared section for persistent volume capacity, status, and storage class distribution.'
    ),
    'persistent_volume_claims': ('Prepared section for PVC request, usage, free space, and risk review.'),
    'storage_risk': ('Prepared section for storage growth risk, low-free-space signals, and operational follow-up.'),
    'tenant_quota_summary': ('Prepared section for tenant quota summary and namespace-level resource governance.'),
    'request_limit_coverage': ('Prepared section for identifying workloads without proper requests or limits.'),
    'namespace_breakdown': ('Prepared section for namespace-level resource distribution and ownership review.'),
    'governance_findings': (
        'Summarizes workload governance gaps, missing resource controls, severity, and remediation priorities.'
    ),
    'forecast_summary': ('Summarizes forecast horizon, data availability, and projected capacity planning posture.'),
    'forecast_risk_summary': ('Summarizes forecast risk level, signal quality, and planning attention areas.'),
    'resource_trend_summary': ('Summarizes CPU, memory, storage, and pod trend direction used by the forecast view.'),
    'cpu_forecast': ('Prepared section for CPU growth projection and future threshold risk.'),
    'memory_forecast': ('Prepared section for memory growth projection and future pressure risk.'),
    'storage_forecast': ('Prepared section for storage growth projection and retention/capacity planning.'),
    'pod_forecast': ('Prepared section for pod growth projection and schedulable capacity planning.'),
    'capacity_projection': ('Summarizes capacity projection, trend direction, and planning recommendations.'),
    'forecast_projection': (
        'Summarizes projected resource pressure, forecast horizon, and estimated growth direction.'
    ),
    'threshold_eta': ('Summarizes estimated threshold timing when forecast data indicates capacity risk.'),
    'top_namespace_consumers': ('Prepared section for namespaces with the highest resource consumption.'),
    'top_workload_consumers': ('Prepared section for workloads with the highest resource consumption.'),
    'top_pod_consumers': ('Prepared section for pods with the highest resource consumption.'),
    'resource_hotspots': ('Prepared section for recurring hotspots and high-impact resource consumers.'),
    'active_alerts': ('Prepared section for active alerts, severity, and operational impact.'),
    'alert_severity_summary': ('Prepared section for alert severity distribution and priority handling.'),
    'source_health': (
        'Summarizes Alertmanager, Metrics Source fallback, resolved source, and source confidence state.'
    ),
    'routing_grouping': (
        'Summarizes Alertmanager routing, receiver groups, grouping keys, fingerprints, and namespace spread.'
    ),
    'silence_inhibition': (
        'Summarizes active silences, silence matcher impact, and inhibited alert context from Alertmanager.'
    ),
    'ownership_runbook': ('Summarizes alert owner, runbook, and contact metadata readiness for operational response.'),
    'incident_readiness': (
        'Combines source, routing, silence, ownership, and signal posture into incident readiness scoring.'
    ),
    'anomaly_context': ('Prepared section for anomaly signals, unusual behavior, and correlation context.'),
    'affected_resources': ('Prepared section for resources affected by alerts, anomalies, or capacity risk.'),
    'inventory_assets': (
        'Lists asset-level records from the latest committed Kubernetes inventory snapshot for the selected scope.'
    ),
    'operational_recommendations': (
        'Provides operational recommendations. For supported report types, recommendations are derived from real findings, risk signals, and utilization/capacity pressure instead of static cards only.'  # noqa: E501
    ),
}

ANALYTICS_REPORT_RECOMMENDATIONS = {
    'analytics_overview': [
        'Review high-level resource posture before starting deeper troubleshooting.',
        'Use detail reports when this overview indicates capacity, utilization, or alert risk.',
        'Compare report output with recent operational incidents and planned maintenance windows.',
    ],
    'resource_utilization': [
        'Review CPU and memory utilization against requests and limits.',
        'Identify workloads with sustained high usage or low resource efficiency.',
        'Validate whether resource requests should be adjusted before scaling workloads.',
    ],
    'capacity_analysis': [
        'Review worker allocatable capacity and available schedulable headroom.',
        'Check node pressure signals before scheduling additional workloads.',
        'Validate namespaces or workloads with request/limit gaps before capacity expansion.',
    ],
    'storage_analysis': [
        'Review PVC request, used, and free capacity.',
        'Check persistent volumes with unusual status or low available space.',
        'Validate storage class usage and growth risk before expanding workloads.',
    ],
    'workload_analysis': [
        'Review workloads without requests or limits.',
        'Prioritize namespaces with incomplete resource governance.',
        'Coordinate with application owners for remediation of risky workload configurations.',
    ],
    'resource_forecast': [
        'Review forecast direction before committing new workloads to the cluster.',
        'Use forecast output as early signal, not as the only capacity planning source.',
        'Validate forecast anomalies against known deployments, incidents, or traffic changes.',
    ],
    'top_consumers': [
        'Review top consumers before investigating cluster-wide resource pressure.',
        'Validate whether high consumers are expected based on application criticality.',
        'Use namespace and workload owner context to drive remediation.',
    ],
    'alerts_anomalies': [
        'Prioritize active alerts by severity and business impact.',
        'Review repeated anomalies for recurring platform or application issues.',
        'Confirm runbook, contact point, and escalation ownership for critical alerts.',
    ],
    'object_storage_analysis': [
        'Review capacity headroom and quota pressure before storage demand reaches operational limits.',
        'Investigate concentrated bucket or container usage and confirm accountable ownership for high consumers.',
        'Validate forecast, request-error, and offline-node signals before changing Object Storage capacity or topology.',
    ],
}

DEFAULT_RECOMMENDATIONS = [
    'Review report metadata and selected scope before taking operational action.',
    'Validate findings with live infrastructure evidence when the report is used for incident response.',
    'Use generated reports as operational evidence and attach them to follow-up tasks when needed.',
]
