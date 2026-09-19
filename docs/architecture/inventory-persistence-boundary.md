# Inventory Persistence and Synchronization Boundary

## Persistence Authority

`app.kubernetes.inventory.persistence` owns replacement writes for Kubernetes inventory
resources. Each `save_*` function converts collector payloads into SQLAlchemy
records and does not commit the transaction.

## Synchronization Authority

`app.kubernetes.inventory.synchronization` owns one-cluster synchronization orchestration:

- row-level cluster lock;
- canonical Kubernetes client construction through the integration registry;
- API discovery and compatibility state;
- ordered resource collection;
- flush boundaries;
- final commit and rollback.

The Kubernetes runtime adapter imports `sync_inventory` from this module
directly. No `app.kubernetes.inventory.service` compatibility facade exists.

## Dependency Direction

`Integration Adapter -> Synchronization -> Persistence -> Concrete Collectors`

Persistence and synchronization may share models and utilities, but neither may
import routes or a re-export module.
