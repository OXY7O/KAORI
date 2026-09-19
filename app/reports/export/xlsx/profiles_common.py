from __future__ import annotations

from app.reports.export.xlsx.schema import column

COMMON_CLUSTER_COLUMNS = (
    column('cluster', 'Cluster', 'Committed cluster display name.', width=22),
    column('environment', 'Environment', 'Environment associated with the cluster.', width=16),
)

COMMON_NAMESPACE_COLUMNS = (
    *COMMON_CLUSTER_COLUMNS,
    column('namespace', 'Namespace', 'Committed Kubernetes namespace.', width=22),
)
