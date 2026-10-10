# Reusable Analytics Dataset and Materialization Extension Standard

**Authority:** [#1105](https://github.com/OXY7O/KAORI/issues/1105), child implementation [#1107](https://github.com/OXY7O/KAORI/issues/1107). This is a consolidation of approved K8s, Object Storage and Metrics Source behavior—not a parallel analytics framework. Existing architectural owners remain authoritative: `job-execution-foundation.md`, `kubernetes-analytics-worker-snapshot-boundary.md`, `app/storage/object_storage/analytics/README.md`, `app/integrations/observability/metrics_source/README.md` and `app/platform_operations/jobs/README.md`.

## Boundary and ownership

```text
Domain capability → instance/asset binding (source provider stays authoritative)
  → qualified provider adapter & versioned metric semantics
  → MetricsConsumer.instant/range OR qualified non-metrics source contract
  → canonical registered JobDefinition / JobPolicy / JobExecution
  → domain-owned bounded worker dataset builder
  → committed snapshot [domain, instance, dataset, scope, time_range, version]
  → shared read-only Controls/Readiness, section tracker, tables and intelligence links
```

- **Metrics Source** owns backend selection, binding validation, routing, source capabilities and `query.instant`/`query.at`/`query.range`. Prometheus and Thanos are implementations of source adapters, not domain-level singleton assumptions.
- **Platform Operations Jobs** owns registration, schedule, queue admission, quotas, fingerprint/dedup, cancellation, JobExecution progress/terminal state, retries and audit. No analytics domain may create another scheduler or execute Celery tasks directly from HTTP.
- **Domain Analytics** owns source eligibility, normalized metric semantics, provider-qualified query profiles, pure calculations, dataset/version meaning, time range, materialization write policy and failure interpretation.
- **KAORI Committed Evidence** is the operational UI authority. Web request handlers must not reach provider metrics/alert APIs just to render a normal page; only a bounded on-demand dispatch is permitted when eligible data is absent/stale.
- **Central Intelligence** owns recommendation/escalation lifecycle. Domain Analytics produces facts and correlated evidence, never its own shadow recommendation system.

## Reuse the existing implementations

| Capability | Kubernetes | Object Storage | Artifact Registry |
|---|---|---|---|
| Source asset | Kubernetes cluster | Object Storage system | Registry integration |
| Provider-first evidence | Kubernetes API inventory | committed Object Storage Inventory | committed Registry Inventory/Security/Governance/Runtime |
| Metrics | `MetricsConsumer` cluster binding | qualified Object Storage `MetricsConsumer` binding | Registry `MetricsConsumer` instance binding |
| Materialization | `analytics.materialize` | `object_storage.analytics.materialize` | `artifact_registry.analytics.materialize` |
| Queue | `analytics-batch` | `analytics-batch` | `analytics-batch` |
| Heavy forecast | `analytics.forecast.materialize` | `object_storage.forecast.materialize` | do not fabricate unsupported history/forecast |
| Snapshot | `AnalyticsSnapshot` keyed by dataset + canonical params | `ObjectStorageAnalyticsSnapshot` keyed by system + range | `RegistryAnalyticsSnapshot` currently written as `current` |
| History | range-based worker dataset | range-based operational and forecast worker datasets | **gap**: instant samples + prior snapshot delta only |
| UI progress | requested-HTMX section tracker; separate JobExecution | shared Controls/readiness and worker progress | shared section tracker and Controls/readiness |

The Registry gap is governed by [#1108](https://github.com/OXY7O/KAORI/issues/1108), not disguised by the common UI. Its `snapshot_window` selector currently tests the **age of the latest materialized snapshot**, not how far back Prometheus/Thanos was queried. Never present this as measured time-series history until worker range materialization is implemented and validated.

## Canonical cross-domain Analytics presentation (#1122)

A single shared Jinja module — `analytics/components/_controls_readiness.html`
— owns the **header**, selector label/control CSS, paired controls grid,
two-card readiness grid, normalized **Source Status** card, and **Latest
Analytics Data Snapshot** card. The same module is used by Kubernetes,
Object Storage, and Artifact Registry Analytics. Shared HTMX section progress
remains independently owned by `analytics/components/_section_load_tracker.html`;
neither UI component owns a provider collector, worker, or data query.

| Presentation responsibility | Canonical owner | Domain supplies |
|---|---|---|
| Controls header and loading bar | `shared_readiness.frame` | capability title, scope description, busy/worker status, HTMX indicator |
| Selector label, form field and focus styles | `shared_readiness.selector` | field ID/name, options, selected value, optional legacy bookmark |
| Filter/readiness two-column geometry | `shared_readiness.controls_grid`, `readiness_grid` | filter/section content |
| Source badge, status dot and 2-cell details | `shared_readiness.source_card` | real readiness status, provenance, labels/values; K8s optional response/check icons |
| Snapshot status and committed evidence | `shared_readiness.snapshot_card` | generated time, dataset, coverage/expiry and worker attempt |
| Canonical seven time-range values and labels | `app/common/analytics/params.py::get_allowed_time_ranges` | selected range, dataset semantics, provider retention validation |
| Requested HTMX section tracker | `analytics/components/_section_load_tracker.html` | actual bounded fragment requests, not Celery percentage |

Kubernetes Overview now delegates its former page-local header, selectors,
and source-status geometry to shared macros. Its
`kubernetes/analytics/components/_metrics_source_status.html` only
classifies Metrics Source states and supplies response time/checked-at:
the shared `source_card` renders the actual card. Object Storage delegates
System/Time Range/History Window/Alert Source controls to `selector`
and retains committed Metrics Source, Inventory and Forecast provenance.
Registry delegates provider and time-range controls to `selector` without
importing any Kubernetes-owned template. Normal seven options come from
`get_allowed_time_ranges`; the Registry `current` bookmark remains an
explicit **snapshot-age** selector and is not historical source telemetry.

For a **new provider in an existing domain**, register the provider adapter,
qualify its capabilities, and supply the same normalized context/options;
do **not** copy or fork the view. For a **new Analytics domain**, use the
existing shared macros, canonical time-range source, section tracker,
readiness model, and registered jobs; implement only the domain-specific
source adapter, dataset builder, and evidence projection.

**Visual changes** to these canonical components propagate automatically to
all consumers. Domain-specific evidence semantics, provider capability
validation, section availability and the meaning of a time-range query
are deliberately **not** centralized into presentation code. A component
change still requires visual/a11y regression checks of all three consumers
before acceptance; no design drift is accepted as a domain exception by default.

## Extension checklist for a fourth domain

1. Define domain capability and asset type before provider product or instance. Register provider-qualified source capabilities and integration binding using the existing Integration Registry.
2. Decide evidence authority: inventory/API, Metrics Source, Alert Source, correlated committed domains, or a qualified combination. Do not assume every integration uses Prometheus.
3. Define versioned metric semantics in the existing source adapter/query profile registry. Validate identity labels and retention; use canonical `MetricsConsumer` for instant/range queries in the worker.
4. Define each dataset's stable key, asset/instance scope, explicit canonical parameters, time range (if applicable), source binding requirements, freshness, stale grace, version and result shape. Use the owning domain's dataset catalog/builder patterns; do not add view-only filters to fingerprint parameters.
5. Register a job in `app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml`: dispatcher, domain permission, queue, default interval and configuration; use existing `dispatch_registered_job` and `enqueue_canonical_job` with registered-worker preflight and resource-group dedup. Prefer `analytics-batch`; `forecasting` only for qualified heavy forecasting.
6. Implement bounded worker-only collection with progress at meaningful stages, timeout and retry accounting, provider-specific failure classification, idempotent commit and source provenance. No unbounded high-cardinality or per-object JobExecution write loop.
7. Persist provider-neutral normalized committed evidence with source identity and observation timestamps. Distinguish `generated_at`, `expires_at`, `last_attempt_at` and a selected **metric history interval**. Preserve last usable evidence during failed refresh within approved grace.
8. Read committed snapshots from a fast page shell; lazy-load only requested sections. Compose `analytics/components/_controls_readiness.html` and `analytics/components/_section_load_tracker.html`. The latter counts HTMX section requests **only**, not worker percent; JobExecution progress uses `components/progress_bar.html::job_progress`.
9. Add tests for source capabilities/absence, time range correctness, scope matching, stale/missing/failed/partial evidence, dedup/permissions, page read-only boundary, shared UI regression, migration/rollback when storage changes, and light/dark/mobile Visual QA before human acceptance.

## Canonical state distinctions

**Metrics Source readiness** (validated required capabilities) differs from **worker source execution** (query success/failure), **snapshot readiness** (current/stale/expired/missing), and **page section loading** (requested/loaded/failed HTMX fragments). One layer cannot substitute for another.

- Transport/source unavailable: record blocked/degraded source evidence; never replace a previously usable snapshot with fabricated zero metrics.
- Missing snapshot and eligible source: dispatch one deduplicated registered job, render pending, poll only scoped JobExecution/committed state.
- Current snapshot: serve immediately even when a transient source health observation is degraded, with an explicit warning.
- Stale within grace: serve qualified stale evidence and dispatch bounded refresh.
- Expired or invalid: do not present as current. A failed refresh preserves prior evidence but not its freshness claim.
- Partial dataset failure: preserve per-source/per-dataset error/provenance, do not label whole coverage healthy.
- Forecast: keep heavy range history and model extrapolation separate from instant operational metrics.

## Time-range semantic contract

Allowed UI labels `1h, 6h, 12h, 24h, 7d, 30d, 60d` are display vocabulary only, already present in `app/common/analytics/params.py` and existing UI. The selected value becomes a **measured source interval** only after the worker executed a true qualified range query and committed that interval's dataset. Merely filtering the creation age of a single `current` snapshot is not historical analytics. Explicit legacy selectors may remain only when described as last-known snapshot selection. The source's retention/capabilities determine whether historical ranges are supported; never infer support from the dropdown.

## Worker and UI progress must stay separate

- `JobExecution.progress_current/total` count completed work items; `payload_json._progress` carries coarse stage/percent, used by shared job progress.
- `analytics/components/_section_load_tracker.html` + `js/analytics/section_load_tracker.js` count requested HTMX committed-evidence fragments. They must not claim a Celery worker percentage, must exclude unopened tabs, and must surface failed fragment loads.
- Form HTMX loading is an immediate UI request indicator; it is neither query validation nor worker progress.

## Change and admission control

This document codifies existing standards and identified gaps. It authorizes **no** new schema or scheduler by itself. Domain-specific implementation must have a scoped child issue, work branch, tests, documentation and exact worker/source evidence. Changes touching provider credentials, data retention, historical-series storage, permissions or deployment require human acceptance and the existing KAORI Developer Check, Full Admission, Visual QA and staging UAT before promotion.

