# Inventory Collector Boundary

## Public Contract

`app.inventory.collector` remains the stable public collector facade. Inventory
persistence and synchronization code must import collectors from this facade,
not from individual resource modules.

## Resource Ownership

Implementations are split under `app.inventory.collectors`:

- `runtime.py`: cluster version and nodes;
- `workloads.py`: Deployments, StatefulSets, DaemonSets, ReplicaSets, Jobs, and CronJobs;
- `pods.py`: pod runtime, owner, volume, condition, and container evidence;
- `services.py`: Services and endpoint evidence;
- `ingresses.py`: Ingress resources and routing evidence;
- `configuration.py`: ConfigMaps, Secrets, and ResourceQuota;
- `storage.py`: StorageClass, PersistentVolume, and PersistentVolumeClaim;
- `common.py`: collector-only normalization and presentation helpers.

## Dependency Direction

Resource collectors may import shared helpers from `common.py`, but they must
never import `app.inventory.collector`. The facade imports the resource package,
and persistence imports only the facade.

This preserves:

`Synchronization -> Persistence -> Collector Facade -> Resource Collector`

No route, template, model, payload shape, transaction boundary, or Kubernetes
API call sequence is intentionally changed by this split.
