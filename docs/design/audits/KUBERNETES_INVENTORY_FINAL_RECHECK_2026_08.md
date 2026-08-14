# Kubernetes Inventory Final Recheck — August 2026

## Scope

This Final Recheck covers Inventory Overview, Nodes, Namespaces, Configuration, Workloads, Pods, Services, Ingresses, Storage, and Topology. Existing locked visual composition remains the baseline; no redesign is introduced.

## Product and architecture decision

Inventory is the committed Kubernetes asset catalog. Worker collection owns live Kubernetes API access and atomic generation commits. Web list, summary, detail, and topology paths read the latest committed generation from the database only.

The final recheck found and corrected three release-relevant residuals:

1. **Authorization ordering:** the clusterless HTMX response previously lived in a Blueprint `before_request`, which could short-circuit route-level `inventory.view`. It is now a protected-view guard that executes after authorization.
2. **Legacy/dead surface:** unused `format_byte_count`, `format_gib`, `_split_inventory_values`, and the empty/stale Inventory partial README are retired.
3. **Topology ownership:** API Server display metadata now comes from the eagerly loaded canonical `Cluster.kubernetes_connection` relationship. The read side no longer invokes the Kubernetes integration resolver for presentation metadata.
4. **Post-lock modal alignment refinement:** Full Workspace Modal lifecycle/readiness/collection labels now use one shared header-state row aligned with the title/description text column. This removes the detached label placement below the leading resource icon without changing modal content or status semantics.
5. **Canonical template routing:** the shared resource-template registry had regressed to `inventory/<resource>/...` while committed templates live under `inventory/kubernetes/<resource>/...`, causing full-page `TemplateNotFound` failures such as `/inventory/nodes`. The registry and release contracts now validate the canonical namespace for every resource page and HTMX partial.
6. **Blocker-safe evidence visibility:** `Inventory Data Snapshot` is now rendered only after the cluster onboarding blocker clears. Overview, Topology, and every resource workspace show Hero + onboarding guidance while blocked; snapshot/posture/table content remains hidden.
7. **Storage scope parity:** Storage Inventory now populates the same `scope_label` Hero evidence used by the other resource pages.
8. **Rendering-test ownership:** Inventory rendering coverage now points to `app/templates/inventory/kubernetes`, preventing a stale test namespace from silently missing the committed template tree.
9. **Shared setup-blocked Hero:** Inventory Overview, all resource pages, and Topology now inherit the Kubernetes Operations Dashboard blocker pattern through `components/cluster/_hero_blocked_context.html`. Hero geometry remains stable while normal posture evidence is replaced by `Inventory Readiness / Cluster Setup Required`.
10. **Hero purpose copy refinement:** resource Hero descriptions now give slightly richer committed-inventory context while remaining inside the global 7–12 word target.

## KAORI UI standard applicability

| Standard | Inventory decision |
| --- | --- |
| Violet / Light / Dark | Shared semantic tokens; no page-local palette. |
| Hero | Canonical Hero; resource right accessory = **Status Badge Box**. |
| Table | Shared Inventory table pattern. |
| Pagination | Default 5; options 5 / 10 / 25 / 50. |
| Status | Shared compact rectangular semantic status labels. |
| Tabs | N/A for resource lists; Topology uses visualization controls rather than peer tabs. |
| Right context rail | N/A for canonical resource lists. |
| Progressive disclosure | Resource pages = Full Workspace Modal; Overview = Side Drawer; Topology = adaptive Inspector/Details drawer. |
| Toast/loading | Read pages use canonical loading; sync mutation uses canonical operational feedback. |
| Navbar/sidebar | Global application shell. |
| Accessibility | Shared labels/focus/modal/drawer controls; technical identifiers preserve native semantics. |
| Responsive | 14-inch baseline plus narrow adaptive table/detail/topology behavior. |

## Security and reliability

Protected GET requests follow `inventory.view → clusterless blocker → committed read`. Unauthorized direct HTMX requests must not probe cluster readiness. Synchronization remains protected by `clusters.sync` and executes asynchronously.

The web read side has no live Kubernetes/Prometheus/network-client fallback. Missing evidence remains neutral/unavailable against the last committed generation rather than triggering a provider call.

## Performance

Resource rows use SQL pagination before materialization. Dependent filter options and summaries are generation-scoped. Topology loads only requested resource families and eager-loads cluster connection metadata rather than performing per-cluster resolver work. Current-generation summary projections remain acceptable read-model work; route-level `.all()` plus Python slicing is prohibited.

## Legacy/dead-code disposition

Retired in this recheck:

```text
app.inventory.kubernetes.formatting.format_byte_count
app.inventory.kubernetes.formatting.format_gib
app.inventory.kubernetes.resources.common._split_inventory_values
app/templates/inventory/partials/_README.md
Blueprint-level Inventory clusterless before_request
Topology integration-resolver presentation dependency
```

Historical migrations and active collector compatibility for Kubernetes API-version differences are not classified as dead compatibility code when they are required to collect supported cluster versions.

## L0–L7 evidence

```text
L0 Static Quality
  scripts/verify_inventory_final_lock.py
  canonical quality_gate.sh static/toolchain checks

L1 Contract
  tests/contracts/kubernetes/test_inventory_final_release_contract.py
  existing Inventory resource contracts

L2 Unit
  tests/unit/inventory/test_inventory_topology_selection.py

L3 Functional
  tests/inventory/test_inventory_route_characterization.py
  existing Inventory behavior suites

L4 Integration
  tests/integration/inventory/test_node_inventory_read_model.py

L5 Security Regression
  tests/security/inventory/test_inventory_security.py

L6 Rendering/UI Contract
  tests/rendering/inventory/test_inventory_rendering.py

L7 End-to-End Smoke
  tests/e2e/inventory/test_inventory_smoke.py
```

## Release verdict

**TARGETED FIX — LOCK REMAINS; DEVCONTAINER RUNTIME VALIDATION REQUIRED**

Source-level verifier, architecture, rendering, security, and contract evidence must be green, followed by authoritative devcontainer Ruff/Ruff Format/djLint/Pyright/Prettier, Functional/Integration/E2E execution, browser smoke, and the full release gate. Once those pass, Inventory becomes **PASS — LOCKED** without reopening its visual design.

## Blocked Metadata and Network Inventory Copy Follow-Up

A cross-domain Hero review found that the setup-blocked right panel was already correct, but Inventory Hero metadata on the left could still render zero-valued counters such as `0 Services in Scope` or `0 Collected Objects`. When no cluster is registered, those values can be mistaken for committed inventory evidence rather than an unavailable source scope.

Inventory Overview, every resource Hero, and Topology now replace normal numeric metadata while blocked with `Committed Inventory` and `Cluster Setup Required`. Normal counters return unchanged after cluster setup is available. Service and Ingress purpose copy is also refined within the canonical Hero copy budget to include endpoint readiness/backend registration and routing posture respectively.
