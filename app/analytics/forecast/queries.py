# app/analytics/forecast/queries.py

from __future__ import annotations

NAMESPACE_ACTIVE_QUERY = (
    'kube_namespace_status_phase{phase="Active"} == 1'
)

CPU_USAGE_QUERY = (
    'sum('
    'rate(container_cpu_usage_seconds_total{container!="", image!=""}[5m])'
    ')'
)

CPU_USAGE_BY_NAMESPACE_QUERY = (
    'sum('
    'rate(container_cpu_usage_seconds_total{'
    'container!="", image!="", namespace="$namespace"'
    '}[5m])'
    ')'
)

MEMORY_USAGE_QUERY = (
    'sum('
    'container_memory_working_set_bytes{container!="", image!=""}'
    ')'
)

MEMORY_USAGE_BY_NAMESPACE_QUERY = (
    'sum('
    'container_memory_working_set_bytes{'
    'container!="", image!="", namespace="$namespace"'
    '}'
    ')'
)

STORAGE_USAGE_QUERY = (
    'sum('
    'kubelet_volume_stats_used_bytes{persistentvolumeclaim!=""}'
    ')'
)

STORAGE_USAGE_BY_NAMESPACE_QUERY = (
    'sum('
    'kubelet_volume_stats_used_bytes{'
    'persistentvolumeclaim!="", namespace="$namespace"'
    '}'
    ')'
)

POD_USAGE_QUERY = (
    'sum('
    'kube_pod_status_phase{phase="Running"} == 1'
    ')'
)

POD_USAGE_BY_NAMESPACE_QUERY = (
    'sum('
    'kube_pod_status_phase{phase="Running", namespace="$namespace"} == 1'
    ')'
)

CPU_WORKER_CAPACITY_QUERY = (
    'sum('
    'kube_node_status_allocatable{resource="cpu", unit="core"} '
    'unless on(node) '
    'kube_node_role{role=~"control-plane|master"}'
    ')'
)

MEMORY_WORKER_CAPACITY_QUERY = (
    'sum('
    'kube_node_status_allocatable{resource="memory", unit="byte"} '
    'unless on(node) '
    'kube_node_role{role=~"control-plane|master"}'
    ')'
)

POD_WORKER_CAPACITY_QUERY = (
    'sum('
    'kube_node_status_allocatable{resource="pods", unit="integer"} '
    'unless on(node) '
    'kube_node_role{role=~"control-plane|master"}'
    ')'
)

STORAGE_CAPACITY_QUERY = (
    'sum('
    'kubelet_volume_stats_capacity_bytes{persistentvolumeclaim!=""}'
    ')'
)

STORAGE_CAPACITY_BY_NAMESPACE_QUERY = (
    'sum('
    'kubelet_volume_stats_capacity_bytes{'
    'persistentvolumeclaim!="", namespace="$namespace"'
    '}'
    ')'
)
