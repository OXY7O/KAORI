# Inventory Collector Boundary

## Authority

Kubernetes API collection is owned directly by resource modules under
`app.kubernetes.inventory.collectors`. KAORI does not keep a forwarding collector facade.

- `runtime.py`: cluster version and nodes;
- `workloads.py`: Deployments, StatefulSets, DaemonSets, ReplicaSets, Jobs, and CronJobs;
- `pods.py`: pod runtime, owner, volume, condition, and container evidence;
- `services.py`: Services and endpoint evidence;
- `ingresses.py`: Ingress resources and routing evidence;
- `configuration.py`: ConfigMaps, Secrets, and ResourceQuota;
- `storage.py`: StorageClass, PersistentVolume, and PersistentVolumeClaim;
- `common.py`: collector-only normalization helpers.

## Dependency Direction

`Synchronization -> Persistence -> Concrete Resource Collector`

`app.kubernetes.inventory.persistence` imports each concrete collector owner explicitly.
`app.kubernetes.inventory.collectors.__init__` is package metadata only and must not restore
aggregate exports. Collector modules may share helpers from `common.py`, but may
not import persistence, synchronization, routes, or another forwarding module.
