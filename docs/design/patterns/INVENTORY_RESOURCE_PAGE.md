# Inventory Resource Page Pattern v1.3

**Status:** Locked reference pattern  
**Scope:** Kubernetes Inventory Overview, Nodes, Namespaces, Configuration, Workloads, Pods, Services, Ingresses, Storage, and Topology

## Product contract

Kubernetes Inventory is the committed Kubernetes asset catalog. Web requests read normalized database snapshots only. Collection, normalization, and generation commits belong to worker-side synchronization; list, summary, detail, and topology requests must never introduce a hidden live Kubernetes API call.

All generation-scoped reads use the **latest committed inventory generation**. `ClusterInventory.collected_at` is the generation marker. Superseded or incomplete generations must not be mixed into current rows, filter options, details, counts, or topology relationships.

## Canonical resource-page structure

```text
Canonical Hero
Cluster onboarding blocker when setup is incomplete
Snapshot Context Bar when inventory scope is available
Resource Posture
Filter + Shared Inventory Table
Pagination 5 / 10 / 25 / 50
Detail Style 2 — Full Workspace Modal
```

Inventory Overview keeps its shared Side Drawer. Topology uses the adaptive visualization workspace with Controls/Inspector drawers below the wide breakpoint.

## Hero contract

Inventory Overview and the eight resource pages use the shared KAORI Hero implementation. The right-side header accessory is the approved **Status Badge Box** when operational/readiness state is shown. Do not create page-local hero geometry, icon boxes, badges, metric cards, or status treatments.

The Hero owns resource identity and high-level posture. Exact collection timestamp, generation coverage, and snapshot exceptions belong to the Snapshot Context Bar rather than duplicated Hero metadata.

## Authorization and readiness request contract

**Authorization before blocker evaluation** is mandatory.

Protected GET flow:

```text
request
  ↓
inventory.view authorization
  ↓
clusterless HTMX blocker
  ↓
request/filter validation
  ↓
committed-snapshot read
  ↓
render
```

A Blueprint-level `before_request` must not short-circuit protected Inventory pages. An unauthorized direct HTMX request must receive the authorization result before KAORI probes cluster readiness or reads Inventory data. `clusters.sync` remains a separate mutation permission for synchronization.

When the Kubernetes onboarding blocker is active, the page renders the canonical Hero plus onboarding blocker only. **Inventory Data Snapshot, posture summaries, tables, and topology workspace stay hidden** because they would imply an available committed inventory scope when no cluster is registered.

The Hero itself remains structurally stable while blocked. Its right panel must use the shared Kubernetes setup-blocked context from `components/cluster/_hero_blocked_context.html` with `Inventory Readiness` as the domain label. The normal Inventory posture/context panel returns only after cluster setup is available.
While blocked, Hero metadata must not present zero-valued asset/resource counters as committed evidence; use `Committed Inventory` plus `Cluster Setup Required` until a valid cluster scope exists.

All resource template registry entries are rooted at `inventory/kubernetes/<resource>/...`. Route helpers must never fall back to the retired `inventory/<resource>/...` namespace; the canonical namespace is release-verified so full-page and HTMX rendering cannot drift apart.

## Table and pagination contract

- Use shared `components/table.html` primitives and the Inventory block header.
- Default page size is **5**; allowed values are **5 / 10 / 25 / 50**.
- Resource services use SQL pagination through `app.common.pagination.paginate_query`; routes must not materialize all rows and slice them in Python.
- Namespaced resources use the shared Namespace identity macro.
- Technical identifiers use canonical technical-value treatment; semantic lifecycle/health state uses the shared compact rectangular status-label contract.
- Page-size and pagination requests update table content only. Scope/filter changes update the owning workspace so Hero context, summary, dependent filters, and rows remain consistent.

## Detail and progressive-disclosure contract

Nodes, Namespaces, Configuration, Workloads, Pods, Services, Ingresses, and Storage use **Detail Style 2 — Full Workspace Modal** through `components/resource_detail_modal.html` and shared detail-content primitives. Inventory Overview uses the shared Side Drawer. Topology uses the adaptive explorer Inspector/Details drawer.

