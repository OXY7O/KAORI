from __future__ import annotations

from app.integrations.prometheus.query_profiles.types import QueryDefinition

FORECAST_QUERIES: dict[str, QueryDefinition] = {
    'analytics.forecast.queries.NAMESPACE_ACTIVE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.NAMESPACE_ACTIVE_QUERY',
        expression='max by (namespace) (kube_namespace_status_phase{phase="Active"} == 1)',
        domain='app.analytics.forecast',
        required_metrics=('kube_namespace_status_phase',),
        required_labels=(('kube_namespace_status_phase', ('namespace', 'phase')),),
    ),
    'analytics.forecast.queries.CPU_USAGE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.CPU_USAGE_QUERY',
        expression='''sum(
  (
    max by (namespace, pod, container) (
      rate(container_cpu_usage_seconds_total{container!="",image!=""}[5m])
    )
    * on(namespace, pod) group_left(node)
    max by (namespace, pod, node) (
      kube_pod_info{namespace!="",pod!=""}
    )
  )
  and on(node)
  (
    max by (node) (
      kube_node_status_condition{condition="Ready",status="true"} == 1
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_pod_info', 'kube_node_status_condition', 'kube_node_role'),
        required_labels=(('container_cpu_usage_seconds_total', ('container', 'image', 'namespace', 'pod')), ('kube_pod_info', ('namespace', 'pod', 'node')), ('kube_node_status_condition', ('node', 'condition', 'status')), ('kube_node_role', ('node', 'role'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.CPU_USAGE_BY_NAMESPACE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.CPU_USAGE_BY_NAMESPACE_QUERY',
        expression='''sum(
  (
    max by (namespace, pod, container) (
      rate(container_cpu_usage_seconds_total{container!="",image!="",namespace="$namespace"}[5m])
    )
    * on(namespace, pod) group_left(node)
    max by (namespace, pod, node) (
      kube_pod_info{namespace="$namespace",pod!=""}
    )
  )
  and on(node)
  (
    max by (node) (
      kube_node_status_condition{condition="Ready",status="true"} == 1
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_pod_info', 'kube_node_status_condition', 'kube_node_role'),
        required_labels=(('container_cpu_usage_seconds_total', ('container', 'image', 'namespace', 'pod')), ('kube_pod_info', ('namespace', 'pod', 'node')), ('kube_node_status_condition', ('node', 'condition', 'status')), ('kube_node_role', ('node', 'role'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.MEMORY_USAGE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.MEMORY_USAGE_QUERY',
        expression='''sum(
  (
    max by (namespace, pod, container) (
      container_memory_working_set_bytes{container!="",image!=""}
    )
    * on(namespace, pod) group_left(node)
    max by (namespace, pod, node) (
      kube_pod_info{namespace!="",pod!=""}
    )
  )
  and on(node)
  (
    max by (node) (
      kube_node_status_condition{condition="Ready",status="true"} == 1
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('container_memory_working_set_bytes', 'kube_pod_info', 'kube_node_status_condition', 'kube_node_role'),
        required_labels=(('container_memory_working_set_bytes', ('container', 'image', 'namespace', 'pod')), ('kube_pod_info', ('namespace', 'pod', 'node')), ('kube_node_status_condition', ('node', 'condition', 'status')), ('kube_node_role', ('node', 'role'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.MEMORY_USAGE_BY_NAMESPACE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.MEMORY_USAGE_BY_NAMESPACE_QUERY',
        expression='''sum(
  (
    max by (namespace, pod, container) (
      container_memory_working_set_bytes{container!="",image!="",namespace="$namespace"}
    )
    * on(namespace, pod) group_left(node)
    max by (namespace, pod, node) (
      kube_pod_info{namespace="$namespace",pod!=""}
    )
  )
  and on(node)
  (
    max by (node) (
      kube_node_status_condition{condition="Ready",status="true"} == 1
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('container_memory_working_set_bytes', 'kube_pod_info', 'kube_node_status_condition', 'kube_node_role'),
        required_labels=(('container_memory_working_set_bytes', ('container', 'image', 'namespace', 'pod')), ('kube_pod_info', ('namespace', 'pod', 'node')), ('kube_node_status_condition', ('node', 'condition', 'status')), ('kube_node_role', ('node', 'role'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.STORAGE_USAGE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.STORAGE_USAGE_QUERY',
        expression='''sum(
  max by (namespace, persistentvolumeclaim) (
    kubelet_volume_stats_used_bytes{persistentvolumeclaim!=""}
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kubelet_volume_stats_used_bytes',),
        required_labels=(('kubelet_volume_stats_used_bytes', ('namespace', 'persistentvolumeclaim')),),
        required_history='90d',
    ),
    'analytics.forecast.queries.STORAGE_USAGE_BY_NAMESPACE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.STORAGE_USAGE_BY_NAMESPACE_QUERY',
        expression='''sum(
  max by (namespace, persistentvolumeclaim) (
    kubelet_volume_stats_used_bytes{persistentvolumeclaim!="",namespace="$namespace"}
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kubelet_volume_stats_used_bytes',),
        required_labels=(('kubelet_volume_stats_used_bytes', ('namespace', 'persistentvolumeclaim')),),
        required_history='90d',
    ),
    'analytics.forecast.queries.POD_USAGE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.POD_USAGE_QUERY',
        expression='''sum(
  (
    max by (namespace, pod) (
      kube_pod_status_phase{phase=~"Pending|Running"} == 1
    )
    * on(namespace, pod) group_left(node)
    max by (namespace, pod, node) (
      kube_pod_info{namespace!="",pod!=""}
    )
  )
  and on(node)
  (
    max by (node) (
      kube_node_status_condition{condition="Ready",status="true"} == 1
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kube_pod_status_phase', 'kube_pod_info', 'kube_node_status_condition', 'kube_node_role'),
        required_labels=(('kube_pod_status_phase', ('namespace', 'pod', 'phase')), ('kube_pod_info', ('namespace', 'pod', 'node')), ('kube_node_status_condition', ('node', 'condition', 'status')), ('kube_node_role', ('node', 'role'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.POD_USAGE_BY_NAMESPACE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.POD_USAGE_BY_NAMESPACE_QUERY',
        expression='''sum(
  (
    max by (namespace, pod) (
      kube_pod_status_phase{phase=~"Pending|Running",namespace="$namespace"} == 1
    )
    * on(namespace, pod) group_left(node)
    max by (namespace, pod, node) (
      kube_pod_info{namespace="$namespace",pod!=""}
    )
  )
  and on(node)
  (
    max by (node) (
      kube_node_status_condition{condition="Ready",status="true"} == 1
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kube_pod_status_phase', 'kube_pod_info', 'kube_node_status_condition', 'kube_node_role'),
        required_labels=(('kube_pod_status_phase', ('namespace', 'pod', 'phase')), ('kube_pod_info', ('namespace', 'pod', 'node')), ('kube_node_status_condition', ('node', 'condition', 'status')), ('kube_node_role', ('node', 'role'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.CPU_WORKER_CAPACITY_QUERY': QueryDefinition(
        key='analytics.forecast.queries.CPU_WORKER_CAPACITY_QUERY',
        expression='''sum(
  (
    max by (node) (
      kube_node_status_allocatable{resource="cpu",unit="core"}
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
  and on(node)
  max by (node) (
    kube_node_status_condition{condition="Ready",status="true"} == 1
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(('kube_node_status_allocatable', ('node', 'resource', 'unit')), ('kube_node_role', ('node', 'role')), ('kube_node_status_condition', ('node', 'condition', 'status'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.MEMORY_WORKER_CAPACITY_QUERY': QueryDefinition(
        key='analytics.forecast.queries.MEMORY_WORKER_CAPACITY_QUERY',
        expression='''sum(
  (
    max by (node) (
      kube_node_status_allocatable{resource="memory",unit="byte"}
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
  and on(node)
  max by (node) (
    kube_node_status_condition{condition="Ready",status="true"} == 1
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(('kube_node_status_allocatable', ('node', 'resource', 'unit')), ('kube_node_role', ('node', 'role')), ('kube_node_status_condition', ('node', 'condition', 'status'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.POD_WORKER_CAPACITY_QUERY': QueryDefinition(
        key='analytics.forecast.queries.POD_WORKER_CAPACITY_QUERY',
        expression='''sum(
  (
    max by (node) (
      kube_node_status_allocatable{resource="pods",unit="integer"}
    )
    unless on(node)
    max by (node) (
      kube_node_role{role=~"control-plane|master"}
    )
  )
  and on(node)
  max by (node) (
    kube_node_status_condition{condition="Ready",status="true"} == 1
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(('kube_node_status_allocatable', ('node', 'resource', 'unit')), ('kube_node_role', ('node', 'role')), ('kube_node_status_condition', ('node', 'condition', 'status'))),
        required_history='90d',
    ),
    'analytics.forecast.queries.STORAGE_CAPACITY_QUERY': QueryDefinition(
        key='analytics.forecast.queries.STORAGE_CAPACITY_QUERY',
        expression='''sum(
  max by (namespace, persistentvolumeclaim) (
    kubelet_volume_stats_capacity_bytes{persistentvolumeclaim!=""}
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kubelet_volume_stats_capacity_bytes',),
        required_labels=(('kubelet_volume_stats_capacity_bytes', ('namespace', 'persistentvolumeclaim')),),
        required_history='90d',
    ),
    'analytics.forecast.queries.STORAGE_CAPACITY_BY_NAMESPACE_QUERY': QueryDefinition(
        key='analytics.forecast.queries.STORAGE_CAPACITY_BY_NAMESPACE_QUERY',
        expression='''sum(
  max by (namespace, persistentvolumeclaim) (
    kubelet_volume_stats_capacity_bytes{persistentvolumeclaim!="",namespace="$namespace"}
  )
)''',
        domain='app.analytics.forecast',
        required_metrics=('kubelet_volume_stats_capacity_bytes',),
        required_labels=(('kubelet_volume_stats_capacity_bytes', ('namespace', 'persistentvolumeclaim')),),
        required_history='90d',
    ),
}
