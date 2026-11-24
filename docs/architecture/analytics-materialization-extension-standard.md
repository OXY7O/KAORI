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
| History | range-based worker dataset | range-based operational and forecast worker datasets | bounded worker `query_range` datasets by selected interval (#1108; UAT pending) |
| UI progress | requested-HTMX section tracker; separate JobExecution | shared Controls/readiness and worker progress | shared section tracker and Controls/readiness |

The Registry historical-range implementation under [#1108](https://github.com/OXY7O/KAORI/issues/1108) now issues bounded `MetricsConsumer.query_range` worker requests for `1h` through `60d`, normalizes source intervals/retention/capability gaps, and persists separate `time_range` snapshots. The legacy `current` path keeps instant Metrics Source measurements. **Runtime verification remains required**: the source's effective retention, series coverage, worker timeout and visual UAT must be proven before human acceptance; an unavailable range is never synthesized from the age of an instant snapshot.

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
`get_allowed_time_ranges`; each Registry historical selection corresponds to a
separate measured worker dataset and source interval. The `current` bookmark
is explicitly instant Metrics Source evidence, not a historical range.

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

## Canonical five-domain progressive dependency contract (#5122)

This is the **cross-domain evidence interpretation contract**, not a claim that all
five Analytics workspaces are already implemented. Kubernetes, Object Storage,
Artifact Registry, Source Control, and Secrets & PKI must apply the same source
families while retaining domain-specific permissions, registered jobs, datasets,
and external-provider authority. Source Control and Secrets & PKI follow their
own scoped implementation workstreams (#5126 and #2594); do not turn this
standard into an implied feature-completion declaration.

### Independent source families, not a global readiness gate

| Source family | Qualifying evidence | Unknown / limited evidence | Consumer behavior |
| --- | --- | --- | --- |
| **1. Domain Integration** | Authorized asset or instance, eligible provider implementation, and committed domain Inventory/generation for data that needs Inventory | Not configured, inaccessible scope, unsupported provider capability, or not-yet-collected Inventory are distinct states | No provider: show canonical domain setup blocker. Authorized, qualified committed Inventory: show its factual subset even if Metrics/Alert sources are absent |
| **2. Metrics Source** | Qualified domain/source/instance binding, capability, measured window, and committed worker metrics provenance | Binding eligibility unknown without a verified source record; no worker snapshot is **Not Collected**, not necessarily **Not Bound**. Missing retention or series is Unavailable | Gate only metrics-dependent sections, never committed Inventory, security, governance, or provider-native evidence |
| **3. Alert Source** | Qualified alert integration and committed, scoped alert provenance; explicitly identify Alertmanager-primary versus supported bounded fallback | Missing, unqualified, partial, or stale alert evidence must not become a clean/zero-alert assertion | Gate alert-dependent sections; a Metrics Source fallback is narrower than a qualified Alert Source and must be labeled as such |

An Analytics **Snapshot is a materialization/output artifact**, never a fourth
external dependency. Its data eligibility, selected time range, materialization
status, freshness, completeness, permission scope and last failed attempt
are evaluated **separately** from all three source families. One source being
ready cannot make another source ready. An expired snapshot cannot claim
current coverage, and a source outage does not erase a separately qualified
last-known committed observation. Time-range labels are not measured
historical coverage until the worker committed qualified range evidence.

Present the three source states through existing shared
`analytics/components/_controls_readiness.html` Controls & Data Readiness;
keep the independent **Latest Analytics Data Snapshot** card and the existing
requested-HTMX section tracker. Do not add page-specific components, provider
calls on normal GET, or a new dependency registry. Any source state presented
without direct binding evidence must explicitly identify that it is derived
from committed selected-window worker evidence.

### Five-domain behavior and RC validation matrix

| Domain | Earlier or current constraint | Progressive target / implementation authority | Mandatory RC UAT cases |
| --- | --- | --- | --- |
| **Kubernetes** | Existing provider and Metrics Source controls already permit committed Inventory and domain Analytics interpretation independently | Preserve existing Kubernetes-specific readiness, scoped clusters/workloads, source freshness, and shared Controls; do not regress qualified operational data | No cluster; Inventory-only; Metrics absent; Alert absent; fresh/stale snapshot; inaccessible cluster; lazy HTMX |
| **Object Storage** | Prior Overview hard block after Inventory Sync when analytics metrics snapshot was absent; August Final Recheck is historical authority | #5124: retain Inventory Sync Required before committed Inventory; allow bounded **Limited Overview** from authorized committed Inventory without Metrics/Alert. Keep physical capacity, performance, forecast, and operational utilization unqualified | No Inventory; fully observed Inventory; partial size/count fields; missing/stale metrics; unauthorized system; seven time windows, desktop/mobile |
| **Artifact Registry** | A single provider prerequisite blocker could conceal independent source dependencies; generic Metrics queries assumed Harbor | #5123: three independent readiness stages without hiding Registry Inventory/Security/Runtime/Governance; #5125: provider-qualified metrics profile (Harbor first; other providers unknown/unsupported until qualified) | No provider; no snapshot; Harbor metrics-only; alert fallback; stale/partial; non-Harbor unsupported profile; cross-provider scoping |
| **Source Control** | Committed installation/repository/PR/review/CI evidence is not equivalent to Prometheus telemetry, and dedicated Analytics is not yet generally admitted | #5126 under #4027: preserve installation-scoped provider-native committed evidence without Metrics/Alert prerequisites; later Analytics sections require bounded, real datasets, not synthetic DORA metrics | No installation; selected-repository grant; missing Metrics/Alert; revoked grant; unauthorized repository; no fabricated delivery trends |
| **Secrets & PKI** | Provider-native metadata and limited Certificate Expiration evidence exist; full historical Analytics (#2594) is not complete | #2594 under #714: qualify Vault/other provider versions and Metrics Source query semantics per dataset; never expose secret values, paths, tokens, credentials or private keys in Analytics | Unauthorized instance; missing/partial telemetry; certificate expiry metadata only; stale evidence; response/log/export redaction and negative permissions |

**Acceptance matrix across every domain:** test absent provider, authorized
Inventory-only, partial source coverage, no materialization, current/stale/
expired snapshot, unsupported provider profile, RBAC denial, and independent
Metrics/Alert outages. Validate count denominators and missing data as
unknown rather than healthy zero. Include light/dark, desktop/mobile,
keyboard/accessibility, shared Hero/cards/table pagination (default five),
HTMX loading/error/empty states, and absence of synchronous provider calls.

### Admission and RC boundary

The above matrix is a **contract and test plan**, not a waiver of existing
domain-specific admission. Code delivery remains separated into #5123,
#5124, #5125, #5126 and #2594, with cross-domain authority #5122,
shared foundation #1105/#1122 and independent CI prerequisite #5131.
RC publication #5133 may include only changes merged to `kaori/staging`
after exact-head Developer Check and Full Admission; unfinished Source
Control or Secrets & PKI scope must remain clearly disclosed as a known
limitation. Signed RC publication, isolated staging deploy, live Visual QA,
security/RBAC negatives and actual human acceptance are separate evidence
gates; neither a contract document nor CI green implies successful UAT.

## Extension checklist for an additional domain

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

## Overlapping scope writer ownership (Object Storage #1392)

Canonical JobExecution deduplication uses request/parameter fingerprints. A fleet materialization request and a selected-system on-demand request can overlap on the **same** Object Storage `(system_id, time_range)` Analytics or `(system_id, history_window, method)` Forecast snapshot. Resource-group admission quotas are not sufficient to guarantee exclusive writes. The current Object Storage implementation therefore fences the **stable dataset key** using its existing snapshot-row `last_job_execution_id` and `last_attempt_at` (no schema addition): a worker claims ownership before provider collection, refuses an older JobExecution claim, and rechecks the exact job ID plus timestamp under a database row lock before committing either ready payload or failed attempt. A superseded worker cannot downgrade or overwrite a later claim, even across duplicate deliveries from one JobExecution.

Do not infer that this fence is automatically present in Kubernetes or Registry Analytics; those domains must audit and implement their own scoped isolation under separate child issues as appropriate. PostgreSQL concurrent write, worker-lost/retry, and crash/cancellation behavior still require runtime evidence before Human Acceptance; source contracts alone do not prove isolation.

## Time-range semantic contract

Allowed UI labels `1h, 6h, 12h, 24h, 7d, 30d, 60d` are display vocabulary only, already present in `app/common/analytics/params.py` and existing UI. The selected value becomes a **measured source interval** only after the worker executed a true qualified range query and committed that interval's dataset. Merely filtering the creation age of a single `current` snapshot is not historical analytics. Explicit legacy selectors may remain only when described as last-known snapshot selection. The source's retention/capabilities determine whether historical ranges are supported; never infer support from the dropdown.

## Worker and UI progress must stay separate

- `JobExecution.progress_current/total` count completed work items; `payload_json._progress` carries coarse stage/percent, used by shared job progress.
- `analytics/components/_section_load_tracker.html` + `js/analytics/section_load_tracker.js` count requested HTMX committed-evidence fragments. They must not claim a Celery worker percentage, must exclude unopened tabs, and must surface failed fragment loads.
- Form HTMX loading is an immediate UI request indicator; it is neither query validation nor worker progress.

## Change and admission control

This document codifies existing standards and identified gaps. It authorizes **no** new schema or scheduler by itself. Domain-specific implementation must have a scoped child issue, work branch, tests, documentation and exact worker/source evidence. Changes touching provider credentials, data retention, historical-series storage, permissions or deployment require human acceptance and the existing KAORI Developer Check, Full Admission, Visual QA and staging UAT before promotion.

