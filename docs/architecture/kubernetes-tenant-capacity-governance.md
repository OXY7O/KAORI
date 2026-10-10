# Tenant Capacity Governance

Issue #654 owns provider-neutral Tenant Capacity Governance for Kubernetes Tenant Management v1.

## Authority boundary

- Kubernetes remains the execution platform.
- ResourceQuota remains a namespace enforcement primitive; it is **not** presented as physical node reservation.
- KAORI owns normalized allocation intent, committed allocation evidence, deterministic preflight, decision history, and auditability.
- #113 owns Resource Profile and namespace allocation snapshots.
- #654 owns Tenant Allocation Budget arithmetic and allocation allow/block decisions.
- #125, #123, and Tenant reporting must consume committed #654 evidence rather than recomputing capacity independently.

Normal operational preflight performs no live Prometheus or Kubernetes request.

## Capacity evidence

The baseline capacity source is the committed `analytics.capacity` materialization for the selected cluster with the canonical `24h` parameters.

The required schedulable-capacity facts are:

- Ready-worker allocatable CPU;
- Ready-worker allocatable memory;
- Ready-worker allocatable Pod slots;
- snapshot identity;
- snapshot state;
- data cutoff.

Persistent-storage physical/backend capacity is deliberately not inferred from this Capacity Analytics snapshot. The logical Tenant Storage Budget is explicit policy until dedicated Kubernetes Storage Analytics provides authoritative PV/PVC/backend correlation.

A positive allocation change fails closed when the required snapshot is missing, invalid, expired, or stale. Refreshing Capacity Analytics is the operator action; #654 does not bypass materialization with a live Metrics Source query.

## Tenant Capacity Policy

One policy is committed per cluster.

The policy records:

- platform/system CPU reserve;
- platform/system memory reserve;
- platform/system Pod reserve;
- operational safety headroom percentage;
- known unmanaged CPU request commitment;
- known unmanaged memory request commitment;
- known unmanaged Pod commitment;
- optional explicit Tenant Storage Budget.

There is no implicit policy row. An operator must explicitly configure the policy before positive Tenant allocation can be admitted.

Reserve and unmanaged values use Kubernetes quantity syntax and may explicitly be zero. Safety headroom is an integer percentage from 0 through 99.

Unmanaged commitment is a governed request commitment outside KAORI Tenant Management. It is not current utilization and is not inferred from PVC quota, limits, or filesystem usage.

## Allocation Budget

For CPU, memory, and Pods:

```text
Tenant Allocation Budget
= Ready-worker allocatable
- platform/system reserve
- safety headroom
- known unmanaged commitment
```

Safety headroom is calculated from Ready-worker allocatable capacity for all three schedulable dimensions.

Storage uses a different contract:

```text
Tenant Storage Budget
= explicit operator-governed logical allocation ceiling
```

It is compared with aggregate committed `requests.storage` and is not presented as physical/backend free space.

A negative derived CPU/memory/Pod result is clamped to zero.

## Tenant committed allocation

KAORI aggregates the frozen effective namespace allocation snapshots from #113:

- `allocation_quota_json["requests.cpu"]`;
- `allocation_quota_json["requests.memory"]`;
- `allocation_quota_json["pods"]`;
- `allocation_quota_json["requests.storage"]`.

The aggregate represents governed Tenant request commitment. It does not claim that ResourceQuota reserves scheduler capacity.

Existing namespace allocations remain committed even when provider state is drifted or failed because KAORI must not silently free capacity intent before an explicit governed allocation change.

An unbounded governed dimension remains explicit. KAORI does not coerce unbounded to zero. A positive allocation cannot be proven safe when CPU, memory, Pod, or configured storage-budget commitment is unbounded.

## Capacity states

State is evaluated from governed budget versus committed/projected Tenant request allocation:

- **Healthy** — more than 40% request-budget headroom remains in both dimensions.
- **Near Capacity** — at least one dimension has 40% or less headroom.
- **Critical** — at least one dimension has 15% or less headroom.
- **Exhausted** — at least one dimension has no remaining headroom without exceeding the budget.
- **Overcommitted** — committed/projected allocation exceeds the budget.
- **Unknown** — required capacity or commitment evidence is incomplete.

