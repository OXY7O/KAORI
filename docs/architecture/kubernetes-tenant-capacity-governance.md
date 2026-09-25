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

The required facts are:

- Ready-worker allocatable CPU;
- Ready-worker allocatable memory;
- snapshot identity;
- snapshot state;
- data cutoff.

A positive allocation change fails closed when the required snapshot is missing, invalid, expired, or stale. Refreshing Capacity Analytics is the operator action; #654 does not bypass materialization with a live Metrics Source query.

## Tenant Capacity Policy

One policy is committed per cluster.

The policy records:

- platform/system CPU reserve;
- platform/system memory reserve;
- operational safety headroom percentage;
- known unmanaged CPU request commitment;
- known unmanaged memory request commitment.

There is no implicit policy row. An operator must explicitly configure the policy before positive Tenant allocation can be admitted.

Reserve and unmanaged values use Kubernetes quantity syntax and may explicitly be zero. Safety headroom is an integer percentage from 0 through 99.

Unmanaged commitment is a governed request commitment outside KAORI Tenant Management. It is not current utilization and is not inferred from PVC quota, limits, or filesystem usage.

## Allocation Budget

For each CPU/memory request dimension:

```text
Tenant Allocation Budget
= Ready-worker allocatable
- platform/system reserve
- safety headroom
- known unmanaged commitment
```

Safety headroom is calculated from Ready-worker allocatable capacity.

A negative result is clamped to zero.

## Tenant committed allocation

KAORI aggregates the frozen effective namespace allocation snapshots from #113:

- `allocation_quota_json["requests.cpu"]`;
- `allocation_quota_json["requests.memory"]`.

The aggregate represents governed Tenant request commitment. It does not claim that ResourceQuota reserves scheduler capacity.

Existing namespace allocations remain committed even when provider state is drifted or failed because KAORI must not silently free capacity intent before an explicit governed allocation change.

An unbounded CPU or memory request dimension remains explicit. KAORI does not coerce unbounded to zero. A positive allocation cannot be proven safe while aggregate request commitment is unbounded.

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

## Storage

PVC/request-storage quota is retained in Resource Profile allocation evidence, but physical storage admission is not inferred from it.

Physical storage governance requires provider/storage capability evidence and remains separate from the baseline CPU/memory request preflight.

## UAT

Staging UAT for #654 must demonstrate:

1. explicit cluster capacity policy configuration;
2. allowed bounded allocation within fresh committed capacity evidence;
3. denied allocation with actionable CPU/memory shortfall evidence;
4. no Namespace/ResourceQuota/LimitRange mutation after a denied preflight;
5. Overcommitted state after simulated/real capacity contraction without rewriting existing Tenant allocations;
6. recovery after capacity increases or Tenant commitment is reduced;
7. persisted decision history with snapshot cutoff and policy/budget inputs.
