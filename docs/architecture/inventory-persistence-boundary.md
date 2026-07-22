# Inventory Persistence and Synchronization Boundary

## Public API

`app.inventory.service` remains the stable public facade used by routes, tasks,
and reporting modules. Existing imports do not need to change.

## Persistence

`app.inventory.persistence` owns replacement writes for Kubernetes inventory
resources. Each `save_*` function translates collector payloads into SQLAlchemy
records and does not commit the transaction.

## Synchronization

`app.inventory.synchronization` owns one-cluster synchronization orchestration:

- row-level cluster lock;
- Kubernetes client construction;
- API discovery and compatibility state;
- ordered resource collection;
- flush boundaries;
- final commit and rollback.

Persistence modules must not import the service facade. This keeps dependency
direction one-way and prevents circular imports when collector modules are split.
