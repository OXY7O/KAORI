# Inventory Overview Boundary

## Authority

`app.inventory.overview` owns read-only operational aggregation for the
Inventory landing page:

- cluster lookup and ordered cluster selection;
- per-cluster sync summary;
- resource totals;
- freshness evaluation;
- health diagnostics;
- risk hints;
- recent synchronization activity.

`app.inventory.service` remains a stable public facade and contains no query,
health, activity, or summary implementation.

## Resource Descriptions

Semantic descriptions for node roles, workload types, Service types, and
storage resource types live in `app.inventory.resources.descriptions`.
Resource detail builders import those descriptions directly. They must not
depend on the service facade.

## Dependency Direction

`Route -> Inventory Service Facade -> Overview or Resource Module`

`Overview -> SQLAlchemy Models`

`Resource Module -> Resource Descriptions`

The overview module is read-only and must not perform Inventory synchronization
or persistence.
