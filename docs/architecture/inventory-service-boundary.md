# Inventory Service Boundary

`app.inventory.service` remains the stable public facade used by routes, tasks,
and other KAORI modules. Read-only list, filter, and detail construction is
implemented by resource modules under `app.inventory.resources`.

Resource modules are divided into nodes, namespaces, configuration, workloads,
pods, services, ingresses, and storage. Shared presentation-neutral formatting
and selector helpers live in `resources/common.py`.

Inventory synchronization and database persistence remain in the service facade
during this batch. They will be moved separately so synchronization behavior is
not changed in the same deployment as the read-query split. Routes and templates
must continue importing from `app.inventory.service`; resource modules are an
internal implementation boundary.