Do not add page-local modal markup, local expandable-row JavaScript, nested scroll boxes, or a fourth disclosure pattern. Detail endpoints remain committed-snapshot reads and must not call Kubernetes live.

### Full Workspace Modal resource-header alignment

The leading resource icon, title/metadata, description, and state evidence form one identity block. Lifecycle/readiness/collection labels rendered beneath the description use the shared `detail.header_badge_row()` primitive and align with the **text-content column after the leading icon**. Do not place the state label as a separate flex child that drops below and aligns with the modal's outer left edge on narrower widths. This keeps Node through Configuration headers visually consistent without changing semantic status treatment.

## Architecture and ownership

```text
collectors/
  Kubernetes API collection + normalization
        ↓
persistence.py / synchronization.py
  atomic generation commit
        ↓
resources/ + overview.py + topology/
  committed read models
        ↓
routes.py
  HTTP / HTMX validation and rendering
```

Topology reads API Server identity from the canonical `Cluster.kubernetes_connection` database relationship. The relationship is eager-loaded for topology cluster reads; the presentation path must not call the Kubernetes integration resolver merely to display connection metadata.

## Performance and reliability

- Row lists are SQL-paginated before materialization.
- Aggregate/semantic summaries may scan a projection of the current committed generation when necessary; they must not cause route-level full-result slicing.
- Topology conditionally loads resource families according to scope/depth and applies its graph/cache/output safeguards. Cluster connection metadata is eager-loaded to avoid resolver/N+1 behavior.
- Missing or unavailable committed evidence renders a neutral unavailable/unknown state; it does not trigger a live-provider fallback.
- Synchronization is asynchronous and owns its own retry/failure feedback boundary. Read pages remain available against the last committed generation when collection is not running.

## Accessibility, typography, and visual consistency

- Human-facing headings, labels, field names, table headers, modal titles, and status descriptions use KAORI Title Case.
- Kubernetes names, namespaces, API values, label/annotation keys, hashes, and other technical identifiers retain native casing and use semantic technical typography where appropriate.
- Status is not communicated by color alone; shared status labels retain readable text and contrast in Light and Dark modes.
- Shared table headers, row actions, pagination controls, modal close controls, topology controls, and drawer controls must retain visible keyboard focus and accessible names.
- Responsive composition must remain usable on the 14-inch baseline and narrow viewports without horizontal page overflow.

## Reference implementations

- **Nodes:** capacity/platform/runtime/scheduling evidence.
- **Namespaces:** lifecycle, quota/LimitRange, Pod Security, workload composition.
- **Workloads:** operational state, rollout/configuration, associated Pods.
- **Pods:** placement/runtime/container/configuration evidence.
- **Services and Ingresses:** publication, backend, TLS/controller references.
- **Storage:** StorageClass/PV/PVC provisioning, capacity/access, binding/lifecycle.
- **Configuration:** protected ConfigMap/Secret key-index metadata; values are never decoded or displayed.
- **Topology:** committed cross-resource relationships with adaptive explorer presentation.

Lifecycle/configuration facts remain factual Inventory evidence until an explicit Governance policy evaluates them.

## L0–L7 release evidence

Final lock requires all applicable layers:

```text
L0 Static Quality
  quality_gate.sh --static + verify_inventory_final_lock.py

L1 Contract Test
  tests/contracts/kubernetes/test_inventory_final_release_contract.py
  existing per-resource Inventory contracts

L2 Unit Test
  tests/unit/inventory/

L3 Functional Test
  tests/inventory/

L4 Integration Test
  tests/integration/inventory/

L5 Security Regression
  tests/security/inventory/

L6 Rendering/UI Contract
  tests/rendering/inventory/

L7 End-to-End Smoke
  tests/e2e/inventory/
```

The final-lock verifier protects AuthZ ordering, committed-snapshot/provider boundaries, canonical Hero/table/modal/pagination composition, Topology database ownership, retired residual helpers/files, documentation ownership, and permanent test evidence.