A projection exactly equal to the budget may be admitted and is reported as Exhausted. A projection above the budget is blocked.

## Preflight behavior

New namespace allocation and future positive allocation edits must pass preflight before provider reconciliation.

Preflight records:

- source snapshot identity/state/data cutoff;
- policy inputs;
- current aggregate Tenant commitment;
- current allocation;
- proposed allocation;
- projected commitment;
- projected headroom;
- shortfall;
- allow/block decision;
- resulting capacity state;
- correlation evidence.

Blocked preflight is committed as decision history but does not create a Tenant namespace intent and performs no ResourceQuota/LimitRange/provider mutation.

An allowed decision is referenced by the committed Tenant namespace allocation.

When cluster capacity contracts and existing commitments exceed the budget, state becomes Overcommitted without rewriting existing namespace allocations. Allocation reductions remain valid. Further positive allocation changes remain blocked until the deficit is corrected.

## Existing namespace allocation changes

A managed namespace changes allocation by selecting another committed Resource Profile version. Inline per-namespace quota overrides are not accepted.

KAORI evaluates the frozen current namespace allocation against the proposed Resource Profile snapshot before mutating the namespace record or provider state.

The operation is classified from governed CPU, memory, Pod, and configured storage commitment:

- `increase` when at least one governed request dimension increases or becomes unbounded;
- `decrease` when no governed dimension increases and at least one decreases or becomes bounded;
- `no_change` when both governed request dimensions are unchanged.

For an increase, current committed capacity evidence and policy must be sufficient to prove the projected allocation safe. Missing/stale capacity evidence, missing policy, unbounded aggregate commitment, or projected budget shortfall blocks the mutation and commits only the capacity-decision evidence.

For a decrease or no-change operation, KAORI may proceed even while capacity evidence is Unknown because the change does not add CPU/memory request commitment. The decision remains `Unknown` when budget/headroom cannot be established, preserving the evidence limitation instead of guessing.

An allowed change updates the namespace source Resource Profile identity/version and frozen allocation snapshot, links the allow decision, then reconciles ResourceQuota and LimitRange through the existing Native Kubernetes provider path. Reconciliation failure remains observable as failed/drift evidence; KAORI does not claim provider state matches desired intent until read-back verifies it.

## Storage

`requests.storage` is now a governed **logical allocation dimension** when the cluster policy has a Tenant Storage Budget.

KAORI compares aggregate committed Tenant `requests.storage` with that explicit budget before provider reconciliation.

The logical budget does not claim physical reservation or backend free space. It is an operator-defined admission ceiling that can be deliberately lower than physical capacity.

Physical/usable storage capacity remains a separate evidence problem. Kubernetes Storage Analytics workstream #782 owns future correlation across StorageClass, PV, PVC, Tenant/Namespace, and authoritative storage-backend capacity. Until that evidence exists, KAORI must not derive physical storage headroom from node filesystem metrics, PV totals, or PVC quota.

## Tenant Allocation Overview (#1034)

The read-only **Resource Profiles → Capacity Governance → Tenant Allocation Overview**
adds a per-cluster visual projection above the existing Allocation Budget table.
The operator selects a cluster in the overview; the routine page renders from
the same committed #654 summaries (`build_capacity_governance_summaries`):
budget, committed requests, headroom, capacity state, snapshot status and
cutoff. Four horizontal accessible bars represent **CPU requests**, **memory
requests**, **Pod slots** and the explicit **logical requests.storage ceiling**.
Bar width is presentation only and never participates in the allow/block
decision. Exact canonical numeric values remain visible alongside the bars;
a deficit is labeled explicitly rather than concealing overcommit.

Create-in-KAORI and provider-Adopt enter the **same effective committed
Namespace allocation** ledger. The Tenant contribution view partitions that
ledger by Tenant while using the existing #654 shared-quota selection and
`_aggregate_committed_allocation` arithmetic per Tenant. Admitted Capsule
Tenant-shared quotas are counted **once** rather than added once per child
Namespace. Ambiguous shared authority, unbounded dimensions and missing/stale
materialized Capacity Analytics evidence remain explicit Unknown/Not Governed,
never fabricated as zero free capacity. Tenants with no committed namespaces or
shared allocation are not counted as committed budget consumers. The Tenant
breakdown is paginated using the canonical five-row default and allows
Namespace identities to be expanded for correlation.

