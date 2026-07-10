# app/analytics/capacity/queries.py

from __future__ import annotations

CURRENT_PODS_QUERY = """
count(kube_pod_info)
"""


CURRENT_WORKER_PODS_QUERY = """
sum(
  (kube_pod_status_phase{phase="Running"} == 1)
  * on(namespace, pod) group_left(node)
  (
    kube_pod_info
    unless on(node)
    kube_node_role{role=~"control-plane|master"}
  )
)
"""


WORKER_CPU_USAGE_QUERY = """
sum(
  rate(
    container_cpu_usage_seconds_total{
      container!="",
      container!="POD",
      node!=""
    }[5m]
  )
  unless on(node)
  kube_node_role{role=~"control-plane|master"}
)
"""


WORKER_MEMORY_USAGE_QUERY = """
sum(
  container_memory_working_set_bytes{
    container!="",
    container!="POD",
    node!=""
  }
  unless on(node)
  kube_node_role{role=~"control-plane|master"}
)
"""


CPU_REQUESTS_TOTAL_QUERY = """
sum(
  kube_pod_container_resource_requests{
    resource="cpu",
    unit="core",
    namespace!="",
    pod!=""
  }
)
"""


CPU_LIMITS_TOTAL_QUERY = """
sum(
  kube_pod_container_resource_limits{
    resource="cpu",
    unit="core",
    namespace!="",
    pod!=""
  }
)
"""


MEMORY_REQUESTS_TOTAL_QUERY = """
sum(
  kube_pod_container_resource_requests{
    resource="memory",
    unit="byte",
    namespace!="",
    pod!=""
  }
)
"""


MEMORY_LIMITS_TOTAL_QUERY = """
sum(
  kube_pod_container_resource_limits{
    resource="memory",
    unit="byte",
    namespace!="",
    pod!=""
  }
)
"""


WORKER_CPU_REQUESTS_TOTAL_QUERY = """
sum(
  kube_pod_container_resource_requests{
    resource="cpu",
    unit="core",
    namespace!="",
    pod!="",
    node!=""
  }
  unless on(node)
  kube_node_role{role=~"control-plane|master"}
)
"""


WORKER_CPU_LIMITS_TOTAL_QUERY = """
sum(
  kube_pod_container_resource_limits{
    resource="cpu",
    unit="core",
    namespace!="",
    pod!="",
    node!=""
  }
  unless on(node)
  kube_node_role{role=~"control-plane|master"}
)
"""


WORKER_MEMORY_REQUESTS_TOTAL_QUERY = """
sum(
  kube_pod_container_resource_requests{
    resource="memory",
    unit="byte",
    namespace!="",
    pod!="",
    node!=""
  }
  unless on(node)
  kube_node_role{role=~"control-plane|master"}
)
"""


WORKER_MEMORY_LIMITS_TOTAL_QUERY = """
sum(
  kube_pod_container_resource_limits{
    resource="memory",
    unit="byte",
    namespace!="",
    pod!="",
    node!=""
  }
  unless on(node)
  kube_node_role{role=~"control-plane|master"}
)
"""


CPU_PEAK_QUERY_TEMPLATE = """
max_over_time(
  sum(
    rate(container_cpu_usage_seconds_total{
      namespace!="",
      container!="",
      image!="",
      pod!=""
    }[5m])
  )[__TIME_RANGE__:__TIME_STEP__]
)
"""


MEMORY_PEAK_QUERY_TEMPLATE = """
max_over_time(
  sum(
    container_memory_working_set_bytes{
      namespace!="",
      container!="",
      image!="",
      pod!=""
    }
  )[__TIME_RANGE__:__TIME_STEP__]
)
"""


WORKER_CPU_PEAK_QUERY_TEMPLATE = """
max_over_time(
  sum(
    rate(
      container_cpu_usage_seconds_total{
        namespace!="",
        container!="",
        image!="",
        pod!="",
        node!=""
      }[5m]
    )
    unless on(node)
    kube_node_role{role=~"control-plane|master"}
  )[__TIME_RANGE__:__TIME_STEP__]
)
"""


WORKER_MEMORY_PEAK_QUERY_TEMPLATE = """
max_over_time(
  sum(
    container_memory_working_set_bytes{
      namespace!="",
      container!="",
      image!="",
      pod!="",
      node!=""
    }
    unless on(node)
    kube_node_role{role=~"control-plane|master"}
  )[__TIME_RANGE__:__TIME_STEP__]
)
"""
WORKER_CPU_ALLOCATABLE_QUERY = """
sum(
  kube_node_status_allocatable{
    resource="cpu",
    unit="core"
  }
  unless on(node)
  kube_node_role{
    role=~"control-plane|master"
  }
)
"""


WORKER_MEMORY_ALLOCATABLE_QUERY = """
sum(
  kube_node_status_allocatable{
    resource="memory",
    unit="byte"
  }
  unless on(node)
  kube_node_role{
    role=~"control-plane|master"
  }
)
"""


WORKER_POD_ALLOCATABLE_QUERY = """
sum(
  kube_node_status_allocatable{
    resource="pods",
    unit="integer"
  }
  unless on(node)
  kube_node_role{
    role=~"control-plane|master"
  }
)
"""
