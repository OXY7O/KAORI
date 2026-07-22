# Inventory Overview Boundary

## Authority

`app.inventory.overview` owns read-only operational aggregation for the
Inventory landing page:

- cluster lookup and ordered cluster selection;
- per-cluster synchronization summary;
- resource totals;
- freshness evaluation;
- health diagnostics;
- risk hints;
- recent synchronization activity.

Inventory routes import this authority directly. There is no service facade
between the route and the overview module.

## Resource Descriptions

Semantic descriptions for node roles, workload types, Service types, and
storage resource types live in `app.inventory.resources.descriptions`.
Resource detail builders import those descriptions directly.

## Dependency Direction

`Route -> Overview or Concrete Resource Module`

`Overview -> SQLAlchemy Models`

`Resource Module -> Resource Descriptions`

The overview module is read-only and must not perform synchronization or
persistence.
