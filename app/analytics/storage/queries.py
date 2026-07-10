# app/analytics/storage/queries.py

from __future__ import annotations

NAMESPACE_ACTIVE_QUERY = """
kube_namespace_status_phase{phase="Active"} == 1
"""


NODE_VAR_FILESYSTEM_SIZE_QUERY = """
sum by (instance) (
  node_filesystem_size_bytes{
    mountpoint="/var",
    fstype!~"tmpfs|overlay"
  }
)
"""


NODE_VAR_FILESYSTEM_AVAILABLE_QUERY = """
sum by (instance) (
  node_filesystem_avail_bytes{
    mountpoint="/var",
    fstype!~"tmpfs|overlay"
  }
)
"""



NODE_ROOT_FILESYSTEM_SIZE_QUERY = """
sum by (instance) (
  node_filesystem_size_bytes{
    mountpoint="/",
    fstype!~"tmpfs|overlay"
  }
)
"""


NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY = """
sum by (instance) (
  node_filesystem_avail_bytes{
    mountpoint="/",
    fstype!~"tmpfs|overlay"
  }
)
"""


PVC_REQUESTED_TOTAL_QUERY = """
sum(kube_persistentvolumeclaim_resource_requests_storage_bytes)
"""


PVC_USED_TOTAL_QUERY = """
sum(kubelet_volume_stats_used_bytes)
"""


PVC_AVAILABLE_TOTAL_QUERY = """
sum(kubelet_volume_stats_available_bytes)
"""


PVC_REQUESTED_BY_CLAIM_QUERY = """
sum by (namespace, persistentvolumeclaim) (
  kube_persistentvolumeclaim_resource_requests_storage_bytes
)
"""


PVC_USED_BY_CLAIM_QUERY = """
sum by (namespace, persistentvolumeclaim) (
  kubelet_volume_stats_used_bytes
)
"""


PVC_AVAILABLE_BY_CLAIM_QUERY = """
sum by (namespace, persistentvolumeclaim) (
  kubelet_volume_stats_available_bytes
)
"""


PVC_STATUS_BY_CLAIM_QUERY = """
kube_persistentvolumeclaim_status_phase
"""


PVC_INFO_QUERY = """
kube_persistentvolumeclaim_info
"""


PVC_COUNT_QUERY = """
count(kube_persistentvolumeclaim_info)
"""


PV_CAPACITY_QUERY = """
sum(kube_persistentvolume_capacity_bytes)
"""


PV_CAPACITY_BY_VOLUME_QUERY = """
kube_persistentvolume_capacity_bytes
"""


PV_COUNT_QUERY = """
count(kube_persistentvolume_info)
"""


PV_INFO_QUERY = """
kube_persistentvolume_info
"""


PV_STATUS_BY_VOLUME_QUERY = """
kube_persistentvolume_status_phase
"""


PV_RECLAIM_POLICY_QUERY = """
kube_persistentvolume_info
"""
