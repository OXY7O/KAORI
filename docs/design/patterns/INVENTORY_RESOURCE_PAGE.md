# Inventory Resource Page Pattern v1.4

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
Operational Posture — shared Section Intro
└── Resource Posture
Inventory Records — shared Section Intro
└── Filter + Shared Inventory Table
Pagination 5 / 10 / 25 / 50
Detail Style 2 — Full Workspace Modal
```

Inventory Overview uses the same Full Workspace Modal and Unified Resource Sheet V10 as the resource pages. Topology remains the deliberate exception and uses the adaptive visualization workspace with Controls/Inspector drawers below the wide breakpoint.

## Hero contract

Inventory Overview and the eight resource pages use the shared KAORI Hero implementation. The right-side header accessory is the approved **Status Badge Box** when operational/readiness state is shown. Do not create page-local hero geometry, icon boxes, badges, metric cards, or status treatments.

The Hero owns resource identity and high-level posture. Exact collection timestamp, generation coverage, and snapshot exceptions belong to the Snapshot Context Bar rather than duplicated Hero metadata.


Cluster-source actions use the canonical label **Open Cluster Integrations** and route to `integrations.kubernetes`. Do not alternate between `Manage Clusters`, `Open Cluster List`, and provider-specific wording on Inventory surfaces.

## Section hierarchy contract

Major Inventory workspaces use `components/section_intro.html` immediately above the owning card/table/visualization. The intro provides operator context without becoming another card.

Resource pages use:

```text
Operational Posture
└── <resource-specific posture card>

