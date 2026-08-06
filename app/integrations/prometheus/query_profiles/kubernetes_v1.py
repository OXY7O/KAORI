from __future__ import annotations

from app.integrations.prometheus.query_profiles import alerts_v1
from app.integrations.prometheus.query_profiles.forecast_v1 import FORECAST_QUERIES
from app.integrations.prometheus.query_profiles.types import QueryDefinition

PROFILE_KEY = 'promql-kubernetes-v1'
PROFILE_VERSION = 1

_NODE_ROLE_LABEL = ('kube_node_role', ('node', 'role'))
_ALLOCATABLE_NODE_RESOURCE_LABEL = ('kube_node_status_allocatable', ('node', 'resource', 'unit'))
_CONTAINER_CPU_NODE_LABEL = ('container_cpu_usage_seconds_total', ('container', 'node'))
_CONTAINER_MEMORY_NODE_LABEL = ('container_memory_working_set_bytes', ('container', 'node'))
_POD_PHASE_LABEL = ('kube_pod_status_phase', ('namespace', 'pod', 'phase'))
_POD_INFO_LABEL = ('kube_pod_info', ('namespace', 'pod', 'node'))

_NODE_READY_LABEL = (
    'kube_node_status_condition',
    ('node', 'condition', 'status'),
)
_TC_WORKER_METRICS = (
    'kube_pod_info',
    'kube_pod_status_phase',
    'kube_node_status_condition',
    'kube_node_role',
)
_TC_WORKER_LABELS = (
    _POD_INFO_LABEL,
    _POD_PHASE_LABEL,
    _NODE_READY_LABEL,
    _NODE_ROLE_LABEL,
)

def _tc_scope(namespace: str) -> str:
    return f'namespace="{namespace}"' if namespace else 'namespace!=""'

def _tc_active_worker_pods(
    namespace: str,
    *,
    phases: str = 'Pending|Running',
) -> str:
    scope = _tc_scope(namespace)
    return (
        'max by (namespace, pod) (\n'
        '  (\n'
        f'    kube_pod_info{{{scope}, pod!="", node!=""}}\n'
        '    and on(node)\n'
        '    (\n'
        '      (kube_node_status_condition{condition="Ready", status="true"} == 1)\n'
        '      unless on(node)\n'
        '      kube_node_role{role=~"control-plane|master"}\n'
        '    )\n'
        '  )\n'
        '  and on(namespace, pod)\n'
        '  max by (namespace, pod) (\n'
        f'    kube_pod_status_phase{{{scope}, pod!="", phase=~"{phases}"}} == 1\n'
        '  )\n'
        ')'
    )

def _tc_container_signal(signal: str, namespace: str) -> str:
    return (
        'max by (namespace, pod, container) (\n'
        '  max by (namespace, pod, container) (\n'
        f'    {signal}\n'
        '  )\n'
        '  and on(namespace, pod)\n'
        f'  {_tc_active_worker_pods(namespace)}\n'
        ')'
    )

def _tc_cpu_signal(namespace: str) -> str:
    scope = _tc_scope(namespace)
    return _tc_container_signal(
        'rate('
        f'container_cpu_usage_seconds_total{{{scope}, pod!="", container!="", '
        'container!="POD", image!=""}[5m])',
        namespace,
    )

def _tc_memory_signal(namespace: str) -> str:
    scope = _tc_scope(namespace)
    return _tc_container_signal(
        f'container_memory_working_set_bytes{{{scope}, pod!="", container!="", '
        'container!="POD", image!=""}',
        namespace,
    )

def _tc_resource_signal(namespace: str, *, resource: str, kind: str) -> str:
    scope = _tc_scope(namespace)
    metric = f'kube_pod_container_resource_{kind}'
    unit = 'core' if resource == 'cpu' else 'byte'
    return _tc_container_signal(
        f'{metric}{{{scope}, pod!="", container!="", '
        f'resource="{resource}", unit="{unit}"}}',
        namespace,
    )

def _tc_pod_owner(namespace: str) -> str:
    scope = _tc_scope(namespace)
    return (
        'max by (namespace, pod, owner_kind, owner_name, owner_is_controller) (\n'
        f'  kube_pod_owner{{{scope}, pod!=""}}\n'
        ')\n'
        'and on(namespace, pod)\n'
        f'{_tc_active_worker_pods(namespace)}'
    )

def _tc_pod_count(namespace: str) -> str:
    return f'sum by (namespace) (\n{_tc_active_worker_pods(namespace, phases="Running")}\n)'

def _tc_ready_worker_capacity(resource: str, unit: str) -> str:
    return (
        'sum(\n'
        '  (\n'
        f'    kube_node_status_allocatable{{resource="{resource}", unit="{unit}"}}\n'
        '    unless on(node)\n'
        '    kube_node_role{role=~"control-plane|master"}\n'
        '  )\n'
        '  and on(node)\n'
        '  (kube_node_status_condition{condition="Ready", status="true"} == 1)\n'
        ')'
    )

def _tc_pvc_signal(namespace: str, metric: str) -> str:
    scope = _tc_scope(namespace)
    return (
        'max by (namespace, persistentvolumeclaim) (\n'
        f'  {metric}{{{scope}, persistentvolumeclaim!=""}}\n'
        ')'
    )

def _tc_definition(
    key: str,
    expression: str,
    *,
    metrics: tuple[str, ...],
    labels: tuple[tuple[str, tuple[str, ...]], ...],
    worker_scoped: bool = False,
    worker_capacity: bool = False,
) -> QueryDefinition:
    required_metrics = metrics
    required_labels = labels
    if worker_scoped:
        required_metrics = tuple(dict.fromkeys((*metrics, *_TC_WORKER_METRICS)))
        required_labels = tuple(dict.fromkeys((*labels, *_TC_WORKER_LABELS)))
    elif worker_capacity:
        required_metrics = tuple(
            dict.fromkeys(
                (*metrics, 'kube_node_status_condition', 'kube_node_role')
            )
        )
        required_labels = tuple(
            dict.fromkeys((*labels, _NODE_READY_LABEL, _NODE_ROLE_LABEL))
        )
    return QueryDefinition(
        key=key,
        expression=expression,
        domain='app.analytics.top_consumers',
        required_metrics=required_metrics,
        required_labels=required_labels,
    )


