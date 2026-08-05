# KAORI Core Workspaces Legacy Cleanup Audit — August 2026

## Scope

This cleanup covers the workspaces that had already completed functional and visual review:

- Welcome;
- Kubernetes Operations Dashboard;
- Kubernetes Inventory Overview;
- Kubernetes Topology;
- Node Inventory;
- Namespace Inventory;
- Workload Inventory;
- Pod Inventory;
- Service Inventory.

The objective is canonical-only application code. Internal wrappers, alternate import paths,
old snapshot aliases, duplicate presentation columns, and unreferenced bridge files are removed
instead of retained as indefinite compatibility layers.

## Removed files

The following obsolete files are deleted and registered in `scripts/cleanup_obsolete_files.sh`:

- `app/static/js/inventory/topology_bootstrap.js`;
- `app/templates/inventory/components/_detail_macros.html`;
- `app/templates/inventory/nodes/partials/_inventory_scope.html`;
- `app/templates/inventory/namespaces/partials/_inventory_scope.html`;
- `app/templates/inventory/workloads/partials/_inventory_scope.html`;
- `app/templates/inventory/pods/partials/_inventory_scope.html`;
- `app/templates/inventory/services/partials/_inventory_scope.html`.

## Canonical ownership after cleanup

### Welcome

`/` and `/welcome` are owned directly by `welcome.index`. Welcome does not redirect through a
retired dashboard blueprint and has no compatibility route package.

### Kubernetes Dashboard

Dashboard services and sections import canonical ORM classes directly from `app.models`.
The dynamic model loader, alternate module probes, broad import exception masking, and the
small KPI description pass-through wrapper are removed.

### Inventory Overview

Inventory Overview remains one canonical full page with a dedicated
`resources-by-cluster-content` HTMX boundary for pagination. It does not use a generic resource
scope wrapper or a compatibility partial.

### Topology

`inventory/topology/index.html` loads `js/inventory/topology.js` directly. The canonical module
imports the Cytoscape ESM renderer itself and owns startup failure presentation. The removed
bootstrap no longer bridges a renderer through `window.cytoscape` or reloads a second workspace
module.

### Node, Namespace, Workload, Pod, and Service

Each audited resource owns one `*-page-workspace` partial. Scope-changing filters replace that
workspace. Page-size and pagination controls replace only `*-table-content`. The former
`*-inventory-scope` wrapper files and route fallback behavior are not used by these pages.

## Canonical evidence cleanup

- Workload read and export paths accept canonical operational states and top-level replica/update
  evidence only. Legacy `Running`, `Succeeded`, and `Scheduled` aliases and nested export fallbacks
  are removed.
- Namespace control evidence no longer infers successful collection merely because a row belongs
  to an older committed generation.
- Pod read and export paths require explicit specification/runtime/reference evidence flags.
  Schema-version and old presentation-field inference are removed.
- Service port and external-address evidence lives only in `ServiceInventory.details`.
  Duplicate `ports` and `external_ip` columns and their bounded-string maintenance code are removed.

## Database change

Migration `20260805_service_inventory_v2` drops:

- `service_inventory.ports`;
- `service_inventory.external_ip`.

The migration is intentionally destructive for the duplicate presentation columns. Their complete
canonical values already exist in `service_inventory.details`. Deployments must run
`flask db upgrade` before starting application workers built from this revision.

## Compatibility boundaries intentionally retained

This cleanup removes internal KAORI compatibility bridges. It does not remove compatibility that
is part of an external provider contract:

- EndpointSlice collection may fall back to the Kubernetes Endpoints API only for permission,
  API-availability, or client-capability conditions. Unexpected provider errors still fail the
  generation.
- Kubernetes `master` and `control-plane` role labels are normalized to one canonical Control Plane
  role because both remain valid evidence from supported Kubernetes versions.

These are provider normalization boundaries, not alternate KAORI application implementations.

## Regression guard

`scripts/verify_core_workspace_legacy_cleanup.py` and its contract test prevent reintroduction of:

- deleted compatibility files;
- dashboard dynamic model loaders;
- audited Inventory scope wrappers;
- Topology bootstrap/global renderer bridges;
- legacy Workload/Pod/Namespace export inference;
- duplicate Service presentation columns.

The verifier is registered in `scripts/quality_gate.sh`.

## Functional corrections discovered during cleanup

The cleanup exposed one Dashboard correctness defect: generic Inventory queries counted historical rows across generations even though the Dashboard copy promised a committed snapshot. `repository.py` now applies `filter_current_generation()` automatically to every inventory model carrying `cluster_id` and `collected_at`. KPI counts, cluster-health rows, and latest inventory timestamps therefore share the same committed evidence boundary as the Inventory pages.

Topology collection and graph payload behavior remain unchanged at the route contract, but the 800+ line graph function was removed. The canonical implementation is split into typed contracts, committed-query repository, node builder, edge builder, graph assembler, presentation helpers, and service/cache orchestration. Node and edge payload constructors now accept typed specifications instead of fourteen loosely coupled parameters.

Dashboard KPI and cluster-health decision helpers now accept typed context objects. This removes high-argument internal APIs without retaining pass-through wrappers.

## Maintainability acceptance criteria

Reviewed core workspaces are guarded by `scripts/verify_core_workspace_code_health.py` with these maximums:

- 800 lines per Python module;
- 160 lines per function;
- 30 branch points per function;
- 8 parameters per function.

The verifier covers Welcome, the Kubernetes Dashboard package, Inventory Overview and routing, Topology, Node, Namespace, Workload, Pod, and Service presentation services. Resolved Dashboard and Topology entries were removed from the global code-health debt baseline rather than retained as permanent exceptions.

## Additional Topology corrections

The modular rewrite also closes two correctness defects that were hidden in the former monolithic
builder:

- the 350-node cap is now strict even when the remaining capacity is smaller than the number of
  active resource groups;
- Ingress route relationships are emitted only when the committed graph contains the corresponding
  Ingress node, preventing dangling edges when a parent Namespace is outside the selected scope.

Behavioral tests cover Cluster, Namespace, Workload, Pod, Service, Ingress, Node, storage, and
configuration relationships, including `owns`, `scheduled_on`, `routes_to`, `selects`, `uses`,
`binds`, and `mounts`.

## Final validation

The cleanup was validated on the supplied source tree with the following results:

- source hygiene: 1,841 tracked files passed;
- Python compilation: 858 source files passed;
- reviewed Jinja parsing: 62 templates passed;
- focused canonical cleanup, Dashboard, Topology, Inventory, and export tests: 64 passed;
- Welcome and Kubernetes contract suite: 212 passed, with two pre-existing failures outside this
  cleanup scope in Secret choice-card styling and the TLS schema-guard literal contract;
- migration graph: 91 revisions, one root, head `20260805_service_inventory_v2`;
- Inventory verifiers: Node, Namespace, Workload, Pod, and Service passed;
- core legacy cleanup and reviewed-scope code-health verifiers passed;
- JavaScript and shell syntax checks passed;
- Git whitespace validation passed.

The audit environment does not include Flask, Ruff, DjLint, or Pyright. Runtime browser testing,
full Flask integration tests, and those optional developer-tool checks must therefore run in the
KAORI development container after applying the patch. No result in this audit claims live browser
or connected Kubernetes validation.
