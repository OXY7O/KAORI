# =====================================================
# Inventory Metrics
# =====================================================

CLUSTER_NODE_COUNT = """
count(kube_node_info)
"""

CLUSTER_NAMESPACE_COUNT = """
count(kube_namespace_labels)
"""

CLUSTER_POD_COUNT = """
count(kube_pod_info)
"""

# =====================================================
# CPU Metrics
# =====================================================

CLUSTER_CPU_CAPACITY = """
sum(
    kube_node_status_capacity{
        resource="cpu"
    }
)
"""

CLUSTER_CPU_USAGE = """
sum(
    rate(
        container_cpu_usage_seconds_total{
            container!="",
            container!="POD"
        }[5m]
    )
)
"""

CLUSTER_CPU_UTILIZATION = """
(
    sum(
        rate(
            container_cpu_usage_seconds_total{
                container!="",
                container!="POD"
            }[5m]
        )
    )
/
    sum(
        kube_node_status_capacity{
            resource="cpu"
        }
    )
) * 100
"""

# =====================================================
# Memory Metrics
# =====================================================

CLUSTER_MEMORY_CAPACITY = """
sum(
    kube_node_status_capacity{
        resource="memory"
    }
)
"""

CLUSTER_MEMORY_USAGE = """
sum(
    container_memory_working_set_bytes{
        container!="",
        container!="POD"
    }
)
"""

CLUSTER_MEMORY_UTILIZATION = """
(
    sum(
        container_memory_working_set_bytes{
            container!="",
            container!="POD"
        }
    )
/
    sum(
        kube_node_status_capacity{
            resource="memory"
        }
    )
) * 100
"""

# =====================================================
# Storage Metrics
# =====================================================

CLUSTER_STORAGE_CAPACITY = """
sum(
    kubelet_volume_stats_capacity_bytes
)
"""

CLUSTER_STORAGE_USAGE = """
sum(
    kubelet_volume_stats_used_bytes
)
"""

CLUSTER_STORAGE_AVAILABLE = """
sum(
    kubelet_volume_stats_available_bytes
)
"""

CLUSTER_STORAGE_UTILIZATION = """
(
    sum(
        kubelet_volume_stats_used_bytes
    )
/
    sum(
        kubelet_volume_stats_capacity_bytes
    )
) * 100
"""

# =====================================================
# Top Consumers
# =====================================================

TOP_CPU_PODS = """
topk(
    10,
    sum by(namespace,pod)(
        rate(
            container_cpu_usage_seconds_total{
                container!="",
                container!="POD"
            }[5m]
        )
    )
)
"""

TOP_MEMORY_PODS = """
topk(
    10,
    sum by(namespace,pod)(
        container_memory_working_set_bytes{
            container!="",
            container!="POD"
        }
    )
)
"""

# =====================================================
# Trend Metrics
# =====================================================

CPU_USAGE_HISTORY = """
sum(
    rate(
        container_cpu_usage_seconds_total{
            container!="",
            container!="POD"
        }[5m]
    )
)
"""

MEMORY_USAGE_HISTORY = """
sum(
    container_memory_working_set_bytes{
        container!="",
        container!="POD"
    }
)
"""

STORAGE_USAGE_HISTORY = """
sum(
    kubelet_volume_stats_used_bytes
)
"""
