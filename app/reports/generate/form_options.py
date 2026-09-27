from __future__ import annotations

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
        'value': 'tenant_inventory',
        'label': 'Tenant Inventory',
        'description': 'Canonical Tenant lifecycle, ownership, environment, and provider authority records.',
    },
    {
        'value': 'namespace_inventory',
        'label': 'Environment & Namespace Inventory',
        'description': 'Committed Tenant environments, namespaces, provisioning state, and profile lineage.',
    },
    {
        'value': 'allocation_posture',
        'label': 'Allocation & Capacity Posture',
        'description': 'Effective Tenant allocation plus capacity allow/block and shortfall evidence.',
    },
    {
        'value': 'access_posture',
        'label': 'Memberships & Access Grants',
        'description': 'Tenant principal membership and scoped RBAC grant posture.',
    },
    {
        'value': 'credential_posture',
        'label': 'Credential Lifecycle Posture',
        'description': 'Non-secret human, admin, and CI/CD credential lifecycle metadata.',
    },
    {
        'value': 'managed_resource_posture',
        'label': 'Managed Resources & Policies',
        'description': 'Managed TLS/registry, domain/exposure policy, and advanced provider intent posture.',
    },
    {
        'value': 'provider_posture',
        'label': 'Provider & Capability Posture',
        'description': 'Committed Native/Capsule authority, capabilities, degradation, and recovery evidence.',
    },
    {
        'value': 'activity_evidence',
        'label': 'Activity & Audit Evidence',
        'description': 'Correlated Kubernetes audit evidence for governed Tenant activity.',
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
        'description': 'Alertmanager, Metrics Source fallback, resolved source, and source confidence state.',
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
        'value': 'object_storage_capacity_usage',
        'label': 'Capacity & Usage',
        'description': 'Usable capacity, committed usage, utilization, and free headroom for the selected Object Storage system.',
    },
    {
        'value': 'object_storage_bucket_distribution',
        'label': 'Bucket / Container Distribution',
        'description': 'Bucket or container usage distribution and concentration across the selected Object Storage system.',
    },
    {
        'value': 'object_storage_quota_headroom',
        'label': 'Quota & Headroom',
        'description': 'Quota evidence coverage, pressure, and remaining headroom for committed Object Storage namespaces.',
    },
    {
        'value': 'object_storage_performance',
        'label': 'Request Performance',
        'description': 'Request rate, error pressure, waiting requests, traffic, and storage-node availability signals.',
    },
    {
        'value': 'object_storage_forecast',
        'label': 'Capacity Forecast',
        'description': 'Worker-materialized growth projection, projected usage, and estimated capacity threshold timing.',
    },
    {
        'value': 'object_storage_top_consumers',
        'label': 'Top Consumers',
        'description': 'Highest-consuming buckets or containers with usage, quota, object, and request evidence.',
    },
    {
        'value': 'object_storage_risk_findings',
        'label': 'Risk & Findings',
        'description': 'Capacity, request-path, quota, concentration, and source-readiness findings requiring review.',
    },
    {
        'value': 'object_storage_inventory_assets',
        'label': 'Object Storage Inventory Data',
        'description': 'Committed Object Storage system and bucket or container asset evidence.',
    },
    {
        'value': 'object_storage_inventory_metadata',
        'label': 'Workbook Metadata',
        'description': 'Object Storage scope, evidence cut-off, ownership, and workbook-standard metadata.',
    },
    {
        'value': 'object_storage_inventory_field_dictionary',
        'label': 'Field Dictionary',
        'description': 'Object Storage inventory column definitions, data types, sources, and missing-value rules.',
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
