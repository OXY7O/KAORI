# app/analytics/workload/queries.py

from __future__ import annotations

NAMESPACE_ACTIVE_QUERY = """
kube_namespace_status_phase{phase="Active"} == 1
"""


TENANT_QUOTA_HARD_QUERY = """
kube_resourcequota{type="hard"}
"""


TENANT_QUOTA_USED_QUERY = """
kube_resourcequota{type="used"}
"""


TENANT_CPU_ACTUAL_QUERY = """
sum by (namespace) (
  rate(container_cpu_usage_seconds_total{
    namespace!="",
    container!="",
    image!="",
    pod!=""
  }[5m])
)
"""


TENANT_MEMORY_ACTUAL_QUERY = """
sum by (namespace) (
  container_memory_working_set_bytes{
    namespace!="",
    container!="",
    image!="",
    pod!=""
  }
)
"""


TENANT_POD_ACTUAL_QUERY = """
count by (namespace) (
  kube_pod_info{namespace!=""}
)
"""


WORKLOAD_POD_OWNER_QUERY = """
kube_pod_owner{namespace!="", pod!=""}
"""


WORKLOAD_QOS_QUERY = """
kube_pod_status_qos_class{namespace!="", pod!="", qos_class!=""} == 1
"""


WORKLOAD_CPU_REQUESTS_QUERY = """
sum by (namespace, pod) (
  kube_pod_container_resource_requests{
    resource="cpu",
    unit="core",
    namespace!="",
    pod!=""
  }
)
"""


WORKLOAD_CPU_LIMITS_QUERY = """
sum by (namespace, pod) (
  kube_pod_container_resource_limits{
    resource="cpu",
    unit="core",
    namespace!="",
    pod!=""
  }
)
"""


WORKLOAD_CPU_AVG_QUERY = """
sum by (namespace, pod) (
  rate(container_cpu_usage_seconds_total{
    namespace!="",
    container!="",
    image!="",
    pod!=""
  }[5m])
)
"""


WORKLOAD_CPU_PEAK_QUERY_TEMPLATE = """
max_over_time(
  sum by (namespace, pod) (
    rate(container_cpu_usage_seconds_total{
      namespace!="",
      container!="",
      image!="",
      pod!=""
    }[5m])
  )[__TIME_RANGE__:__TIME_STEP__]
)
"""


WORKLOAD_MEMORY_REQUESTS_QUERY = """
sum by (namespace, pod) (
  kube_pod_container_resource_requests{
    resource="memory",
    unit="byte",
    namespace!="",
    pod!=""
  }
)
"""


WORKLOAD_MEMORY_LIMITS_QUERY = """
sum by (namespace, pod) (
  kube_pod_container_resource_limits{
    resource="memory",
    unit="byte",
    namespace!="",
    pod!=""
  }
)
"""


WORKLOAD_MEMORY_AVG_QUERY = """
sum by (namespace, pod) (
  container_memory_working_set_bytes{
    namespace!="",
    container!="",
    image!="",
    pod!=""
  }
)
"""


WORKLOAD_MEMORY_PEAK_QUERY_TEMPLATE = """
max_over_time(
  sum by (namespace, pod) (
    container_memory_working_set_bytes{
      namespace!="",
      container!="",
      image!="",
      pod!=""
    }
  )[__TIME_RANGE__:__TIME_STEP__]
)
"""
