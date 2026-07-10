CPU_CAPACITY = """
sum(
    kube_node_status_capacity{
        resource="cpu"
    }
)
"""

CPU_USAGE = """
sum(
    rate(
        container_cpu_usage_seconds_total{
            container!="",
            container!="POD"
        }[5m]
    )
)
"""

CPU_UTILIZATION = """
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

MEMORY_CAPACITY = """
sum(
    kube_node_status_capacity{
        resource="memory"
    }
)
"""

MEMORY_USAGE = """
sum(
    container_memory_working_set_bytes{
        container!="",
        container!="POD"
    }
)
"""

MEMORY_UTILIZATION = """
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

STORAGE_CAPACITY = """
sum(
    node_filesystem_size_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs"
    }
)
or
sum(
    node_filesystem_size_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs"
    }
)
"""

STORAGE_AVAILABLE = """
sum(
    node_filesystem_avail_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs"
    }
)
or
sum(
    node_filesystem_avail_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs"
    }
)
"""

STORAGE_USAGE = """
sum(
    node_filesystem_size_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs"
    }
    -
    node_filesystem_avail_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs"
    }
)
or
sum(
    node_filesystem_size_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs"
    }
    -
    node_filesystem_avail_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs"
    }
)
"""

STORAGE_UTILIZATION = """
(
    sum(
        node_filesystem_size_bytes{
            mountpoint="/var",
            fstype!~"tmpfs|overlay|squashfs"
        }
        -
        node_filesystem_avail_bytes{
            mountpoint="/var",
            fstype!~"tmpfs|overlay|squashfs"
        }
    )
/
    sum(
        node_filesystem_size_bytes{
            mountpoint="/var",
            fstype!~"tmpfs|overlay|squashfs"
        }
    )
) * 100
or
(
    sum(
        node_filesystem_size_bytes{
            mountpoint="/",
            fstype!~"tmpfs|overlay|squashfs"
        }
        -
        node_filesystem_avail_bytes{
            mountpoint="/",
            fstype!~"tmpfs|overlay|squashfs"
        }
    )
/
    sum(
        node_filesystem_size_bytes{
            mountpoint="/",
            fstype!~"tmpfs|overlay|squashfs"
        }
    )
) * 100
"""

POD_COUNT = """
count(
    kube_pod_status_phase{
        phase="Running"
    }
)
"""

POD_CAPACITY = """
sum(
    kube_node_status_capacity{
        resource="pods"
    }
)
"""

POD_UTILIZATION = """
(
    count(
        kube_pod_status_phase{
            phase="Running"
        }
    )
/
    sum(
        kube_node_status_capacity{
            resource="pods"
        }
    )
) * 100
"""

CPU_UTILIZATION_HISTORY = CPU_UTILIZATION
MEMORY_UTILIZATION_HISTORY = MEMORY_UTILIZATION
POD_UTILIZATION_HISTORY = POD_UTILIZATION

TOP_CPU_CONSUMERS = """
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

TOP_MEMORY_CONSUMERS = """
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

KUBERNETES_VERSION = """
kubernetes_build_info
"""

TOTAL_NODES = """
count(
    kube_node_info
)
"""

READY_NODES = """
count(
    kube_node_status_condition{
        condition="Ready",
        status="true"
    } == 1
)
"""

NOT_READY_NODES = """
count(
    kube_node_status_condition{
        condition="Ready",
        status!="true"
    } == 1
)
"""

MASTER_NODES = """
count(
    kube_node_role{
        role="control-plane"
    }
)
"""

WORKER_NODES = """
count(
    kube_node_info
)
-
count(
    kube_node_role{
        role="control-plane"
    }
)
"""

NODE_LIST = """
kube_node_info
"""

WORKER_NODE_LIST = """
kube_node_info
unless on(node)
kube_node_role{
    role="control-plane"
}
"""

FILESYSTEM_INSTANCE_LIST = """
node_filesystem_size_bytes{
    mountpoint="/var",
    fstype!~"tmpfs|overlay|squashfs"
}
or on(instance)
(
    node_filesystem_size_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs"
    }
    unless on(instance)
    node_filesystem_size_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs"
    }
)
"""

CPU_CAPACITY_BY_NODE = """
sum(
    kube_node_status_capacity{
        resource="cpu",
        node="{node}"
    }
)
"""

CPU_USAGE_BY_NODE = """
sum(
    rate(
        container_cpu_usage_seconds_total{
            container!="",
            container!="POD",
            node="{node}"
        }[5m]
    )
)
"""

CPU_UTILIZATION_BY_NODE = """
(
    sum(
        rate(
            container_cpu_usage_seconds_total{
                container!="",
                container!="POD",
                node="{node}"
            }[5m]
        )
    )
/
    sum(
        kube_node_status_capacity{
            resource="cpu",
            node="{node}"
        }
    )
) * 100
"""

MEMORY_CAPACITY_BY_NODE = """
sum(
    kube_node_status_capacity{
        resource="memory",
        node="{node}"
    }
)
"""