QUERIES: dict[str, QueryDefinition] = {
    'prometheus.queries.CLUSTER_NODE_COUNT': QueryDefinition(
        key='prometheus.queries.CLUSTER_NODE_COUNT',
        expression='count(kube_node_info)',
        domain='app.prometheus',
        required_metrics=('kube_node_info',),
        required_labels=(),
    ),
    'prometheus.queries.CLUSTER_NAMESPACE_COUNT': QueryDefinition(
        key='prometheus.queries.CLUSTER_NAMESPACE_COUNT',
        expression='count(kube_namespace_labels)',
        domain='app.prometheus',
        required_metrics=('kube_namespace_labels',),
        required_labels=(),
    ),
    'prometheus.queries.CLUSTER_POD_COUNT': QueryDefinition(
        key='prometheus.queries.CLUSTER_POD_COUNT',
        expression='count(kube_pod_info)',
        domain='app.prometheus',
        required_metrics=('kube_pod_info',),
        required_labels=(),
    ),
    'prometheus.queries.CLUSTER_CPU_CAPACITY': QueryDefinition(
        key='prometheus.queries.CLUSTER_CPU_CAPACITY',
        expression='sum(\n    kube_node_status_capacity{\n        resource="cpu"\n    }\n)',
        domain='app.prometheus',
        required_metrics=('kube_node_status_capacity',),
        required_labels=(('kube_node_status_capacity', ('resource',)),),
    ),
    'prometheus.queries.CLUSTER_CPU_USAGE': QueryDefinition(
        key='prometheus.queries.CLUSTER_CPU_USAGE',
        expression='sum(\n    rate(\n        container_cpu_usage_seconds_total{\n            container!="",\n            container!="POD"\n        }[5m]\n    )\n)',
        domain='app.prometheus',
        required_metrics=('container_cpu_usage_seconds_total',),
        required_labels=(('container_cpu_usage_seconds_total', ('container',)),),
    ),
    'prometheus.queries.CLUSTER_CPU_UTILIZATION': QueryDefinition(
        key='prometheus.queries.CLUSTER_CPU_UTILIZATION',
        expression='(\n    sum(\n        rate(\n            container_cpu_usage_seconds_total{\n                container!="",\n                container!="POD"\n            }[5m]\n        )\n    )\n/\n    sum(\n        kube_node_status_capacity{\n            resource="cpu"\n        }\n    )\n) * 100',
        domain='app.prometheus',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_node_status_capacity'),
        required_labels=(
            ('container_cpu_usage_seconds_total', ('container',)),
            ('kube_node_status_capacity', ('resource',)),
        ),
    ),
    'prometheus.queries.CLUSTER_MEMORY_CAPACITY': QueryDefinition(
        key='prometheus.queries.CLUSTER_MEMORY_CAPACITY',
        expression='sum(\n    kube_node_status_capacity{\n        resource="memory"\n    }\n)',
        domain='app.prometheus',
        required_metrics=('kube_node_status_capacity',),
        required_labels=(('kube_node_status_capacity', ('resource',)),),
    ),
    'prometheus.queries.CLUSTER_MEMORY_USAGE': QueryDefinition(
        key='prometheus.queries.CLUSTER_MEMORY_USAGE',
        expression='sum(\n    container_memory_working_set_bytes{\n        container!="",\n        container!="POD"\n    }\n)',
        domain='app.prometheus',
        required_metrics=('container_memory_working_set_bytes',),
        required_labels=(('container_memory_working_set_bytes', ('container',)),),
    ),
    'prometheus.queries.CLUSTER_MEMORY_UTILIZATION': QueryDefinition(
        key='prometheus.queries.CLUSTER_MEMORY_UTILIZATION',
        expression='(\n    sum(\n        container_memory_working_set_bytes{\n            container!="",\n            container!="POD"\n        }\n    )\n/\n    sum(\n        kube_node_status_capacity{\n            resource="memory"\n        }\n    )\n) * 100',
        domain='app.prometheus',
        required_metrics=('container_memory_working_set_bytes', 'kube_node_status_capacity'),
        required_labels=(
            ('container_memory_working_set_bytes', ('container',)),
            ('kube_node_status_capacity', ('resource',)),
        ),
    ),
    'prometheus.queries.CLUSTER_STORAGE_CAPACITY': QueryDefinition(
        key='prometheus.queries.CLUSTER_STORAGE_CAPACITY',
        expression='sum(\n    kubelet_volume_stats_capacity_bytes\n)',
        domain='app.prometheus',
        required_metrics=('kubelet_volume_stats_capacity_bytes',),
        required_labels=(),
    ),
    'prometheus.queries.CLUSTER_STORAGE_USAGE': QueryDefinition(
        key='prometheus.queries.CLUSTER_STORAGE_USAGE',
        expression='sum(\n    kubelet_volume_stats_used_bytes\n)',
        domain='app.prometheus',
        required_metrics=('kubelet_volume_stats_used_bytes',),
        required_labels=(),
    ),
    'prometheus.queries.CLUSTER_STORAGE_AVAILABLE': QueryDefinition(
        key='prometheus.queries.CLUSTER_STORAGE_AVAILABLE',
        expression='sum(\n    kubelet_volume_stats_available_bytes\n)',
        domain='app.prometheus',
        required_metrics=('kubelet_volume_stats_available_bytes',),
        required_labels=(),
    ),
    'prometheus.queries.CLUSTER_STORAGE_UTILIZATION': QueryDefinition(
        key='prometheus.queries.CLUSTER_STORAGE_UTILIZATION',
        expression='(\n    sum(\n        kubelet_volume_stats_used_bytes\n    )\n/\n    sum(\n        kubelet_volume_stats_capacity_bytes\n    )\n) * 100',
        domain='app.prometheus',
        required_metrics=('kubelet_volume_stats_used_bytes', 'kubelet_volume_stats_capacity_bytes'),
        required_labels=(),
    ),
    'prometheus.queries.TOP_CPU_PODS': QueryDefinition(
        key='prometheus.queries.TOP_CPU_PODS',
        expression='topk(\n    10,\n    sum by(namespace,pod)(\n        rate(\n            container_cpu_usage_seconds_total{\n                container!="",\n                container!="POD"\n            }[5m]\n        )\n    )\n)',
        domain='app.prometheus',
        required_metrics=('container_cpu_usage_seconds_total',),
        required_labels=(('container_cpu_usage_seconds_total', ('container',)),),
    ),
    'prometheus.queries.TOP_MEMORY_PODS': QueryDefinition(
        key='prometheus.queries.TOP_MEMORY_PODS',
        expression='topk(\n    10,\n    sum by(namespace,pod)(\n        container_memory_working_set_bytes{\n            container!="",\n            container!="POD"\n        }\n    )\n)',
        domain='app.prometheus',
        required_metrics=('container_memory_working_set_bytes',),
        required_labels=(('container_memory_working_set_bytes', ('container',)),),
    ),
    'prometheus.queries.CPU_USAGE_HISTORY': QueryDefinition(
        key='prometheus.queries.CPU_USAGE_HISTORY',
        expression='sum(\n    rate(\n        container_cpu_usage_seconds_total{\n            container!="",\n            container!="POD"\n        }[5m]\n    )\n)',
        domain='app.prometheus',
        required_metrics=('container_cpu_usage_seconds_total',),
        required_labels=(('container_cpu_usage_seconds_total', ('container',)),),
    ),
    'prometheus.queries.MEMORY_USAGE_HISTORY': QueryDefinition(
        key='prometheus.queries.MEMORY_USAGE_HISTORY',
        expression='sum(\n    container_memory_working_set_bytes{\n        container!="",\n        container!="POD"\n    }\n)',
        domain='app.prometheus',
        required_metrics=('container_memory_working_set_bytes',),
        required_labels=(('container_memory_working_set_bytes', ('container',)),),
    ),
    'prometheus.queries.STORAGE_USAGE_HISTORY': QueryDefinition(
        key='prometheus.queries.STORAGE_USAGE_HISTORY',
        expression='sum(\n    kubelet_volume_stats_used_bytes\n)',
        domain='app.prometheus',
        required_metrics=('kubelet_volume_stats_used_bytes',),
        required_labels=(),
    ),
    'analytics.alerts.queries.PROMETHEUS_ALERTS_QUERY': QueryDefinition(
        key='analytics.alerts.queries.PROMETHEUS_ALERTS_QUERY',
        expression=alerts_v1.PROMETHEUS_ALERTS_QUERY,
        domain='app.analytics.alerts',
        required_metrics=('ALERTS',),
        required_labels=(('ALERTS', ('alertstate',)),),
    ),
    'analytics.alerts.queries.PROMETHEUS_FIRING_ALERTS_QUERY': QueryDefinition(
        key='analytics.alerts.queries.PROMETHEUS_FIRING_ALERTS_QUERY',
        expression='ALERTS{alertstate="firing"}',
        domain='app.analytics.alerts',
        required_metrics=('ALERTS',),
        required_labels=(('ALERTS', ('alertstate',)),),
    ),
    'analytics.alerts.queries.POD_RESTART_ANOMALY_QUERY': QueryDefinition(
        key='analytics.alerts.queries.POD_RESTART_ANOMALY_QUERY',
        expression=alerts_v1.POD_RESTART_ANOMALY_QUERY,
        domain='app.analytics.alerts',
        required_metrics=('kube_pod_container_status_restarts_total', 'kube_pod_status_phase'),
        required_labels=(
            ('kube_pod_container_status_restarts_total', ('namespace', 'pod', 'container')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.alerts.queries.POD_NOT_READY_ANOMALY_QUERY': QueryDefinition(
        key='analytics.alerts.queries.POD_NOT_READY_ANOMALY_QUERY',
        expression=alerts_v1.POD_NOT_READY_ANOMALY_QUERY,
        domain='app.analytics.alerts',
        required_metrics=('kube_pod_status_ready', 'kube_pod_status_phase'),
        required_labels=(('kube_pod_status_ready', ('condition', 'namespace', 'pod')), _POD_PHASE_LABEL),
    ),
    'analytics.alerts.queries.CPU_SPIKE_QUERY': QueryDefinition(
        key='analytics.alerts.queries.CPU_SPIKE_QUERY',
        expression='sum by (namespace, pod) (\n  rate(container_cpu_usage_seconds_total{container!="", pod!=""}[5m])\n)',
        domain='app.analytics.alerts',
        required_metrics=('container_cpu_usage_seconds_total',),
        required_labels=(('container_cpu_usage_seconds_total', ('container', 'pod')),),
    ),
    'analytics.alerts.queries.MEMORY_USAGE_QUERY': QueryDefinition(
        key='analytics.alerts.queries.MEMORY_USAGE_QUERY',
        expression='sum by (namespace, pod) (\n  container_memory_working_set_bytes{container!="", pod!=""}\n)',
        domain='app.analytics.alerts',
        required_metrics=('container_memory_working_set_bytes',),
        required_labels=(('container_memory_working_set_bytes', ('container', 'pod')),),
    ),
    'analytics.capacity.queries.CURRENT_WORKER_PODS_QUERY': QueryDefinition(
        key='analytics.capacity.queries.CURRENT_WORKER_PODS_QUERY',
        expression='sum(\n  (\n    (\n      (kube_pod_status_phase{phase="Running"} == 1)\n      * on(namespace, pod) group_left(node)\n      kube_pod_info{node!=""}\n    )\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_pod_status_phase', 'kube_node_role', 'kube_node_status_condition', 'kube_pod_info'),
        required_labels=(
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
            ('kube_pod_info', ('namespace', 'node', 'pod')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.capacity.queries.WORKER_CPU_USAGE_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_CPU_USAGE_QUERY',
        expression='sum(\n  (\n    rate(\n      container_cpu_usage_seconds_total{\n        container!="",\n        container!="POD",\n        node!=""\n      }[5m]\n    )\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('container_cpu_usage_seconds_total', ('container', 'node')),
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
        ),
    ),
    'analytics.capacity.queries.WORKER_MEMORY_USAGE_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_MEMORY_USAGE_QUERY',
        expression='sum(\n  (\n    container_memory_working_set_bytes{\n      container!="",\n      container!="POD",\n      node!=""\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('container_memory_working_set_bytes', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('container_memory_working_set_bytes', ('container', 'node')),
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
        ),
    ),
    'analytics.capacity.queries.WORKER_CPU_REQUESTS_TOTAL_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_CPU_REQUESTS_TOTAL_QUERY',
        expression='sum(\n  (\n    kube_pod_container_resource_requests{\n      resource="cpu",\n      unit="core",\n      namespace!="",\n      pod!="",\n      node!=""\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_pod_container_resource_requests', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
            ('kube_pod_container_resource_requests', ('namespace', 'node', 'pod', 'resource', 'unit')),
        ),
    ),
    'analytics.capacity.queries.WORKER_CPU_LIMITS_TOTAL_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_CPU_LIMITS_TOTAL_QUERY',
        expression='sum(\n  (\n    kube_pod_container_resource_limits{\n      resource="cpu",\n      unit="core",\n      namespace!="",\n      pod!="",\n      node!=""\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_pod_container_resource_limits', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
            ('kube_pod_container_resource_limits', ('namespace', 'node', 'pod', 'resource', 'unit')),
        ),
    ),
    'analytics.capacity.queries.WORKER_MEMORY_REQUESTS_TOTAL_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_MEMORY_REQUESTS_TOTAL_QUERY',
        expression='sum(\n  (\n    kube_pod_container_resource_requests{\n      resource="memory",\n      unit="byte",\n      namespace!="",\n      pod!="",\n      node!=""\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_pod_container_resource_requests', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
            ('kube_pod_container_resource_requests', ('namespace', 'node', 'pod', 'resource', 'unit')),
        ),
    ),
    'analytics.capacity.queries.WORKER_MEMORY_LIMITS_TOTAL_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_MEMORY_LIMITS_TOTAL_QUERY',
        expression='sum(\n  (\n    kube_pod_container_resource_limits{\n      resource="memory",\n      unit="byte",\n      namespace!="",\n      pod!="",\n      node!=""\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_pod_container_resource_limits', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
            ('kube_pod_container_resource_limits', ('namespace', 'node', 'pod', 'resource', 'unit')),
        ),
    ),
    'analytics.capacity.queries.WORKER_CPU_PEAK_QUERY_TEMPLATE': QueryDefinition(
        key='analytics.capacity.queries.WORKER_CPU_PEAK_QUERY_TEMPLATE',
        expression='max_over_time(\n  sum(\n    (\n      rate(\n        container_cpu_usage_seconds_total{\n          namespace!="",\n          container!="",\n          image!="",\n          pod!="",\n          node!=""\n        }[5m]\n      )\n      unless on(node)\n      kube_node_role{role=~"control-plane|master"}\n    )\n    and on(node)\n    (kube_node_status_condition{condition="Ready",status="true"} == 1)\n  )[__TIME_RANGE__:__TIME_STEP__]\n)',
        domain='app.analytics.capacity',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('container_cpu_usage_seconds_total', ('container', 'image', 'namespace', 'node', 'pod')),
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
        ),
    ),
    'analytics.capacity.queries.WORKER_MEMORY_PEAK_QUERY_TEMPLATE': QueryDefinition(
        key='analytics.capacity.queries.WORKER_MEMORY_PEAK_QUERY_TEMPLATE',
        expression='max_over_time(\n  sum(\n    (\n      container_memory_working_set_bytes{\n        namespace!="",\n        container!="",\n        image!="",\n        pod!="",\n        node!=""\n      }\n      unless on(node)\n      kube_node_role{role=~"control-plane|master"}\n    )\n    and on(node)\n    (kube_node_status_condition{condition="Ready",status="true"} == 1)\n  )[__TIME_RANGE__:__TIME_STEP__]\n)',
        domain='app.analytics.capacity',
        required_metrics=('container_memory_working_set_bytes', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('container_memory_working_set_bytes', ('container', 'image', 'namespace', 'node', 'pod')),
            ('kube_node_role', ('role',)),
            ('kube_node_status_condition', ('condition', 'status')),
        ),
    ),
    'analytics.capacity.queries.WORKER_NODE_COUNT_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_NODE_COUNT_QUERY',
        expression='count(\n  kube_node_info\n  unless on(node)\n  kube_node_role{role=~"control-plane|master"}\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_node_info', 'kube_node_role'),
        required_labels=(('kube_node_info', ('node',)), ('kube_node_role', ('node', 'role'))),
    ),
    'analytics.capacity.queries.READY_WORKER_NODE_COUNT_QUERY': QueryDefinition(
        key='analytics.capacity.queries.READY_WORKER_NODE_COUNT_QUERY',
        expression='count(\n  (\n    kube_node_info\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_node_info', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('kube_node_info', ('node',)),
            ('kube_node_role', ('node', 'role')),
            ('kube_node_status_condition', ('node', 'condition', 'status')),
        ),
    ),
    'analytics.capacity.queries.WORKER_CPU_ALLOCATABLE_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_CPU_ALLOCATABLE_QUERY',
        expression='sum(\n  (\n    kube_node_status_allocatable{\n      resource="cpu",\n      unit="core"\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('kube_node_role', ('role',)),
            ('kube_node_status_allocatable', ('node', 'resource', 'unit')),
            ('kube_node_status_condition', ('node', 'condition', 'status')),
        ),
    ),
    'analytics.capacity.queries.WORKER_MEMORY_ALLOCATABLE_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_MEMORY_ALLOCATABLE_QUERY',
        expression='sum(\n  (\n    kube_node_status_allocatable{\n      resource="memory",\n      unit="byte"\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('kube_node_role', ('role',)),
            ('kube_node_status_allocatable', ('node', 'resource', 'unit')),
            ('kube_node_status_condition', ('node', 'condition', 'status')),
        ),
    ),
    'analytics.capacity.queries.WORKER_POD_ALLOCATABLE_QUERY': QueryDefinition(
        key='analytics.capacity.queries.WORKER_POD_ALLOCATABLE_QUERY',
        expression='sum(\n  (\n    kube_node_status_allocatable{\n      resource="pods",\n      unit="integer"\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n  )\n  and on(node)\n  (kube_node_status_condition{condition="Ready",status="true"} == 1)\n)',
        domain='app.analytics.capacity',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role', 'kube_node_status_condition'),
        required_labels=(
            ('kube_node_role', ('role',)),
            ('kube_node_status_allocatable', ('node', 'resource', 'unit')),
            ('kube_node_status_condition', ('node', 'condition', 'status')),
        ),
    ),
    'analytics.storage.queries.NAMESPACE_ACTIVE_QUERY': QueryDefinition(
        key='analytics.storage.queries.NAMESPACE_ACTIVE_QUERY',
        expression='kube_namespace_status_phase{phase="Active"} == 1',
        domain='app.analytics.storage',
        required_metrics=('kube_namespace_status_phase',),
        required_labels=(('kube_namespace_status_phase', ('phase',)),),
    ),
    'analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY': QueryDefinition(
        key='analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY',
        expression='node_filesystem_size_bytes{mountpoint="/var", fstype!~"tmpfs|overlay"}',
        domain='app.analytics.storage',
        required_metrics=('node_filesystem_size_bytes',),
        required_labels=(('node_filesystem_size_bytes', ('mountpoint',)),),
    ),
    'analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY': QueryDefinition(
        key='analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY',
        expression='node_filesystem_avail_bytes{mountpoint="/var", fstype!~"tmpfs|overlay"}',
        domain='app.analytics.storage',
        required_metrics=('node_filesystem_avail_bytes',),
        required_labels=(('node_filesystem_avail_bytes', ('mountpoint',)),),
    ),
    'analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY': QueryDefinition(
        key='analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY',
        expression='node_filesystem_size_bytes{mountpoint="/", fstype!~"tmpfs|overlay"}',
        domain='app.analytics.storage',
        required_metrics=('node_filesystem_size_bytes',),
        required_labels=(('node_filesystem_size_bytes', ('mountpoint',)),),
    ),
    'analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY': QueryDefinition(
        key='analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY',
        expression='node_filesystem_avail_bytes{mountpoint="/", fstype!~"tmpfs|overlay"}',
        domain='app.analytics.storage',
        required_metrics=('node_filesystem_avail_bytes',),
        required_labels=(('node_filesystem_avail_bytes', ('mountpoint',)),),
    ),
    'analytics.storage.queries.PVC_REQUESTED_BY_CLAIM_QUERY': QueryDefinition(
        key='analytics.storage.queries.PVC_REQUESTED_BY_CLAIM_QUERY',
        expression='sum by (namespace, persistentvolumeclaim) (\n  kube_persistentvolumeclaim_resource_requests_storage_bytes\n)',
        domain='app.analytics.storage',
        required_metrics=('kube_persistentvolumeclaim_resource_requests_storage_bytes',),
        required_labels=(),
    ),
    'analytics.storage.queries.PVC_CAPACITY_BY_CLAIM_QUERY': QueryDefinition(
        key='analytics.storage.queries.PVC_CAPACITY_BY_CLAIM_QUERY',
        expression='max by (namespace, persistentvolumeclaim) (\n  kubelet_volume_stats_capacity_bytes{persistentvolumeclaim!=""}\n)',
        domain='app.analytics.storage',
        required_metrics=('kubelet_volume_stats_capacity_bytes',),
        required_labels=(('kubelet_volume_stats_capacity_bytes', ('namespace', 'persistentvolumeclaim')),),
    ),
    'analytics.storage.queries.PVC_USED_BY_CLAIM_QUERY': QueryDefinition(
        key='analytics.storage.queries.PVC_USED_BY_CLAIM_QUERY',
        expression='max by (namespace, persistentvolumeclaim) (\n  kubelet_volume_stats_used_bytes{persistentvolumeclaim!=""}\n)',
        domain='app.analytics.storage',
        required_metrics=('kubelet_volume_stats_used_bytes',),
        required_labels=(),
    ),
    'analytics.storage.queries.PVC_AVAILABLE_BY_CLAIM_QUERY': QueryDefinition(
        key='analytics.storage.queries.PVC_AVAILABLE_BY_CLAIM_QUERY',
        expression='max by (namespace, persistentvolumeclaim) (\n  kubelet_volume_stats_available_bytes{persistentvolumeclaim!=""}\n)',
        domain='app.analytics.storage',
        required_metrics=('kubelet_volume_stats_available_bytes',),
        required_labels=(),
    ),
    'analytics.storage.queries.PVC_STATUS_BY_CLAIM_QUERY': QueryDefinition(
        key='analytics.storage.queries.PVC_STATUS_BY_CLAIM_QUERY',
        expression='kube_persistentvolumeclaim_status_phase',
        domain='app.analytics.storage',
        required_metrics=('kube_persistentvolumeclaim_status_phase',),
        required_labels=(),
    ),
    'analytics.storage.queries.PVC_INFO_QUERY': QueryDefinition(
        key='analytics.storage.queries.PVC_INFO_QUERY',
        expression='kube_persistentvolumeclaim_info',
        domain='app.analytics.storage',
        required_metrics=('kube_persistentvolumeclaim_info',),
        required_labels=(),
    ),
    'analytics.storage.queries.PV_CAPACITY_BY_VOLUME_QUERY': QueryDefinition(
        key='analytics.storage.queries.PV_CAPACITY_BY_VOLUME_QUERY',
        expression='kube_persistentvolume_capacity_bytes',
        domain='app.analytics.storage',
        required_metrics=('kube_persistentvolume_capacity_bytes',),
        required_labels=(),
    ),
    'analytics.storage.queries.PV_INFO_QUERY': QueryDefinition(
        key='analytics.storage.queries.PV_INFO_QUERY',
        expression='kube_persistentvolume_info',
        domain='app.analytics.storage',
        required_metrics=('kube_persistentvolume_info',),
        required_labels=(),
    ),
    'analytics.storage.queries.PV_STATUS_BY_VOLUME_QUERY': QueryDefinition(
        key='analytics.storage.queries.PV_STATUS_BY_VOLUME_QUERY',
        expression='kube_persistentvolume_status_phase',
        domain='app.analytics.storage',
        required_metrics=('kube_persistentvolume_status_phase',),
        required_labels=(),
    ),
    'analytics.top_consumers.queries.NAMESPACE_ACTIVE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.NAMESPACE_ACTIVE_QUERY',
        'max by (namespace) (kube_namespace_status_phase{phase="Active"} == 1)',
        metrics=('kube_namespace_status_phase',),
        labels=(('kube_namespace_status_phase', ('namespace', 'phase')),),
    ),
    'analytics.top_consumers.queries.TOP_CPU_CONSUMERS_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOP_CPU_CONSUMERS_QUERY',
        f'topk(50,\n{_tc_cpu_signal("")}\n)',
        metrics=('container_cpu_usage_seconds_total',),
        labels=(('container_cpu_usage_seconds_total', ('namespace', 'pod', 'container', 'image')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOP_CPU_CONSUMERS_BY_NAMESPACE_QUERY',
        f'topk(50,\n{_tc_cpu_signal("$namespace")}\n)',
        metrics=('container_cpu_usage_seconds_total',),
        labels=(('container_cpu_usage_seconds_total', ('namespace', 'pod', 'container', 'image')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_QUERY': _tc_definition(
        'analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_QUERY',
        _tc_resource_signal('', resource='cpu', kind='requests'),
        metrics=('kube_pod_container_resource_requests',),
        labels=(('kube_pod_container_resource_requests', ('namespace', 'pod', 'container', 'resource', 'unit')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.CPU_REQUEST_BY_CONTAINER_NAMESPACE_QUERY',
        _tc_resource_signal('$namespace', resource='cpu', kind='requests'),
        metrics=('kube_pod_container_resource_requests',),
        labels=(('kube_pod_container_resource_requests', ('namespace', 'pod', 'container', 'resource', 'unit')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_QUERY': _tc_definition(
        'analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_QUERY',
        _tc_resource_signal('', resource='cpu', kind='limits'),
        metrics=('kube_pod_container_resource_limits',),
        labels=(('kube_pod_container_resource_limits', ('namespace', 'pod', 'container', 'resource', 'unit')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.CPU_LIMIT_BY_CONTAINER_NAMESPACE_QUERY',
        _tc_resource_signal('$namespace', resource='cpu', kind='limits'),
        metrics=('kube_pod_container_resource_limits',),
        labels=(('kube_pod_container_resource_limits', ('namespace', 'pod', 'container', 'resource', 'unit')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.CPU_ALLOCATABLE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.CPU_ALLOCATABLE_QUERY',
        _tc_ready_worker_capacity('cpu', 'core'),
        metrics=('kube_node_status_allocatable',),
        labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL,),
        worker_capacity=True,
    ),
    'analytics.top_consumers.queries.TOTAL_CPU_USAGE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOTAL_CPU_USAGE_QUERY',
        f'sum(\n{_tc_cpu_signal("")}\n)',
        metrics=('container_cpu_usage_seconds_total',),
        labels=(('container_cpu_usage_seconds_total', ('namespace', 'pod', 'container', 'image')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOTAL_CPU_USAGE_BY_NAMESPACE_QUERY',
        f'sum(\n{_tc_cpu_signal("$namespace")}\n)',
        metrics=('container_cpu_usage_seconds_total',),
        labels=(('container_cpu_usage_seconds_total', ('namespace', 'pod', 'container', 'image')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_QUERY',
        f'topk(50,\n{_tc_memory_signal("")}\n)',
        metrics=('container_memory_working_set_bytes',),
        labels=(('container_memory_working_set_bytes', ('namespace', 'pod', 'container', 'image')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_BY_NAMESPACE_QUERY',
        f'topk(50,\n{_tc_memory_signal("$namespace")}\n)',
        metrics=('container_memory_working_set_bytes',),
        labels=(('container_memory_working_set_bytes', ('namespace', 'pod', 'container', 'image')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_QUERY': _tc_definition(
        'analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_QUERY',
        _tc_resource_signal('', resource='memory', kind='requests'),
        metrics=('kube_pod_container_resource_requests',),
        labels=(('kube_pod_container_resource_requests', ('namespace', 'pod', 'container', 'resource', 'unit')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.MEMORY_REQUEST_BY_CONTAINER_NAMESPACE_QUERY',
        _tc_resource_signal('$namespace', resource='memory', kind='requests'),
        metrics=('kube_pod_container_resource_requests',),
        labels=(('kube_pod_container_resource_requests', ('namespace', 'pod', 'container', 'resource', 'unit')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_QUERY': _tc_definition(
        'analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_QUERY',
        _tc_resource_signal('', resource='memory', kind='limits'),
        metrics=('kube_pod_container_resource_limits',),
        labels=(('kube_pod_container_resource_limits', ('namespace', 'pod', 'container', 'resource', 'unit')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.MEMORY_LIMIT_BY_CONTAINER_NAMESPACE_QUERY',
        _tc_resource_signal('$namespace', resource='memory', kind='limits'),
        metrics=('kube_pod_container_resource_limits',),
        labels=(('kube_pod_container_resource_limits', ('namespace', 'pod', 'container', 'resource', 'unit')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.MEMORY_ALLOCATABLE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.MEMORY_ALLOCATABLE_QUERY',
        _tc_ready_worker_capacity('memory', 'byte'),
        metrics=('kube_node_status_allocatable',),
        labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL,),
        worker_capacity=True,
    ),
    'analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_QUERY',
        f'sum(\n{_tc_memory_signal("")}\n)',
        metrics=('container_memory_working_set_bytes',),
        labels=(('container_memory_working_set_bytes', ('namespace', 'pod', 'container', 'image')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOTAL_MEMORY_USAGE_BY_NAMESPACE_QUERY',
        f'sum(\n{_tc_memory_signal("$namespace")}\n)',
        metrics=('container_memory_working_set_bytes',),
        labels=(('container_memory_working_set_bytes', ('namespace', 'pod', 'container', 'image')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.POD_OWNER_QUERY': _tc_definition(
        'analytics.top_consumers.queries.POD_OWNER_QUERY',
        _tc_pod_owner(''),
        metrics=('kube_pod_owner',),
        labels=(('kube_pod_owner', ('namespace', 'pod', 'owner_kind', 'owner_name', 'owner_is_controller')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.POD_OWNER_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.POD_OWNER_BY_NAMESPACE_QUERY',
        _tc_pod_owner('$namespace'),
        metrics=('kube_pod_owner',),
        labels=(('kube_pod_owner', ('namespace', 'pod', 'owner_kind', 'owner_name', 'owner_is_controller')),),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOP_POD_CONSUMERS_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOP_POD_CONSUMERS_QUERY',
        f'topk(50, {_tc_pod_count("")})',
        metrics=(),
        labels=(),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOP_POD_CONSUMERS_BY_NAMESPACE_QUERY',
        f'topk(50, {_tc_pod_count("$namespace")})',
        metrics=(),
        labels=(),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.POD_CAPACITY_QUERY': _tc_definition(
        'analytics.top_consumers.queries.POD_CAPACITY_QUERY',
        _tc_ready_worker_capacity('pods', 'integer'),
        metrics=('kube_node_status_allocatable',),
        labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL,),
        worker_capacity=True,
    ),
    'analytics.top_consumers.queries.TOTAL_RUNNING_PODS_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOTAL_RUNNING_PODS_QUERY',
        f'sum({_tc_pod_count("")})',
        metrics=(),
        labels=(),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOTAL_RUNNING_PODS_BY_NAMESPACE_QUERY',
        f'sum({_tc_pod_count("$namespace")})',
        metrics=(),
        labels=(),
        worker_scoped=True,
    ),
    'analytics.top_consumers.queries.TOP_PVC_CONSUMERS_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOP_PVC_CONSUMERS_QUERY',
        f'topk(50,\n{_tc_pvc_signal("", "kubelet_volume_stats_used_bytes")}\n)',
        metrics=('kubelet_volume_stats_used_bytes',),
        labels=(('kubelet_volume_stats_used_bytes', ('namespace', 'persistentvolumeclaim')),),
    ),
    'analytics.top_consumers.queries.TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOP_PVC_CONSUMERS_BY_NAMESPACE_QUERY',
        f'topk(50,\n{_tc_pvc_signal("$namespace", "kubelet_volume_stats_used_bytes")}\n)',
        metrics=('kubelet_volume_stats_used_bytes',),
        labels=(('kubelet_volume_stats_used_bytes', ('namespace', 'persistentvolumeclaim')),),
    ),
    'analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_QUERY': _tc_definition(
        'analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_QUERY',
        _tc_pvc_signal('', 'kubelet_volume_stats_capacity_bytes'),
        metrics=('kubelet_volume_stats_capacity_bytes',),
        labels=(('kubelet_volume_stats_capacity_bytes', ('namespace', 'persistentvolumeclaim')),),
    ),
    'analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.PVC_CAPACITY_BY_CLAIM_NAMESPACE_QUERY',
        _tc_pvc_signal('$namespace', 'kubelet_volume_stats_capacity_bytes'),
        metrics=('kubelet_volume_stats_capacity_bytes',),
        labels=(('kubelet_volume_stats_capacity_bytes', ('namespace', 'persistentvolumeclaim')),),
    ),
    'analytics.top_consumers.queries.TOTAL_PVC_USED_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOTAL_PVC_USED_QUERY',
        f'sum(\n{_tc_pvc_signal("", "kubelet_volume_stats_used_bytes")}\n)',
        metrics=('kubelet_volume_stats_used_bytes',),
        labels=(('kubelet_volume_stats_used_bytes', ('namespace', 'persistentvolumeclaim')),),
    ),
    'analytics.top_consumers.queries.TOTAL_PVC_USED_BY_NAMESPACE_QUERY': _tc_definition(
        'analytics.top_consumers.queries.TOTAL_PVC_USED_BY_NAMESPACE_QUERY',
        f'sum(\n{_tc_pvc_signal("$namespace", "kubelet_volume_stats_used_bytes")}\n)',
        metrics=('kubelet_volume_stats_used_bytes',),
        labels=(('kubelet_volume_stats_used_bytes', ('namespace', 'persistentvolumeclaim')),),
    ),
    'analytics.utilization.queries.CPU_CAPACITY': QueryDefinition(
        key='analytics.utilization.queries.CPU_CAPACITY',
        expression='sum(\n    kube_node_status_allocatable{\n        resource="cpu",\n        unit="core"\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role'),
        required_labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL, _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.CPU_USAGE': QueryDefinition(
        key='analytics.utilization.queries.CPU_USAGE',
        expression='sum(\n    rate(\n        container_cpu_usage_seconds_total{\n            container!="",\n            container!="POD",\n            node!=""\n        }[5m]\n    )\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n)',
        domain='app.analytics.utilization',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_node_role'),
        required_labels=(_CONTAINER_CPU_NODE_LABEL, _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.CPU_UTILIZATION': QueryDefinition(
        key='analytics.utilization.queries.CPU_UTILIZATION',
        expression='(\n    sum(\n        rate(\n            container_cpu_usage_seconds_total{\n                container!="",\n                container!="POD",\n                node!=""\n            }[5m]\n        )\n        unless on(node)\n        kube_node_role{role=~"control-plane|master"}\n    )\n/\n    sum(\n        kube_node_status_allocatable{\n            resource="cpu",\n            unit="core"\n        }\n        unless on(node)\n        kube_node_role{role=~"control-plane|master"}\n    )\n) * 100',
        domain='app.analytics.utilization',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_node_role', 'kube_node_status_allocatable'),
        required_labels=(_CONTAINER_CPU_NODE_LABEL, _NODE_ROLE_LABEL, _ALLOCATABLE_NODE_RESOURCE_LABEL),
    ),
    'analytics.utilization.queries.MEMORY_CAPACITY': QueryDefinition(
        key='analytics.utilization.queries.MEMORY_CAPACITY',
        expression='sum(\n    kube_node_status_allocatable{\n        resource="memory",\n        unit="byte"\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role'),
        required_labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL, _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.MEMORY_USAGE': QueryDefinition(
        key='analytics.utilization.queries.MEMORY_USAGE',
        expression='sum(\n    container_memory_working_set_bytes{\n        container!="",\n        container!="POD",\n        node!=""\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n)',
        domain='app.analytics.utilization',
        required_metrics=('container_memory_working_set_bytes', 'kube_node_role'),
        required_labels=(_CONTAINER_MEMORY_NODE_LABEL, _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.MEMORY_UTILIZATION': QueryDefinition(
        key='analytics.utilization.queries.MEMORY_UTILIZATION',
        expression='(\n    sum(\n        container_memory_working_set_bytes{\n            container!="",\n            container!="POD",\n            node!=""\n        }\n        unless on(node)\n        kube_node_role{role=~"control-plane|master"}\n    )\n/\n    sum(\n        kube_node_status_allocatable{\n            resource="memory",\n            unit="byte"\n        }\n        unless on(node)\n        kube_node_role{role=~"control-plane|master"}\n    )\n) * 100',
        domain='app.analytics.utilization',
        required_metrics=('container_memory_working_set_bytes', 'kube_node_role', 'kube_node_status_allocatable'),
        required_labels=(_CONTAINER_MEMORY_NODE_LABEL, _NODE_ROLE_LABEL, _ALLOCATABLE_NODE_RESOURCE_LABEL),
    ),
    'analytics.utilization.queries.STORAGE_CAPACITY': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_CAPACITY',
        expression='sum(\n    node_filesystem_size_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n)\nor\nsum(\n    node_filesystem_size_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes',),
        required_labels=(('node_filesystem_size_bytes', ('mountpoint',)),),
    ),
    'analytics.utilization.queries.STORAGE_AVAILABLE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_AVAILABLE',
        expression='sum(\n    node_filesystem_avail_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n)\nor\nsum(\n    node_filesystem_avail_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_avail_bytes',),
        required_labels=(('node_filesystem_avail_bytes', ('mountpoint',)),),
    ),
    'analytics.utilization.queries.STORAGE_USAGE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_USAGE',
        expression='sum(\n    node_filesystem_size_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n    -\n    node_filesystem_avail_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n)\nor\nsum(\n    node_filesystem_size_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n    -\n    node_filesystem_avail_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes', 'node_filesystem_avail_bytes'),
        required_labels=(
            ('node_filesystem_avail_bytes', ('mountpoint',)),
            ('node_filesystem_size_bytes', ('mountpoint',)),
        ),
    ),
    'analytics.utilization.queries.STORAGE_UTILIZATION': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_UTILIZATION',
        expression='(\n    sum(\n        node_filesystem_size_bytes{\n            mountpoint="/var",\n            fstype!~"tmpfs|overlay|squashfs"\n        }\n        -\n        node_filesystem_avail_bytes{\n            mountpoint="/var",\n            fstype!~"tmpfs|overlay|squashfs"\n        }\n    )\n/\n    sum(\n        node_filesystem_size_bytes{\n            mountpoint="/var",\n            fstype!~"tmpfs|overlay|squashfs"\n        }\n    )\n) * 100\nor\n(\n    sum(\n        node_filesystem_size_bytes{\n            mountpoint="/",\n            fstype!~"tmpfs|overlay|squashfs"\n        }\n        -\n        node_filesystem_avail_bytes{\n            mountpoint="/",\n            fstype!~"tmpfs|overlay|squashfs"\n        }\n    )\n/\n    sum(\n        node_filesystem_size_bytes{\n            mountpoint="/",\n            fstype!~"tmpfs|overlay|squashfs"\n        }\n    )\n) * 100',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes', 'node_filesystem_avail_bytes'),
        required_labels=(
            ('node_filesystem_avail_bytes', ('mountpoint',)),
            ('node_filesystem_size_bytes', ('mountpoint',)),
        ),
    ),
    'analytics.utilization.queries.POD_COUNT': QueryDefinition(
        key='analytics.utilization.queries.POD_COUNT',
        expression='sum(\n    (kube_pod_status_phase{phase="Running"} == 1)\n    * on(namespace, pod) group_left(node)\n    (\n        kube_pod_info\n        unless on(node)\n        kube_node_role{role=~"control-plane|master"}\n    )\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_pod_status_phase', 'kube_pod_info', 'kube_node_role'),
        required_labels=(_POD_PHASE_LABEL, _POD_INFO_LABEL, _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.POD_CAPACITY': QueryDefinition(
        key='analytics.utilization.queries.POD_CAPACITY',
        expression='sum(\n    kube_node_status_allocatable{\n        resource="pods",\n        unit="integer"\n    }\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_allocatable', 'kube_node_role'),
        required_labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL, _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.POD_UTILIZATION': QueryDefinition(
        key='analytics.utilization.queries.POD_UTILIZATION',
        expression='(\n    sum(\n        (kube_pod_status_phase{phase="Running"} == 1)\n        * on(namespace, pod) group_left(node)\n        (\n            kube_pod_info\n            unless on(node)\n            kube_node_role{role=~"control-plane|master"}\n        )\n    )\n/\n    sum(\n        kube_node_status_allocatable{\n            resource="pods",\n            unit="integer"\n        }\n        unless on(node)\n        kube_node_role{role=~"control-plane|master"}\n    )\n) * 100',
        domain='app.analytics.utilization',
        required_metrics=('kube_pod_status_phase', 'kube_pod_info', 'kube_node_role', 'kube_node_status_allocatable'),
        required_labels=(_POD_PHASE_LABEL, _POD_INFO_LABEL, _NODE_ROLE_LABEL, _ALLOCATABLE_NODE_RESOURCE_LABEL),
    ),
    'analytics.utilization.queries.TOP_CPU_CONSUMERS': QueryDefinition(
        key='analytics.utilization.queries.TOP_CPU_CONSUMERS',
        expression='topk(\n    10,\n    sum by(namespace, pod)(\n        rate(\n            container_cpu_usage_seconds_total{\n                container!="",\n                container!="POD",\n                node!=""\n            }[5m]\n        )\n        unless on(node)\n        kube_node_role{role=~"control-plane|master"}\n    )\n)',
        domain='app.analytics.utilization',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_node_role'),
        required_labels=(('container_cpu_usage_seconds_total', ('container', 'namespace', 'pod', 'node')), _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.TOP_MEMORY_CONSUMERS': QueryDefinition(
        key='analytics.utilization.queries.TOP_MEMORY_CONSUMERS',
        expression='topk(\n    10,\n    sum by(namespace, pod)(\n        container_memory_working_set_bytes{\n            container!="",\n            container!="POD",\n            node!=""\n        }\n        unless on(node)\n        kube_node_role{role=~"control-plane|master"}\n    )\n)',
        domain='app.analytics.utilization',
        required_metrics=('container_memory_working_set_bytes', 'kube_node_role'),
        required_labels=(('container_memory_working_set_bytes', ('container', 'namespace', 'pod', 'node')), _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.KUBERNETES_VERSION': QueryDefinition(
        key='analytics.utilization.queries.KUBERNETES_VERSION',
        expression='kubernetes_build_info',
        domain='app.analytics.utilization',
        required_metrics=(),
        required_labels=(),
    ),
    'analytics.utilization.queries.TOTAL_NODES': QueryDefinition(
        key='analytics.utilization.queries.TOTAL_NODES',
        expression='count(\n    kube_node_info\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_info',),
        required_labels=(),
    ),
    'analytics.utilization.queries.READY_NODES': QueryDefinition(
        key='analytics.utilization.queries.READY_NODES',
        expression='count(\n    kube_node_status_condition{\n        condition="Ready",\n        status="true"\n    } == 1\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_condition',),
        required_labels=(('kube_node_status_condition', ('condition', 'status')),),
    ),
    'analytics.utilization.queries.NOT_READY_NODES': QueryDefinition(
        key='analytics.utilization.queries.NOT_READY_NODES',
        expression='count(\n    kube_node_status_condition{\n        condition="Ready",\n        status!="true"\n    } == 1\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_condition',),
        required_labels=(('kube_node_status_condition', ('condition', 'status')),),
    ),
    'analytics.utilization.queries.MASTER_NODES': QueryDefinition(
        key='analytics.utilization.queries.MASTER_NODES',
        expression='count(\n    count by(node)(\n        kube_node_role{role=~"control-plane|master"}\n    )\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_role',),
        required_labels=(_NODE_ROLE_LABEL,),
    ),
    'analytics.utilization.queries.WORKER_NODES': QueryDefinition(
        key='analytics.utilization.queries.WORKER_NODES',
        expression='count(\n    kube_node_info\n    unless on(node)\n    kube_node_role{role=~"control-plane|master"}\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_info', 'kube_node_role'),
        required_labels=(('kube_node_info', ('node',)), _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.NODE_LIST': QueryDefinition(
        key='analytics.utilization.queries.NODE_LIST',
        expression='kube_node_info',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_info',),
        required_labels=(),
    ),
    'analytics.utilization.queries.WORKER_NODE_LIST': QueryDefinition(
        key='analytics.utilization.queries.WORKER_NODE_LIST',
        expression='kube_node_info\nunless on(node)\nkube_node_role{role=~"control-plane|master"}',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_info', 'kube_node_role'),
        required_labels=(('kube_node_info', ('node',)), _NODE_ROLE_LABEL),
    ),
    'analytics.utilization.queries.FILESYSTEM_INSTANCE_LIST': QueryDefinition(
        key='analytics.utilization.queries.FILESYSTEM_INSTANCE_LIST',
        expression='node_filesystem_size_bytes{\n    mountpoint="/var",\n    fstype!~"tmpfs|overlay|squashfs"\n}\nor on(instance)\n(\n    node_filesystem_size_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n    unless on(instance)\n    node_filesystem_size_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes',),
        required_labels=(('node_filesystem_size_bytes', ('mountpoint',)),),
    ),
    'analytics.utilization.queries.CPU_CAPACITY_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.CPU_CAPACITY_BY_NODE',
        expression='sum(\n    kube_node_status_allocatable{\n        resource="cpu",\n        unit="core",\n        node="{node}"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_allocatable',),
        required_labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL,),
    ),
    'analytics.utilization.queries.CPU_USAGE_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.CPU_USAGE_BY_NODE',
        expression='sum(\n    rate(\n        container_cpu_usage_seconds_total{\n            container!="",\n            container!="POD",\n            node="{node}"\n        }[5m]\n    )\n)',
        domain='app.analytics.utilization',
        required_metrics=('container_cpu_usage_seconds_total',),
        required_labels=(('container_cpu_usage_seconds_total', ('container', 'node')),),
    ),
    'analytics.utilization.queries.CPU_UTILIZATION_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.CPU_UTILIZATION_BY_NODE',
        expression='(\n    sum(\n        rate(\n            container_cpu_usage_seconds_total{\n                container!="",\n                container!="POD",\n                node="{node}"\n            }[5m]\n        )\n    )\n/\n    sum(\n        kube_node_status_allocatable{\n            resource="cpu",\n            unit="core",\n            node="{node}"\n        }\n    )\n) * 100',
        domain='app.analytics.utilization',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_node_status_allocatable'),
        required_labels=(_CONTAINER_CPU_NODE_LABEL, _ALLOCATABLE_NODE_RESOURCE_LABEL),
    ),
    'analytics.utilization.queries.MEMORY_CAPACITY_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.MEMORY_CAPACITY_BY_NODE',
        expression='sum(\n    kube_node_status_allocatable{\n        resource="memory",\n        unit="byte",\n        node="{node}"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_allocatable',),
        required_labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL,),
    ),
    'analytics.utilization.queries.MEMORY_USAGE_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.MEMORY_USAGE_BY_NODE',
        expression='sum(\n    container_memory_working_set_bytes{\n        container!="",\n        container!="POD",\n        node="{node}"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('container_memory_working_set_bytes',),
        required_labels=(('container_memory_working_set_bytes', ('container', 'node')),),
    ),
    'analytics.utilization.queries.MEMORY_UTILIZATION_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.MEMORY_UTILIZATION_BY_NODE',
        expression='(\n    sum(\n        container_memory_working_set_bytes{\n            container!="",\n            container!="POD",\n            node="{node}"\n        }\n    )\n/\n    sum(\n        kube_node_status_allocatable{\n            resource="memory",\n            unit="byte",\n            node="{node}"\n        }\n    )\n) * 100',
        domain='app.analytics.utilization',
        required_metrics=('container_memory_working_set_bytes', 'kube_node_status_allocatable'),
        required_labels=(_CONTAINER_MEMORY_NODE_LABEL, _ALLOCATABLE_NODE_RESOURCE_LABEL),
    ),
    'analytics.utilization.queries.POD_COUNT_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.POD_COUNT_BY_NODE',
        expression='count(\n    (\n        kube_pod_status_phase{\n            phase="Running"\n        } == 1\n    )\n    * on(namespace,pod)\n    group_left(node)\n    kube_pod_info{\n        node="{node}"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_pod_status_phase', 'kube_pod_info'),
        required_labels=(('kube_pod_info', ('node',)), ('kube_pod_status_phase', ('phase',))),
    ),
    'analytics.utilization.queries.POD_CAPACITY_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.POD_CAPACITY_BY_NODE',
        expression='sum(\n    kube_node_status_allocatable{\n        resource="pods",\n        unit="integer",\n        node="{node}"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_allocatable',),
        required_labels=(_ALLOCATABLE_NODE_RESOURCE_LABEL,),
    ),
    'analytics.utilization.queries.POD_UTILIZATION_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.POD_UTILIZATION_BY_NODE',
        expression='(\n    count(\n        (\n            kube_pod_status_phase{phase="Running"} == 1\n        )\n        * on(namespace, pod) group_left(node)\n        kube_pod_info{node="{node}"}\n    )\n/\n    sum(\n        kube_node_status_allocatable{\n            resource="pods",\n            unit="integer",\n            node="{node}"\n        }\n    )\n) * 100',
        domain='app.analytics.utilization',
        required_metrics=('kube_pod_status_phase', 'kube_pod_info', 'kube_node_status_allocatable'),
        required_labels=(_POD_PHASE_LABEL, _POD_INFO_LABEL, _ALLOCATABLE_NODE_RESOURCE_LABEL),
    ),
    'analytics.utilization.queries.STORAGE_CAPACITY_BY_INSTANCE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_CAPACITY_BY_INSTANCE',
        expression='sum(\n    node_filesystem_size_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs",\n        instance="{instance}"\n    }\n)\nor\nsum(\n    node_filesystem_size_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs",\n        instance="{instance}"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes',),
        required_labels=(('node_filesystem_size_bytes', ('instance', 'mountpoint')),),
    ),
    'analytics.utilization.queries.STORAGE_AVAILABLE_BY_INSTANCE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_AVAILABLE_BY_INSTANCE',
        expression='sum(\n    node_filesystem_avail_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs",\n        instance="{instance}"\n    }\n)\nor\nsum(\n    node_filesystem_avail_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs",\n        instance="{instance}"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_avail_bytes',),
        required_labels=(('node_filesystem_avail_bytes', ('instance', 'mountpoint')),),
    ),
    'analytics.utilization.queries.STORAGE_USAGE_BY_INSTANCE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_USAGE_BY_INSTANCE',
        expression='sum(\n    node_filesystem_size_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs",\n        instance="{instance}"\n    }\n    -\n    node_filesystem_avail_bytes{\n        mountpoint="/var",\n        fstype!~"tmpfs|overlay|squashfs",\n        instance="{instance}"\n    }\n)\nor\nsum(\n    node_filesystem_size_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs",\n        instance="{instance}"\n    }\n    -\n    node_filesystem_avail_bytes{\n        mountpoint="/",\n        fstype!~"tmpfs|overlay|squashfs",\n        instance="{instance}"\n    }\n)',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes', 'node_filesystem_avail_bytes'),
        required_labels=(
            ('node_filesystem_avail_bytes', ('instance', 'mountpoint')),
            ('node_filesystem_size_bytes', ('instance', 'mountpoint')),
        ),
    ),
    'analytics.utilization.queries.STORAGE_UTILIZATION_BY_INSTANCE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_UTILIZATION_BY_INSTANCE',
        expression='(\n    sum(\n        node_filesystem_size_bytes{\n            mountpoint="/var",\n            fstype!~"tmpfs|overlay|squashfs",\n            instance="{instance}"\n        }\n        -\n        node_filesystem_avail_bytes{\n            mountpoint="/var",\n            fstype!~"tmpfs|overlay|squashfs",\n            instance="{instance}"\n        }\n    )\n/\n    sum(\n        node_filesystem_size_bytes{\n            mountpoint="/var",\n            fstype!~"tmpfs|overlay|squashfs",\n            instance="{instance}"\n        }\n    )\n) * 100\nor\n(\n    sum(\n        node_filesystem_size_bytes{\n            mountpoint="/",\n            fstype!~"tmpfs|overlay|squashfs",\n            instance="{instance}"\n        }\n        -\n        node_filesystem_avail_bytes{\n            mountpoint="/",\n            fstype!~"tmpfs|overlay|squashfs",\n            instance="{instance}"\n        }\n    )\n/\n    sum(\n        node_filesystem_size_bytes{\n            mountpoint="/",\n            fstype!~"tmpfs|overlay|squashfs",\n            instance="{instance}"\n        }\n    )\n) * 100',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes', 'node_filesystem_avail_bytes'),
        required_labels=(
            ('node_filesystem_avail_bytes', ('instance', 'mountpoint')),
            ('node_filesystem_size_bytes', ('instance', 'mountpoint')),
        ),
    ),
    'analytics.utilization.queries.STORAGE_CAPACITY_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_CAPACITY_BY_NODE',
        expression='sum(node_filesystem_size_bytes{mountpoint="/var",fstype!~"tmpfs|overlay|squashfs",node="{node}"}) or sum(node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay|squashfs",node="{node}"})',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes',),
        required_labels=(('node_filesystem_size_bytes', ('node', 'mountpoint')),),
    ),
    'analytics.utilization.queries.STORAGE_AVAILABLE_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_AVAILABLE_BY_NODE',
        expression='sum(node_filesystem_avail_bytes{mountpoint="/var",fstype!~"tmpfs|overlay|squashfs",node="{node}"}) or sum(node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay|squashfs",node="{node}"})',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_avail_bytes',),
        required_labels=(('node_filesystem_avail_bytes', ('node', 'mountpoint')),),
    ),
    'analytics.utilization.queries.STORAGE_USAGE_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_USAGE_BY_NODE',
        expression='sum(node_filesystem_size_bytes{mountpoint="/var",fstype!~"tmpfs|overlay|squashfs",node="{node}"} - node_filesystem_avail_bytes{mountpoint="/var",fstype!~"tmpfs|overlay|squashfs",node="{node}"}) or sum(node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay|squashfs",node="{node}"} - node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay|squashfs",node="{node}"})',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes', 'node_filesystem_avail_bytes'),
        required_labels=(
            ('node_filesystem_size_bytes', ('node', 'mountpoint')),
            ('node_filesystem_avail_bytes', ('node', 'mountpoint')),
        ),
    ),
    'analytics.utilization.queries.STORAGE_UTILIZATION_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.STORAGE_UTILIZATION_BY_NODE',
        expression='((sum(node_filesystem_size_bytes{mountpoint="/var",fstype!~"tmpfs|overlay|squashfs",node="{node}"} - node_filesystem_avail_bytes{mountpoint="/var",fstype!~"tmpfs|overlay|squashfs",node="{node}"}) / sum(node_filesystem_size_bytes{mountpoint="/var",fstype!~"tmpfs|overlay|squashfs",node="{node}"})) * 100) or ((sum(node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay|squashfs",node="{node}"} - node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay|squashfs",node="{node}"}) / sum(node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay|squashfs",node="{node}"})) * 100)',
        domain='app.analytics.utilization',
        required_metrics=('node_filesystem_size_bytes', 'node_filesystem_avail_bytes'),
        required_labels=(
            ('node_filesystem_size_bytes', ('node', 'mountpoint')),
            ('node_filesystem_avail_bytes', ('node', 'mountpoint')),
        ),
    ),
    'analytics.utilization.queries.MEMORY_PRESSURE_NODES': QueryDefinition(
        key='analytics.utilization.queries.MEMORY_PRESSURE_NODES',
        expression='sum(\n    kube_node_status_condition{\n        condition="MemoryPressure",\n        status="true"\n    } == 1\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_condition',),
        required_labels=(('kube_node_status_condition', ('condition', 'status')),),
    ),
    'analytics.utilization.queries.DISK_PRESSURE_NODES': QueryDefinition(
        key='analytics.utilization.queries.DISK_PRESSURE_NODES',
        expression='sum(\n    kube_node_status_condition{\n        condition="DiskPressure",\n        status="true"\n    } == 1\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_condition',),
        required_labels=(('kube_node_status_condition', ('condition', 'status')),),
    ),
    'analytics.utilization.queries.PID_PRESSURE_NODES': QueryDefinition(
        key='analytics.utilization.queries.PID_PRESSURE_NODES',
        expression='sum(\n    kube_node_status_condition{\n        condition="PIDPressure",\n        status="true"\n    } == 1\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_condition',),
        required_labels=(('kube_node_status_condition', ('condition', 'status')),),
    ),
    'analytics.utilization.queries.MEMORY_PRESSURE_NODES_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.MEMORY_PRESSURE_NODES_BY_NODE',
        expression='sum(\n    kube_node_status_condition{\n        condition="MemoryPressure",\n        status="true",\n        node="{node}"\n    } == 1\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_condition',),
        required_labels=(('kube_node_status_condition', ('condition', 'node', 'status')),),
    ),
    'analytics.utilization.queries.DISK_PRESSURE_NODES_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.DISK_PRESSURE_NODES_BY_NODE',
        expression='sum(\n    kube_node_status_condition{\n        condition="DiskPressure",\n        status="true",\n        node="{node}"\n    } == 1\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_condition',),
        required_labels=(('kube_node_status_condition', ('condition', 'node', 'status')),),
    ),
    'analytics.utilization.queries.PID_PRESSURE_NODES_BY_NODE': QueryDefinition(
        key='analytics.utilization.queries.PID_PRESSURE_NODES_BY_NODE',
        expression='sum(\n    kube_node_status_condition{\n        condition="PIDPressure",\n        status="true",\n        node="{node}"\n    } == 1\n)',
        domain='app.analytics.utilization',
        required_metrics=('kube_node_status_condition',),
        required_labels=(('kube_node_status_condition', ('condition', 'node', 'status')),),
    ),
    'analytics.workload.queries.NAMESPACE_ACTIVE_QUERY': QueryDefinition(
        key='analytics.workload.queries.NAMESPACE_ACTIVE_QUERY',
        expression='kube_namespace_status_phase{phase="Active"} == 1',
        domain='app.analytics.workload',
        required_metrics=('kube_namespace_status_phase',),
        required_labels=(('kube_namespace_status_phase', ('phase',)),),
    ),
    'analytics.workload.queries.TENANT_QUOTA_HARD_QUERY': QueryDefinition(
        key='analytics.workload.queries.TENANT_QUOTA_HARD_QUERY',
        expression='max by (namespace, resourcequota, resource, type) (\n  kube_resourcequota{type="hard", namespace!="", resourcequota!="", resource!=""}\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_resourcequota',),
        required_labels=(('kube_resourcequota', ('namespace', 'resourcequota', 'resource', 'type')),),
    ),
    'analytics.workload.queries.TENANT_QUOTA_USED_QUERY': QueryDefinition(
        key='analytics.workload.queries.TENANT_QUOTA_USED_QUERY',
        expression='max by (namespace, resourcequota, resource, type) (\n  kube_resourcequota{type="used", namespace!="", resourcequota!="", resource!=""}\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_resourcequota',),
        required_labels=(('kube_resourcequota', ('namespace', 'resourcequota', 'resource', 'type')),),
    ),
    'analytics.workload.queries.TENANT_CPU_ACTUAL_QUERY': QueryDefinition(
        key='analytics.workload.queries.TENANT_CPU_ACTUAL_QUERY',
        expression='sum by (namespace) (\n  (\n    sum by (namespace, pod) (\n      max by (namespace, pod, container) (\n        rate(container_cpu_usage_seconds_total{\n          namespace!="",\n          container!="",\n          image!="",\n          pod!=""\n        }[5m])\n      )\n    )\n    and on (namespace, pod)\n    max by (namespace, pod) (\n      kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n    )\n  )\n)',
        domain='app.analytics.workload',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_pod_status_phase'),
        required_labels=(
            ('container_cpu_usage_seconds_total', ('container', 'image', 'namespace', 'pod')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.TENANT_MEMORY_ACTUAL_QUERY': QueryDefinition(
        key='analytics.workload.queries.TENANT_MEMORY_ACTUAL_QUERY',
        expression='sum by (namespace) (\n  (\n    sum by (namespace, pod) (\n      max by (namespace, pod, container) (\n        container_memory_working_set_bytes{\n          namespace!="",\n          container!="",\n          image!="",\n          pod!=""\n        }\n      )\n    )\n    and on (namespace, pod)\n    max by (namespace, pod) (\n      kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n    )\n  )\n)',
        domain='app.analytics.workload',
        required_metrics=('container_memory_working_set_bytes', 'kube_pod_status_phase'),
        required_labels=(
            ('container_memory_working_set_bytes', ('container', 'image', 'namespace', 'pod')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.TENANT_POD_ACTUAL_QUERY': QueryDefinition(
        key='analytics.workload.queries.TENANT_POD_ACTUAL_QUERY',
        expression='sum by (namespace) (\n  max by (namespace, pod) (\n    kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n  )\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_pod_status_phase',),
        required_labels=(('kube_pod_status_phase', ('namespace', 'pod', 'phase')),),
    ),
    'analytics.workload.queries.WORKLOAD_POD_OWNER_QUERY': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_POD_OWNER_QUERY',
        expression='max by (namespace, pod, owner_kind, owner_name) (\n  kube_pod_owner{namespace!="", pod!=""}\n)\nand on (namespace, pod)\nmax by (namespace, pod) (\n  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_pod_owner', 'kube_pod_status_phase'),
        required_labels=(
            ('kube_pod_owner', ('namespace', 'pod', 'owner_kind', 'owner_name')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_QOS_QUERY': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_QOS_QUERY',
        expression='max by (namespace, pod, qos_class) (\n  kube_pod_status_qos_class{namespace!="", pod!="", qos_class!=""} == 1\n)\nand on (namespace, pod)\nmax by (namespace, pod) (\n  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_pod_status_qos_class', 'kube_pod_status_phase'),
        required_labels=(
            ('kube_pod_status_qos_class', ('namespace', 'pod', 'qos_class')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_CPU_REQUESTS_QUERY': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_CPU_REQUESTS_QUERY',
        expression='sum by (namespace, pod) (\n  max by (namespace, pod, container) (\n    kube_pod_container_resource_requests{\n      resource="cpu",\n      unit="core",\n      namespace!="",\n      pod!="",\n      container!=""\n    }\n  )\n)\nand on (namespace, pod)\nmax by (namespace, pod) (\n  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_pod_container_resource_requests', 'kube_pod_status_phase'),
        required_labels=(
            ('kube_pod_container_resource_requests', ('namespace', 'pod', 'container', 'resource', 'unit')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_CPU_LIMITS_QUERY': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_CPU_LIMITS_QUERY',
        expression='sum by (namespace, pod) (\n  max by (namespace, pod, container) (\n    kube_pod_container_resource_limits{\n      resource="cpu",\n      unit="core",\n      namespace!="",\n      pod!="",\n      container!=""\n    }\n  )\n)\nand on (namespace, pod)\nmax by (namespace, pod) (\n  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_pod_container_resource_limits', 'kube_pod_status_phase'),
        required_labels=(
            ('kube_pod_container_resource_limits', ('namespace', 'pod', 'container', 'resource', 'unit')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_CPU_CURRENT_QUERY': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_CPU_CURRENT_QUERY',
        expression='sum by (namespace, pod) (\n  max by (namespace, pod, container) (\n    rate(container_cpu_usage_seconds_total{\n      namespace!="",\n      container!="",\n      image!="",\n      pod!=""\n    }[5m])\n  )\n)\nand on (namespace, pod)\nmax by (namespace, pod) (\n  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n)',
        domain='app.analytics.workload',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_pod_status_phase'),
        required_labels=(
            ('container_cpu_usage_seconds_total', ('container', 'image', 'namespace', 'pod')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_CPU_PEAK_QUERY_TEMPLATE': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_CPU_PEAK_QUERY_TEMPLATE',
        expression='max_over_time(\n  (\n    sum by (namespace, pod) (\n      max by (namespace, pod, container) (\n        rate(container_cpu_usage_seconds_total{\n          namespace!="",\n          container!="",\n          image!="",\n          pod!=""\n        }[5m])\n      )\n    )\n    and on (namespace, pod)\n    max by (namespace, pod) (\n      kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n    )\n  )[__TIME_RANGE__:__TIME_STEP__]\n)',
        domain='app.analytics.workload',
        required_metrics=('container_cpu_usage_seconds_total', 'kube_pod_status_phase'),
        required_labels=(
            ('container_cpu_usage_seconds_total', ('container', 'image', 'namespace', 'pod')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_MEMORY_REQUESTS_QUERY': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_MEMORY_REQUESTS_QUERY',
        expression='sum by (namespace, pod) (\n  max by (namespace, pod, container) (\n    kube_pod_container_resource_requests{\n      resource="memory",\n      unit="byte",\n      namespace!="",\n      pod!="",\n      container!=""\n    }\n  )\n)\nand on (namespace, pod)\nmax by (namespace, pod) (\n  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_pod_container_resource_requests', 'kube_pod_status_phase'),
        required_labels=(
            ('kube_pod_container_resource_requests', ('namespace', 'pod', 'container', 'resource', 'unit')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_MEMORY_LIMITS_QUERY': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_MEMORY_LIMITS_QUERY',
        expression='sum by (namespace, pod) (\n  max by (namespace, pod, container) (\n    kube_pod_container_resource_limits{\n      resource="memory",\n      unit="byte",\n      namespace!="",\n      pod!="",\n      container!=""\n    }\n  )\n)\nand on (namespace, pod)\nmax by (namespace, pod) (\n  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n)',
        domain='app.analytics.workload',
        required_metrics=('kube_pod_container_resource_limits', 'kube_pod_status_phase'),
        required_labels=(
            ('kube_pod_container_resource_limits', ('namespace', 'pod', 'container', 'resource', 'unit')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_MEMORY_CURRENT_QUERY': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_MEMORY_CURRENT_QUERY',
        expression='sum by (namespace, pod) (\n  max by (namespace, pod, container) (\n    container_memory_working_set_bytes{\n      namespace!="",\n      container!="",\n      image!="",\n      pod!=""\n    }\n  )\n)\nand on (namespace, pod)\nmax by (namespace, pod) (\n  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n)',
        domain='app.analytics.workload',
        required_metrics=('container_memory_working_set_bytes', 'kube_pod_status_phase'),
        required_labels=(
            ('container_memory_working_set_bytes', ('container', 'image', 'namespace', 'pod')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
    'analytics.workload.queries.WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE': QueryDefinition(
        key='analytics.workload.queries.WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE',
        expression='max_over_time(\n  (\n    sum by (namespace, pod) (\n      max by (namespace, pod, container) (\n        container_memory_working_set_bytes{\n          namespace!="",\n          container!="",\n          image!="",\n          pod!=""\n        }\n      )\n    )\n    and on (namespace, pod)\n    max by (namespace, pod) (\n      kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n    )\n  )[__TIME_RANGE__:__TIME_STEP__]\n)',
        domain='app.analytics.workload',
        required_metrics=('container_memory_working_set_bytes', 'kube_pod_status_phase'),
        required_labels=(
            ('container_memory_working_set_bytes', ('container', 'image', 'namespace', 'pod')),
            ('kube_pod_status_phase', ('namespace', 'pod', 'phase')),
        ),
    ),
}

QUERIES.update(FORECAST_QUERIES)