**Boundary:** this is request-budget governance and an **admission planning
read model**, not actual CPU/memory use, Pod runtime pressure, or physical
storage reservation. Actual metrics and backend capacity remain in dedicated
Kubernetes Analytics; the link to Capacity Analytics is permission-gated.
The view performs no live provider/Prometheus call, no adoption/provisioning
mutation, no new quota arithmetic or independent admission rule. Cluster policy
changes and Namespace allocation increases still require the same #654
preflight and provider reconciliation/write-readback governance. Projected
transaction impact for Create/Adopt is scoped separately under #125.

### Tenant Allocation Overview UX refinement (#1038)

The cluster selector uses the existing HTMX partial-response pattern to refresh the
selected overview immediately on change; the non-JavaScript form fallback remains
available. The permission-guarded Capacity Analytics destination uses the shared
KAORI secondary action contract. No live provider or Prometheus query is added.

The compact budget guidance is an accessible disclosure rather than an always-open
paragraph: **CPU, memory and Pod request budget = Ready-worker allocatable −
platform reserve − safety headroom − unmanaged commitment**. Logical
`requests.storage` is a separately governed policy ceiling, not physical
storage availability. `ResourceQuota` enforces Kubernetes quota and never
constitutes a physical node-resource reservation.

**Tenant Contributions is detail on demand:** the overview shows the committed
Tenant count and opens the canonical native KAORI dialog. A large, responsive
dialog retains the committed Tenant/Namespace and Native/Capsule evidence,
search, 5-row default pagination, selectable page size, accessibility semantics
and Tenant Registry navigation. The dialog's nested HTMX target is restricted to
its registry section: pagination, search and page-size changes must **not**
replace or close the parent dialog or the outer Capacity Overview. Cluster
changes intentionally replace the outer overview and reset pagination.

The contribution registry displays a stable Tenant ID alongside the Tenant
name so same-named adopted and managed records remain distinguishable.
The read-model search matches Tenant name/ID, Namespace, Environment, and
allocation authority, but does **not** alter committed #654 aggregation.
Near Capacity, Critical and Exhausted overview headers may identify the
**lowest proportional governed headroom** from already computed presentation
bars. This is display context only, not a separate capacity-state rule, admission
approval, or replacement of canonical budget/shortfall evidence.

The integrated review branch is a **DevContainer Visual QA candidate**.
Source changes and tests may be authored before gate authorization, but no
CI/CD Developer Check, Full Admission, staging deployment, or production
promotion is implied. Confirm keyboard/focus behavior, responsive dialog
pagination and cluster-change semantics with a human before acceptance.

### Review / quality evidence

- Verify positive, zero-budget, overcommitted, unknown/missing, unbounded and
  logical-storage-unconfigured visuals alongside the existing detail modal.
- Prove aggregate and per-Tenant values against #654 for Native and Capsule
  shared allocations, including a shared Tenant with multiple Namespaces.
- Check cluster selection, HTMX partial swap, pagination, expanded Namespace
  identities, permission-scoped Analytics link, keyboard, accessible text,
  light/dark and responsive layouts.
- Human DevContainer visual acceptance is separate from Developer Check,
  Full Admission and provider UAT. No admission/deployment gate is implied by
  this read-only presentation.

## UAT

Staging UAT for #654 must demonstrate:

1. explicit cluster capacity policy configuration;
2. allowed bounded allocation within fresh committed capacity evidence;
3. denied allocation with actionable CPU/memory/Pod/logical-storage shortfall evidence;
4. no Namespace/ResourceQuota/LimitRange mutation after a denied preflight;
5. Overcommitted state after simulated/real capacity contraction without rewriting existing Tenant allocations;
6. recovery after capacity increases or Tenant commitment is reduced;
7. persisted decision history with snapshot cutoff and policy/budget inputs.
