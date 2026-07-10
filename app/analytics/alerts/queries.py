from __future__ import annotations

PROMETHEUS_ALERTS_QUERY = 'ALERTS'

PROMETHEUS_FIRING_ALERTS_QUERY = 'ALERTS{alertstate="firing"}'

POD_RESTART_ANOMALY_QUERY = """
sum by (namespace, pod) (
  increase(kube_pod_container_status_restarts_total[15m])
)
"""

POD_NOT_READY_ANOMALY_QUERY = """
kube_pod_status_ready{condition="false"}
"""

CPU_SPIKE_QUERY = """
sum by (namespace, pod) (
  rate(container_cpu_usage_seconds_total{container!="", pod!=""}[5m])
)
"""

MEMORY_USAGE_QUERY = """
sum by (namespace, pod) (
  container_memory_working_set_bytes{container!="", pod!=""}
)
"""
