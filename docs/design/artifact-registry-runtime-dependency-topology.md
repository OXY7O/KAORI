# Artifact Registry — Runtime Dependency Topology

**Authority:** #1692 (bounded implementation), #897 (Registry ↔ Kubernetes correlation);
#558 (provider-neutral Registry foundation), #747 (page-level navigation),
`docs/design/patterns/KUBERNETES_TOPOLOGY.md` (shared visualization grammar).

## Placement and boundaries

**Artifact Registry → Runtime** is a sidebar capability. Its canonical
level-three Integrated Workspace Tabs appear **above the Hero**, using the
existing `capability_navigation` injection from `layouts/app.html` and
`components/workspace_tabs.html::render_navigation`:

1. **Overview** — `/artifact-registry/runtime/overview`; default sidebar
   destination, committed correlation posture, freshness, evidence coverage
   and links to detailed explorations.
2. **Runtime Usage** — `/artifact-registry/runtime`; existing searchable
   Runtime Bindings table/filter/detail registry, preserved for backwards
   compatibility with deep links and other domain handoffs.
3. **Topology** — `/artifact-registry/runtime/topology`; read-only
   artifact-centric Adaptive Explorer graph/list/inspector.

The Runtime menu is named **Runtime**, not `Runtime Usage`. Tab labels are
exactly **Overview**, **Runtime Usage**, **Topology**. They are page-level views,
not an additional sidebar level or an inner graph tab family. The
`/artifact-registry/runtime/topology/data` endpoint retains its existing
`artifact_registry.view` permission and read-only filters. Tab navigation
preserves supported URL scope filters while not carrying list pagination or
graph-only display state.

The topology is a read-only, artifact-centric graph over the existing
committed RegistryWorkloadBinding materialization. It is **not** an additional
provider API, relationship database, scanner, or Intelligence recommendation
lifecycle. Graph and Resource List present the **same bounded query slice**,
and the inspector links back to the canonical Runtime Bindings view.

## Relationship model

```text
Registry artifact digest
    └─ runtime_usage (derived RegistryWorkloadBinding evidence)
        Kubernetes cluster
            └─ contains → Namespace
                └─ contains → Workload
                    └─ owns → Pod (container references in inspector)
```

The parent hierarchy from Cluster to Pod is **presentation context** extracted
from the binding, not a separate assertion of complete Kubernetes resource
ownership. Workload name/type can be unresolved; this is displayed as
`Not Resolved`, never invented. Artifact identity is source-scoped and
digest-first; tag-only correlation remains lower-confidence. A single
artifact-to-cluster edge may aggregate both match types and is then
`mixed`, with individual evidence available in Resource List / inspector.
Vulnerability counts belong to the Registry Artifact and must never be summed
as independent new CVEs on every affected Pod or Cluster.

## Read model and completeness

1. Start from active/enabled Registry source identity, using the same
   normalized SQL filters as Runtime Usage (Registry source, cluster,
   namespace, artifact, match type, security exposure and search).
2. Compute exact in-scope committed binding count before display limiting.
3. Select at most **45 bindings** in stable artifact/cluster/namespace/
   workload/pod/ID order; hydrate only those matching entities.
4. Deduplicate graph nodes/edges deterministically; expose total, displayed,
   omitted, and visible-node counts to the client.
5. Scope, identity, and confidence are never broadened to satisfy missing
   evidence. An invalid selected Registry source fails closed.
6. Load Cytoscape only for the graph. The accessible Resource List and
   inspector use the same response and remain usable if Cytoscape fails.

A graph slice is **not** a complete fleet blast-radius conclusion when
`omitted_bindings > 0`. Refine scope rather than treating omitted edges as
absent consumers.

## Readiness and negative evidence

The graph exposes the existing Runtime Correlation readiness:
`not_materialized`, `inputs_changed`, `refreshing`,
`refresh_failed`, `stale`, `ready`. A previous committed correlation
may be displayed while provisional, but never labeled as current/complete.
No bindings under incomplete evidence is **not** a verified "No Impact".

The normal UI neither calls Harbor nor queries live Kubernetes, and Reload
Snapshot re-fetches only the committed KAORI graph JSON. Synchronization
and materialization remain owned by canonical jobs.

## UI and interaction

Reuse `visualization_workspace.html` (Adaptive Explorer), Violet semantic
tokens, shared Hero, Inventory Data Snapshot, table helpers, overlay inspector,
graph/list fallback, and responsive/light/dark patterns. Do not add a third
sidebar level. Filter changes are URL-backed and bounded; local graph
presentation actions do not change the committed data. The list defaults to
five rows per page. Export PNG is an image of the **visible** graph slice,
not an authoritative fleet report.

## Current limitations and UAT gates

- #1441 remains the canonical source identity/container-precision follow-up;
  #929 remains materialization performance/heartbeat authority.
- The MVP does not infer source-control lineage, deployments, network
  communication, Service Catalog dependencies, or operational causality.
- DevContainer UAT must verify correct visible relationships, evidence
  states, filters, narrow viewport, light/dark, keyboard access, renderer
  fallback, and omission warnings with >45 in-scope bindings.
- Do not proceed to Developer Check, Full Admission, staging/main promotion
  or release without explicit human acceptance. Review integration target:
  `kaori/review/staging-uat`.
