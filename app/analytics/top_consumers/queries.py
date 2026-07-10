# app/analytics/top_consumers/queries.py

from __future__ import annotations


NAMESPACE_ACTIVE_QUERY = (
    'kube_namespace_status_phase{phase="Active"} == 1'
)


TOP_CPU_CONSUMERS_QUERY = (
    'topk(50, '
    'sum by (namespace, pod, container) ('
    'rate(container_cpu_usage_seconds_total{container!="", image!=""}[5m])'
    ')'
    ')'
)

TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY = (
    'topk(50, '
    'sum by (namespace, pod, container) ('
    'rate(container_cpu_usage_seconds_total{'
    'container!="", image!="", namespace="$namespace"'
    '}[5m])'
    ')'
    ')'
)

CPU_REQUEST_BY_CONTAINER_QUERY = (
    'sum by (namespace, pod, container) ('
    'kube_pod_container_resource_requests{resource="cpu", unit="core"}'
    ')'
)

CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY = (
    'sum by (namespace, pod, container) ('
    'kube_pod_container_resource_requests{'
    'resource="cpu", unit="core", namespace="$namespace"'
    '}'
    ')'
)

CPU_LIMIT_BY_CONTAINER_QUERY = (
    'sum by (namespace, pod, container) ('
    'kube_pod_container_resource_limits{resource="cpu", unit="core"}'
    ')'
)

CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY = (
    'sum by (namespace, pod, container) ('
    'kube_pod_container_resource_limits{'
    'resource="cpu", unit="core", namespace="$namespace"'
    '}'
    ')'
)

CPU_ALLOCATABLE_QUERY = (
    'sum('
    'kube_node_status_allocatable{resource="cpu", unit="core"} '
    'unless on(node) kube_node_role{role=~"control-plane|master"}'
    ')'
)

TOTAL_CPU_USAGE_QUERY = (
    'sum(rate(container_cpu_usage_seconds_total{container!="", image!=""}[5m]))'
)

TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY = (
    'sum(rate(container_cpu_usage_seconds_total{'
    'container!="", image!="", namespace="$namespace"'
    '}[5m]))'
)


TOP_MEMORY_CONSUMERS_QUERY = (
    'topk(50, '
    'sum by (namespace, pod, container) ('
    'container_memory_working_set_bytes{container!="", image!=""}'
    ')'
    ')'
)

TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY = (
    'topk(50, '
    'sum by (namespace, pod, container) ('
    'container_memory_working_set_bytes{'
    'container!="", image!="", namespace="$namespace"'
    '}'
    ')'
    ')'
)

MEMORY_REQUEST_BY_CONTAINER_QUERY = (
    'sum by (namespace, pod, container) ('
    'kube_pod_container_resource_requests{resource="memory", unit="byte"}'
    ')'
)

MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY = (
    'sum by (namespace, pod, container) ('
    'kube_pod_container_resource_requests{'
    'resource="memory", unit="byte", namespace="$namespace"'
    '}'
    ')'
)

MEMORY_LIMIT_BY_CONTAINER_QUERY = (
    'sum by (namespace, pod, container) ('
    'kube_pod_container_resource_limits{resource="memory", unit="byte"}'
    ')'
)

MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY = (
    'sum by (namespace, pod, container) ('
    'kube_pod_container_resource_limits{'
    'resource="memory", unit="byte", namespace="$namespace"'
    '}'
    ')'
)

MEMORY_ALLOCATABLE_QUERY = (
    'sum('
    'kube_node_status_allocatable{resource="memory", unit="byte"} '
    'unless on(node) kube_node_role{role=~"control-plane|master"}'
    ')'
)

TOTAL_MEMORY_USAGE_QUERY = (
    'sum(container_memory_working_set_bytes{container!="", image!=""})'
)

TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY = (
    'sum(container_memory_working_set_bytes{'
    'container!="", image!="", namespace="$namespace"'
    '})'
)


TOP_POD_CONSUMERS_QUERY = (
    'topk(50, '
    'sum by (namespace) ('
    'kube_pod_status_phase{phase="Running"} == 1'
    ')'
    ')'
)

TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY = (
    'topk(50, '
    'sum by (namespace) ('
    'kube_pod_status_phase{phase="Running", namespace="$namespace"} == 1'
    ')'
    ')'
)

POD_CAPACITY_QUERY = (
    'sum('
    'kube_node_status_allocatable{resource="pods", unit="integer"} '
    'unless on(node) kube_node_role{role=~"control-plane|master"}'
    ')'
)

TOTAL_RUNNING_PODS_QUERY = (
    'sum(kube_pod_status_phase{phase="Running"} == 1)'
)

TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY = (
    'sum(kube_pod_status_phase{phase="Running", namespace="$namespace"} == 1)'
)


TOP_PVC_CONSUMERS_QUERY = (
    'topk(50, '
    'kubelet_volume_stats_used_bytes{persistentvolumeclaim!=""}'
    ')'
)

TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY = (
    'topk(50, '
    'kubelet_volume_stats_used_bytes{'
    'persistentvolumeclaim!="", namespace="$namespace"'
    '}'
    ')'
)

PVC_CAPACITY_BY_CLAIM_QUERY = (
    'kubelet_volume_stats_capacity_bytes{persistentvolumeclaim!=""}'
)

PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY = (
    'kubelet_volume_stats_capacity_bytes{'
    'persistentvolumeclaim!="", namespace="$namespace"'
    '}'
)

PVC_AVAILABLE_BY_CLAIM_QUERY = (
    'kubelet_volume_stats_available_bytes{persistentvolumeclaim!=""}'
)

PVC_AVAILABLE_BY_CLAIM_NAMESPACE_QUERY = (
    'kubelet_volume_stats_available_bytes{'
    'persistentvolumeclaim!="", namespace="$namespace"'
    '}'
)

TOTAL_PVC_USED_QUERY = (
    'sum(kubelet_volume_stats_used_bytes{persistentvolumeclaim!=""})'
)

TOTAL_PVC_USED_BY_NAMESPACE_QUERY = (
    'sum(kubelet_volume_stats_used_bytes{'
    'persistentvolumeclaim!="", namespace="$namespace"'
    '})'
)

TOTAL_PVC_CAPACITY_QUERY = (
    'sum(kubelet_volume_stats_capacity_bytes{persistentvolumeclaim!=""})'
)

TOTAL_PVC_CAPACITY_BY_NAMESPACE_QUERY = (
    'sum(kubelet_volume_stats_capacity_bytes{'
    'persistentvolumeclaim!="", namespace="$namespace"'
    '})'
)
