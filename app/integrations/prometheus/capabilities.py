from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    key: str
    label: str
    required_by: tuple[str, ...]
    impact: str
    source_owner: str
    recommendation: str
    expected_signals: tuple[str, ...] = ()
    validation_query: str | None = None


CAPABILITIES: dict[str, CapabilityDefinition] = {
    'instant_query': CapabilityDefinition(
        'instant_query',
        'Instant Query API',
        ('All metrics consumers',),
        'KAORI cannot retrieve current metrics.',
        'Prometheus or Thanos Query API',
        'Expose the Prometheus-compatible /api/v1/query endpoint through the exact URL configured in KAORI.',
        validation_query='vector(1)',
    ),
    'range_query': CapabilityDefinition(
        'range_query',
        'Range Query API',
        ('Utilization', 'Forecast', 'Trends'),
        'Historical charts and forecast inputs are unavailable.',
        'Prometheus or Thanos Query API',
        'Expose /api/v1/query_range and confirm that the reverse proxy permits range queries.',
        validation_query='count(up)',
    ),
    'kubernetes_identity': CapabilityDefinition(
        'kubernetes_identity',
        'Kubernetes Identity Metrics',
        ('Overview', 'Inventory correlation'),
        'Metrics cannot be correlated reliably with Kubernetes objects.',
        'kube-state-metrics scrape pipeline',
        'Scrape kube-state-metrics and preserve namespace, pod, node, and workload identity labels.',
        expected_signals=('kube_node_info', 'kube_pod_info', 'kube_namespace_status_phase'),
    ),
    'utilization_metrics': CapabilityDefinition(
        'utilization_metrics',
        'Utilization Metrics',
        ('Utilization Analytics', 'Kubernetes Dashboard'),
        'CPU, memory, pod, readiness, and pressure utilization cannot be calculated reliably.',
        'kube-state-metrics, kubelet, cAdvisor, and Prometheus scrape pipeline',
        'Expose node capacity, container CPU and memory usage, pod status, node conditions, and canonical node identity labels through the configured Prometheus or Thanos Query endpoint.',
        expected_signals=(
            'kube_node_status_capacity',
            'container_cpu_usage_seconds_total',
            'container_memory_working_set_bytes',
            'kube_pod_status_phase',
            'kube_node_status_condition',
            'kube_node_info',
            'kube_pod_info',
        ),
        validation_query='count(kube_node_status_capacity{resource="cpu"})',
    ),
    'capacity_metrics': CapabilityDefinition(
        'capacity_metrics',
        'Worker Capacity Metrics',
        ('Capacity Analytics', 'Forecast'),
        'Worker allocatable capacity, current usage, and worker-only headroom cannot be calculated reliably.',
        'kube-state-metrics, container metrics, and node identity pipeline',
        'Expose allocatable node metrics, container CPU and memory usage, pod placement, and node-role labels with canonical Kubernetes node identity.',
        expected_signals=(
            'kube_node_status_allocatable',
            'container_cpu_usage_seconds_total',
            'container_memory_working_set_bytes',
            'kube_node_role',
            'kube_pod_info',
        ),
        validation_query='count(kube_node_status_allocatable{resource="cpu",unit="core"})',
    ),
    'workload_metrics': CapabilityDefinition(
        'workload_metrics',
        'Workload Identity and Governance Metrics',
        ('Workload Analytics', 'Tenant Quota Analysis', 'Workload Reports'),
        'Tenant quota, workload ownership, QoS, placement, and right-sizing analysis cannot be calculated reliably.',
        'kube-state-metrics, kubelet, cAdvisor, and Prometheus scrape pipeline',
        'Expose namespace, ResourceQuota, pod ownership, QoS, pod placement, container requests/limits, and container usage metrics with canonical namespace, pod, owner, node, resource, and unit labels.',
        expected_signals=(
            'kube_namespace_status_phase',
            'kube_resourcequota',
            'kube_pod_owner',
            'kube_pod_status_qos_class',
            'kube_pod_info',
            'kube_pod_container_resource_requests',
            'kube_pod_container_resource_limits',
            'container_cpu_usage_seconds_total',
            'container_memory_working_set_bytes',
        ),
        validation_query='count(kube_pod_owner)',
    ),
    'resource_requests_limits': CapabilityDefinition(
        'resource_requests_limits',
        'Resource Requests and Limits',
        ('Capacity', 'Top Consumers', 'Forecast'),
        'Capacity pressure, overcommit, and request/limit analysis are incomplete.',
        'kube-state-metrics scrape pipeline',
        'Expose kube_pod_container_resource_requests and kube_pod_container_resource_limits with resource, unit, namespace, pod, and node labels.',
        expected_signals=('kube_pod_container_resource_requests', 'kube_pod_container_resource_limits'),
    ),
    'pvc_usage': CapabilityDefinition(
        'pvc_usage',
        'PVC Usage Contract',
        ('Storage Analytics', 'Storage Forecast'),
        'PVC usage, available capacity, and storage forecast are unavailable.',
        'Kubelet metrics and Prometheus scrape configuration',
        'Enable kubelet volume statistics scraping and ensure the metrics are forwarded to the configured Prometheus or Thanos Query endpoint.',
        expected_signals=(
            'kubelet_volume_stats_capacity_bytes',
            'kubelet_volume_stats_used_bytes',
            'kubelet_volume_stats_available_bytes',
        ),
        validation_query='count(kubelet_volume_stats_used_bytes)',
    ),
    'node_filesystem_identity': CapabilityDefinition(
        'node_filesystem_identity',
        'Storage Filesystem Contract',
        ('Storage Analytics',),
        'Storage Analytics cannot calculate node filesystem capacity and availability reliably.',
        'node_exporter relabeling or recording rules',
        'Run the validation query against the configured Prometheus or Thanos endpoint. When the metric exists but the contract query returns no canonical node series, review query filters, recording rules, and label transformation before changing the exporter.',
        expected_signals=('node_filesystem_size_bytes{node!=""}', 'node_filesystem_avail_bytes{node!=""}'),
        validation_query=(
            'node_filesystem_size_bytes{mountpoint="/var",fstype!~"tmpfs|overlay"}\n'
            'node_filesystem_avail_bytes{mountpoint="/var",fstype!~"tmpfs|overlay"}\n'
            'node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}\n'
            'node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}'
        ),
    ),
    'long_term_history': CapabilityDefinition(
        'long_term_history',
        'Long-Term Metric History',
        ('Forecast', 'Historical reports'),
        'Long-range trend and forecast windows are degraded or unavailable.',
        'Prometheus retention or Thanos Store pipeline',
        'Increase Prometheus retention or ensure historical blocks are queryable through Thanos Query for the required horizons.',
        validation_query='count(up)',
    ),
}


def definition(key: str) -> CapabilityDefinition | None:
    return CAPABILITIES.get(key)


CAPABILITY_KEYS = tuple(CAPABILITIES)
COMPATIBILITY_PROFILES = ('prometheus-v2', 'prometheus-v3')


BINDING_CAPABILITY_KEYS = (
    'metrics',
    'capacity',
    'utilization',
    'storage',
    'workload',
    'forecast',
    'top_consumers',
    'alert_metrics',
)
