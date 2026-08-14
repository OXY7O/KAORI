"""Semantic descriptions shared by Inventory resource detail builders."""

NODE_ROLE_DESCRIPTIONS = {
    'control-plane': (
        'Runs Kubernetes control-plane components that coordinate cluster state, '
        'scheduling, and API operations. Application workloads are usually kept '
        'off this node.'
    ),
    'master': (
        'Runs Kubernetes control-plane components that coordinate cluster state, '
        'scheduling, and API operations. Application workloads are usually kept '
        'off this node.'
    ),
    'worker': (
        'Runs application Pods and provides compute, memory, networking, and storage capacity for Kubernetes workloads.'
    ),
    'data-plane': ('Provides runtime capacity for application workloads and data-plane traffic.'),
}

WORKLOAD_TYPE_DESCRIPTIONS = {
    'Deployment': ('Maintains a desired number of interchangeable Pods and supports controlled rolling updates.'),
    'StatefulSet': (
        'Runs stateful Pods with stable identities, ordered rollout behavior, and persistent storage mappings.'
    ),
    'DaemonSet': (
        'Ensures a Pod runs on every matching node, commonly for agents, networking, logging, or monitoring.'
    ),
    'Job': ('Runs one-time or finite work until the required number of Pods completes successfully.'),
    'CronJob': ('Creates Jobs on a recurring schedule for periodic operational or application tasks.'),
}

SERVICE_TYPE_DESCRIPTIONS = {
    'ClusterIP': ('Exposes selected Pods on an internal virtual IP that is reachable only inside the cluster.'),
    'NodePort': ('Exposes the Service on a fixed port on every node and forwards traffic to selected Pods.'),
    'LoadBalancer': ('Requests an external load balancer and forwards external traffic to selected Pods.'),
    'ExternalName': ('Maps the Service DNS name to an external DNS hostname without selecting cluster Pods.'),
    'Headless': ('Uses no virtual ClusterIP and returns Pod endpoints directly through Kubernetes DNS.'),
}

STORAGE_TYPE_DESCRIPTIONS = {
    'StorageClass': ('Defines dynamic volume provisioning behavior and lifecycle defaults for PersistentVolumes.'),
    'PersistentVolume': ('Represents cluster-scoped storage capacity that can be bound to a PersistentVolumeClaim.'),
    'PersistentVolumeClaim': ('Represents a namespace-scoped request for storage consumed by one or more Pods.'),
}
