from __future__ import annotations

ACTIVE_ALERTS_EXPRESSION = 'ALERTS{alertstate=~"pending|firing"}'

POD_RESTART_ANOMALY_QUERY = (
    'sum by (namespace, pod) (\n'
    '  max by (namespace, pod, container) (\n'
    '    increase(kube_pod_container_status_restarts_total{namespace!="", pod!="", container!=""}[15m])\n'
    '  )\n'
    ')\n'
    'and on (namespace, pod)\n'
    'max by (namespace, pod) (\n'
    '  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n'
    ')'
)

POD_NOT_READY_ANOMALY_QUERY = (
    'max by (namespace, pod) (\n'
    '  kube_pod_status_ready{condition="false", namespace!="", pod!=""} == 1\n'
    ')\n'
    'and on (namespace, pod)\n'
    'max by (namespace, pod) (\n'
    '  kube_pod_status_phase{namespace!="", pod!="", phase=~"Pending|Running"} == 1\n'
    ')'
)
