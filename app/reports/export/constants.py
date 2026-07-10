from __future__ import annotations

REPORT_DOMAIN_KUBEREPORT = 'kubereport'
REPORT_DOMAIN_SERVERREPORT = 'serverreport'
REPORT_DOMAIN_HCIREPORT = 'hcireport'

SOURCE_KIND_KUBERNETES = 'kubernetes'
SOURCE_KIND_SERVER = 'server'
SOURCE_KIND_VM = 'vm'
SOURCE_KIND_HCI = 'hci'

REPORT_DOMAIN_LABELS = {
    REPORT_DOMAIN_KUBEREPORT: 'KubeReport',
    REPORT_DOMAIN_SERVERREPORT: 'ServerReport',
    REPORT_DOMAIN_HCIREPORT: 'HCIReport',
}

REPORT_DOMAIN_DESCRIPTIONS = {
    REPORT_DOMAIN_KUBEREPORT: 'Kubernetes inventory, Prometheus/Alertmanager analytics, governance, and operational reports.',
    REPORT_DOMAIN_SERVERREPORT: 'Server and VM infrastructure reports using server inventory plus Node Exporter metrics.',
    REPORT_DOMAIN_HCIREPORT: 'HCI cluster, host, datastore, and VM placement reports using HCI API integration.',
}

SOURCE_KIND_LABELS = {
    SOURCE_KIND_KUBERNETES: 'Kubernetes',
    SOURCE_KIND_SERVER: 'Server',
    SOURCE_KIND_VM: 'Virtual Machine',
    SOURCE_KIND_HCI: 'HCI',
}

REPORT_DOMAIN_SOURCE_KINDS = {
    REPORT_DOMAIN_KUBEREPORT: [SOURCE_KIND_KUBERNETES],
    REPORT_DOMAIN_SERVERREPORT: [SOURCE_KIND_SERVER, SOURCE_KIND_VM],
    REPORT_DOMAIN_HCIREPORT: [SOURCE_KIND_HCI],
}

DEFAULT_REPORT_DOMAIN = REPORT_DOMAIN_KUBEREPORT
DEFAULT_REPORT_SOURCE_KIND = SOURCE_KIND_KUBERNETES

REPORT_TYPE_LABELS = {
    'analytics_overview': 'Analytics Overview',
    'resource_utilization': 'Resource Utilization',
    'capacity_analysis': 'Capacity Analysis',
    'storage_analysis': 'Storage Analysis',
    'workload_analysis': 'Workload Analysis',
    'resource_forecast': 'Resource Forecast',
    'top_consumers': 'Top Consumers',
    'alerts_anomalies': 'Alerts & Anomalies',
}

REPORT_TYPE_DESCRIPTIONS = {
    'analytics_overview': (
        'High-level Kubernetes operational summary covering resource posture, '
        'risk context, and recommended follow-up actions.'
    ),
    'resource_utilization': (
        'Resource usage report focused on CPU, memory, storage, and pod utilization patterns across the selected scope.'
    ),
    'capacity_analysis': (
        'Capacity and headroom report focused on allocatable resources, usage pressure, and scheduling risk.'
    ),
    'storage_analysis': (
        'Storage-focused report covering filesystem, persistent volume, persistent volume claim, '
        'quota, and storage risk context.'
    ),
    'workload_analysis': (
        'Workload governance report focused on request/limit coverage, namespace breakdown, '
        'and workload resource mapping.'
    ),
    'resource_forecast': (
        'Forecast report designed to summarize projected resource growth and capacity planning signals.'
    ),
    'top_consumers': (
        'Top consumer report for identifying high-impact namespaces, workloads, pods, and resource hotspots.'
    ),
    'alerts_anomalies': (
        'Alert and anomaly report focused on active alert state, severity distribution, '
        'affected resources, and operational response context.'
    ),
}

SECTION_LABELS = {
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
}

SECTION_DESCRIPTIONS = {
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
    'source_health': ('Summarizes Alertmanager, Prometheus fallback, resolved source, and source confidence state.'),
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
    'operational_recommendations': (
        'Provides operational recommendations. For supported report types, recommendations are derived from real findings, risk signals, and utilization/capacity pressure instead of static cards only.'  # noqa: E501
    ),
}

REPORT_TYPE_RECOMMENDATIONS = {
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
}

DEFAULT_RECOMMENDATIONS = [
    'Review report metadata and selected scope before taking operational action.',
    'Validate findings with live cluster data when the report is used for incident response.',
    'Use generated reports as operational evidence and attach them to follow-up tasks when needed.',
]

REAL_DATA_REPORT_TYPES = {
    'analytics_overview',
    'resource_utilization',
    'capacity_analysis',
    'storage_analysis',
    'workload_analysis',
    'resource_forecast',
    'top_consumers',
    'alerts_anomalies',
}

REQUIRES_SINGLE_CLUSTER_REPORT_TYPES = {
    'resource_utilization',
    'capacity_analysis',
    'storage_analysis',
    'workload_analysis',
    'resource_forecast',
    'top_consumers',
    'alerts_anomalies',
}


REAL_DATA_SECTION_MAP = {
    'analytics_overview': {
        'executive_summary',
        'analytics_summary',
        'resource_snapshot',
        'risk_overview',
        'operational_recommendations',
    },
    'resource_utilization': {
        'executive_summary',
        'resource_snapshot',
        'cpu_utilization',
        'memory_utilization',
        'storage_utilization',
        'pod_utilization',
        'node_resource_detail',
        'risk_overview',
        'operational_recommendations',
    },
    'capacity_analysis': {
        'executive_summary',
        'worker_capacity_summary',
        'resource_allocation_headroom',
        'capacity_pressure_risk',
        'operational_recommendations',
    },
    'storage_analysis': {
        'executive_summary',
        'filesystem_summary',
        'persistent_volume_summary',
        'persistent_volume_claims',
        'storage_risk',
        'operational_recommendations',
    },
    'workload_analysis': {
        'executive_summary',
        'tenant_quota_summary',
        'request_limit_coverage',
        'workload_resource_mapping',
        'governance_findings',
        'operational_recommendations',
    },
    'resource_forecast': {
        'executive_summary',
        'forecast_summary',
        'forecast_risk_summary',
        'resource_trend_summary',
        'cpu_forecast',
        'memory_forecast',
        'storage_forecast',
        'pod_forecast',
        'capacity_projection',
        'forecast_projection',
        'threshold_eta',
        'operational_recommendations',
    },
    'top_consumers': {
        'executive_summary',
        'top_namespace_consumers',
        'top_workload_consumers',
        'top_pod_consumers',
        'resource_hotspots',
        'operational_recommendations',
    },
    'alerts_anomalies': {
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
    },
}