MEMORY_USAGE_BY_NODE = """
sum(
    container_memory_working_set_bytes{
        container!="",
        container!="POD",
        node="{node}"
    }
)
"""

MEMORY_UTILIZATION_BY_NODE = """
(
    sum(
        container_memory_working_set_bytes{
            container!="",
            container!="POD",
            node="{node}"
        }
    )
/
    sum(
        kube_node_status_capacity{
            resource="memory",
            node="{node}"
        }
    )
) * 100
"""

POD_COUNT_BY_NODE = """
count(
    (
        kube_pod_status_phase{
            phase="Running"
        } == 1
    )
    * on(namespace,pod)
    group_left(node)
    kube_pod_info{
        node="{node}"
    }
)
"""

POD_CAPACITY_BY_NODE = """
sum(
    kube_node_status_capacity{
        resource="pods",
        node="{node}"
    }
)
"""

POD_UTILIZATION_BY_NODE = """
(
    count(
        (
            kube_pod_status_phase{
                phase="Running"
            } == 1
        )
        * on(namespace,pod)
        group_left(node)
        kube_pod_info{
            node="{node}"
        }
    )
/
    sum(
        kube_node_status_capacity{
            resource="pods",
            node="{node}"
        }
    )
) * 100
"""


CPU_UTILIZATION_HISTORY_BY_NODE = CPU_UTILIZATION_BY_NODE

MEMORY_UTILIZATION_HISTORY_BY_NODE = MEMORY_UTILIZATION_BY_NODE

POD_UTILIZATION_HISTORY_BY_NODE = POD_UTILIZATION_BY_NODE

STORAGE_CAPACITY_BY_INSTANCE = """
sum(
    node_filesystem_size_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs",
        instance="{instance}"
    }
)
or
sum(
    node_filesystem_size_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs",
        instance="{instance}"
    }
)
"""

STORAGE_AVAILABLE_BY_INSTANCE = """
sum(
    node_filesystem_avail_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs",
        instance="{instance}"
    }
)
or
sum(
    node_filesystem_avail_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs",
        instance="{instance}"
    }
)
"""

STORAGE_USAGE_BY_INSTANCE = """
sum(
    node_filesystem_size_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs",
        instance="{instance}"
    }
    -
    node_filesystem_avail_bytes{
        mountpoint="/var",
        fstype!~"tmpfs|overlay|squashfs",
        instance="{instance}"
    }
)
or
sum(
    node_filesystem_size_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs",
        instance="{instance}"
    }
    -
    node_filesystem_avail_bytes{
        mountpoint="/",
        fstype!~"tmpfs|overlay|squashfs",
        instance="{instance}"
    }
)
"""

STORAGE_UTILIZATION_BY_INSTANCE = """
(
    sum(
        node_filesystem_size_bytes{
            mountpoint="/var",
            fstype!~"tmpfs|overlay|squashfs",
            instance="{instance}"
        }
        -
        node_filesystem_avail_bytes{
            mountpoint="/var",
            fstype!~"tmpfs|overlay|squashfs",
            instance="{instance}"
        }
    )
/
    sum(
        node_filesystem_size_bytes{
            mountpoint="/var",
            fstype!~"tmpfs|overlay|squashfs",
            instance="{instance}"
        }
    )
) * 100
or
(
    sum(
        node_filesystem_size_bytes{
            mountpoint="/",
            fstype!~"tmpfs|overlay|squashfs",
            instance="{instance}"
        }
        -
        node_filesystem_avail_bytes{
            mountpoint="/",
            fstype!~"tmpfs|overlay|squashfs",
            instance="{instance}"
        }
    )
/
    sum(
        node_filesystem_size_bytes{
            mountpoint="/",
            fstype!~"tmpfs|overlay|squashfs",
            instance="{instance}"
        }
    )
) * 100
"""

MEMORY_PRESSURE_NODES = """
sum(
    kube_node_status_condition{
        condition="MemoryPressure",
        status="true"
    } == 1
)
"""

DISK_PRESSURE_NODES = """
sum(
    kube_node_status_condition{
        condition="DiskPressure",
        status="true"
    } == 1
)
"""

PID_PRESSURE_NODES = """
sum(
    kube_node_status_condition{
        condition="PIDPressure",
        status="true"
    } == 1
)
"""


MEMORY_PRESSURE_NODES_BY_NODE = """
sum(
    kube_node_status_condition{
        condition="MemoryPressure",
        status="true",
        node="{node}"
    } == 1
)
"""

DISK_PRESSURE_NODES_BY_NODE = """
sum(
    kube_node_status_condition{
        condition="DiskPressure",
        status="true",
        node="{node}"
    } == 1
)
"""

PID_PRESSURE_NODES_BY_NODE = """
sum(
    kube_node_status_condition{
        condition="PIDPressure",
        status="true",
        node="{node}"
    } == 1
)
"""
PROMETHEUS_HEALTH = """
vector(1)
"""