Inventory Records
└── <resource> Inventory table
```

This section hierarchy is also reused by Object Storage Systems, Object Storage Buckets & Containers, and Artifact Registry Projects, Repositories, and Artifacts. Domain evidence remains domain-owned; reuse applies to hierarchy and shared components rather than forcing identical metrics.

Artifact Registry resource posture remains committed-inventory evidence only:
- Projects summarize project identities, Registry-source participation, public visibility, and missing visibility evidence.
- Repositories summarize repository identities, Registry-source participation, referenced artifact counts, and observed pull-count evidence.
- Artifacts summarize digest-oriented identities, Registry-source participation, and tagged/untagged reference posture.

Security scan, governance, and runtime-correlation interpretation stay in their owning workspaces and are not pulled into Inventory merely for visual parity.

Inventory Overview uses `Inventory Assets` above the asset catalog and `Multi-Cluster Inventory` above the compact cluster table. Topology uses `Inventory Relationships` above the adaptive visualization workspace.

The section title and child card title must not repeat the same phrase. Preserve the child's existing shared component ownership and HTMX target boundaries.

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

The Hero itself remains structurally stable while blocked. Its eyebrow, H1, description, and metadata roles remain stable across Normal and Blocked states in accordance with the provider-prerequisite contract in #894. Its right panel must use the shared Kubernetes setup-blocked context from `components/cluster/_hero_blocked_context.html`, which delegates geometry to `components/provider_prerequisite/_hero_context.html`, with `Inventory Readiness` as the domain label. The normal Inventory posture/context panel returns only after cluster setup is available.

Blocked readiness is additive context, not replacement metadata. Factual registration/scope/count roles may resolve to zero when no Kubernetes provider is registered, but those values must not be presented as provider readiness or as evidence of a successful inventory collection. Do not replace the normal metadata vocabulary with blocker-only labels such as `Committed Inventory`; the provider-prerequisite context owns `Cluster Setup Required` and the below-Hero onboarding blocker owns remediation.

All resource template registry entries are rooted at `inventory/kubernetes/<resource>/...`. Route helpers must never fall back to the retired `inventory/<resource>/...` namespace; the canonical namespace is release-verified so full-page and HTMX rendering cannot drift apart.

## Table and pagination contract

- Use shared `components/table.html` primitives and the Inventory block header.
- Default page size is **5**; allowed values are **5 / 10 / 25 / 50**.
- Resource services use SQL pagination through `app.common.pagination.paginate_query`; routes must not materialize all rows and slice them in Python.
- Namespaced resources use the shared Namespace identity macro.
- Technical identifiers use canonical technical-value treatment; semantic lifecycle/health state uses the shared compact rectangular status-label contract.
- Page-size and pagination requests update table content only. Scope/filter changes update the owning workspace so Hero context, summary, dependent filters, and rows remain consistent.

## Detail and progressive-disclosure contract

Inventory Overview plus Nodes, Namespaces, Configuration, Workloads, Pods, Services, Ingresses, and Storage use **Detail Style 2 — Full Workspace Modal** through `components/resource_detail_modal.html` and Unified Resource Sheet V10 primitives. Artifact Registry Projects, Repositories, and Artifacts reuse the same Full Workspace Modal progressive-disclosure contract for committed Registry Inventory detail. Topology remains the deliberate exception because its adaptive explorer Inspector/Details drawers are part of the graph workspace itself.

Repository detail may expose a bounded artifact preview; Artifact detail may expose bounded tag references. These remain Inventory evidence only. Vulnerability, signature, SBOM, runtime-correlation, and governance interpretation stay in their owning Artifact Registry workspaces.

Do not add page-local modal markup, local expandable-row JavaScript, nested scroll boxes, or a fourth disclosure pattern. Detail endpoints remain committed-snapshot reads and must not call Kubernetes or Registry providers live.

### Full Workspace Modal resource-header alignment

The leading resource icon, title, metadata, and primary lifecycle/readiness/collection state form one identity group. Use the shared `detail.header_identity_row()` primitive so operational state such as `Ready`, `Not Ready`, lifecycle posture, backend readiness, and collection evidence sits beside the resource title and metadata instead of floating on a second line beneath the description. The description remains the supporting line below that grouped identity. The same grouped identity primitive is reused by other Full Workspace Modal surfaces such as Access administration, Object Storage Inventory, and TLS Governance so state never drifts onto a detached second line.

### Full Workspace Modal resource-sheet symmetry and utility actions

The four-column summary strip is a flush, full-width modal band immediately below the resource identity header; it must not use inset outer gutters, rounded card framing, or a detached outer border. The modal summary host owns the band boundary so scrolling evidence does not expose offset vertical framing. Its content remains the alignment reference for the evidence sheet below it. At `xl`, the descriptive rail uses the first quarter of the sheet and the evidence body uses the remaining three quarters. `detail.inventory_band_grid_classes()` owns this geometry and must also be reused by embedded metadata and related-resource collections; page-local fixed rail widths are not permitted.

Technical identifiers that operators frequently transfer into operational tooling may expose the shared icon-only copy control. Kubernetes UID/UID, System UUID, and concrete IP addresses are approved examples. The action must have an accessible name, use the global Clipboard behavior, and disappear for unavailable values.

Dense resource filters use the canonical `Search` field label with a concise domain-specific placeholder. Ingress DNS host actions may open only a concrete declared host using `http` or `https` derived from committed TLS declaration. Wildcard host declarations remain reference-only, and a direct-open action never implies DNS resolution, reachability, or service health.

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

## Inventory table contextual explanations (KAORI shared Info Tip)

When an Inventory table contains terms whose meaning may not be clear at a glance, place a concise, read-only `components/info_tip.html::render` control beside the **technical header label**. Namespace Inventory also exposes a tip beside its **PSA Enforce** in-cell label. The component already supports pointer hover, keyboard focus, click/touch and Escape; its popover is portaled to avoid clipping inside scrollable tables, including HTMX replacements. No parallel tooltip JavaScript or page-local hover CSS is allowed.

Apply this across Kubernetes Inventory Overview plus Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage and Configuration; Object Storage Systems and Buckets & Containers; and Artifact Registry Projects, Repositories and Artifacts. Keep header `<th>` semantics, column count, keyboard focus, stable unique tooltip IDs per rendered view, responsive Violet design tokens and default 5-row pagination. Explain the **meaning and evidence boundary** of reported values (for example PSA = Pod Security Admission, quota vs LimitRange, Service endpoints, PV/PVC binding, TLS secret references, Registry pull counts, bucket protection), not presumed health, compliance, or provider state. Missing values remain unknown, never a fabricated zero. Detailed data and source authority stay in the existing on-demand detail modal and committed Inventory snapshots.

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
  tests/unit/kubernetes/inventory/

L3 Functional Test
  tests/kubernetes/inventory/

L4 Integration Test
  tests/integration/kubernetes/inventory/

L5 Security Regression
  tests/security/kubernetes/inventory/

L6 Rendering/UI Contract
  tests/rendering/kubernetes/inventory/

L7 End-to-End Smoke
  tests/e2e/kubernetes/inventory/
```

The final-lock verifier protects AuthZ ordering, committed-snapshot/provider boundaries, canonical Hero/table/modal/pagination composition, Topology database ownership, retired residual helpers/files, documentation ownership, and permanent test evidence.
