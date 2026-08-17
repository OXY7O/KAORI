# KAORI Foundation Hardening Audit — 24 July 2026

## Decision

**Status: NO-GO for large Inventory and Analytics feature expansion.**

The repository is materially safer than the submitted archive after this hardening slice, but the current Inventory and Analytics implementation is not yet a stable foundation for substantial new behavior. The remaining risk is no longer dominated by legacy import paths or migration graph integrity; it is dominated by oversized orchestration units, duplicated live-query composition, missing domain behavior characterization, and one unresolved durable Resolver redelivery boundary.

Small corrective work and the controlled decomposition batches below are safe to continue. New Inventory/Analytics features should wait until the mandatory exit criteria in this document are met.

## Scope and evidence

The review covered:

- Python import and application-factory initialization order;
- Celery task discovery, task routes, production worker queues, Beat ownership, and canonical JobExecution task arguments;
- Alembic graph integrity;
- dead modules, compatibility façades, wrappers, re-export shims, and obsolete query modules;
- module/function size, branch density, argument count, and broad exception debt;
- Inventory collection, persistence, current-generation reads, routes, and topology composition;
- Analytics provider access, normalization, page context, reports, and recommendation consumers;
- production environment configuration and Compose worker topology;
- contract, migration, and available pure behavior tests;
- source archive hygiene.

Static evidence after the patch:

- 428 application Python modules and 2,705 functions scanned by the code-health gate;
- 11 Celery tasks, 11 explicit routes, and 6 production-consumed queues verified as closed topology;
- 83 Alembic revisions with one root and one head (`20260723_resolver_readiness`);
- 2,823 application import records validated against architecture boundaries;
- 198 broad exception handlers remain explicitly bounded as burn-down debt;
- submitted archive contained 1,274 `__pycache__/*.pyc` artifacts.

## Critical defects corrected in this slice

### 1. Resolver was not production-routable

Resolver tasks existed in source but were absent from Celery startup imports, task routes, Beat recovery scheduling, and production worker services. The task could therefore appear complete in code while remaining unregistered or unconsumed in production.

Corrected by:

- registering `app.intelligence.resolver.tasks` in Celery imports;
- adding explicit routes for execution and lease reconciliation;
- adding dedicated execution and maintenance workers;
- adding Beat lease recovery;
- exposing and validating queue, worker, action, namespace, maintenance, and signing-key configuration.

### 2. Canonical dispatcher/task argument mismatch

`enqueue_canonical_job()` injects `job_execution_id` into every dispatched task. Resolver execution did not accept the argument, which would have caused an immediate unexpected-keyword failure before any resolver code ran.

Corrected by:

- accepting `job_execution_id` in Resolver execution;
- integrating `JobExecutionContext` start, progress, retry, success, and failure lifecycle;
- adding contract coverage for the injected argument and lifecycle calls.

### 3. Resolver held a database lock across provider execution

The execution lease was flushed but not committed before the external Resolver action. This kept the row lock and running state inside an open transaction while provider I/O executed, preventing reliable visibility and recovery.

Corrected by committing lease ownership before provider dispatch and verifying the ordering in the contract gate.

### 4. Resolver dispatch failure could orphan a queued journal

Canonical job admission commits before broker publication. If publication failed, the Resolver journal could remain `queued` without a usable job reference and could not be safely enqueued again.

Corrected by restoring the journal to a retryable pre-delivery state, clearing task/job references, and persisting `dispatch_failed` evidence.

### 5. Resolver secret material crossed the broker boundary

The signing key was previously passed with the one-time authorization token in task kwargs. Broker payload exposure would therefore reveal both token and validation secret.

Corrected by keeping the signing key process-local and loading it from worker configuration. The broker payload now carries the one-time token but not the signing key.

### 6. Application initialization imported domain graphs too early

The application factory imported blueprint and presentation dependency graphs before configuration and extension initialization. A domain import failure could break application startup before the actual bootstrap stage was visible.

Corrected by introducing explicit bootstrap owners and delaying presentation, blueprint, command, and Resolver integration imports until their required initialization stage.

### 7. Idle production workers created false operational readiness

Analytics and forecasting worker services consumed queues that had no registered tasks or routes. They spent production resources while suggesting asynchronous Analytics/Forecasting support that did not exist.

Corrected by removing the idle worker services. Queue names remain reserved contracts and workers must be added in the same change that adds concrete tasks and explicit routes.

### 8. Legacy and unused modules remained after cutover

Twenty-seven unused or compatibility-only Python modules were removed, including:

- Alerts aggregate service/query façades;
- Analytics query re-export modules;
- Kubernetes integration wrappers;
- Prometheus and Alertmanager schemas/query/validation re-exports;
- duplicate runtime dispatcher;
- obsolete report storage base, user lifecycle, formatter, binding-contract, and deprecation modules.

The architecture verifier now rejects both re-creation and imports of retired paths.

### 9. Identical Analytics coercion helpers were copied across services

Identical `_as_dict`, `_as_list`, `_safe_float`, and `_safe_int` implementations existed in multiple large Analytics services.

Corrected by moving the canonical pure behavior to `app/analytics/common/coercion.py`, replacing duplicated definitions, and adding behavior tests.

### 10. Maintainability debt had no growth control

Large modules, long functions, high branch density, high-arity functions, and broad exceptions were visible but not release-gated.

Corrected by adding a code-health debt ceiling. Existing debt is documented, but any new debt or growth now fails the static quality gate. Reducing a hotspot below the default limit also forces removal of its stale baseline entry.

## Remaining blockers before Inventory/Analytics expansion

### P0 — Durable Resolver redelivery is incomplete

Celery `acks_late` and `reject_on_worker_lost` provide native broker redelivery for a lost worker. Lease recovery also moves abandoned journals to `retry_wait`. However, KAORI cannot reconstruct the raw one-time token from the database if the broker message is permanently lost after admission. The former unused `due_retry_journals()` scaffold was removed rather than presenting false recovery.

Required resolution: define one explicit ownership model before enabling production Resolver actions:

1. rely on broker redelivery and prove it with worker-loss integration evidence plus broker visibility/retention configuration; or
2. persist an encrypted, expiring execution envelope that a maintenance task can safely re-enqueue.

Do not store a plaintext token or signing key in the journal.

### P0 — Full runtime gate was not executable in this sandbox

The supplied archive did not include an installed KAORI runtime environment. Flask, Celery, Redis client, Flask-SQLAlchemy, Flask-WTF, Kubernetes client, Prometheus client, and Ruff were unavailable. Dependency installation was also unavailable from the configured package index.

Therefore this audit proves source compilation, static contracts, migration shape, architecture topology, and pure helper behavior, but it does **not** prove application startup, PostgreSQL transaction behavior, Redis/Celery delivery, provider calls, HTMX behavior, or full frontend build.

The full Dev Container/CI gate remains mandatory before merge.

### P1 — Inventory topology is an unsafe extension point

Current Inventory size:

- 28 modules;
- approximately 8,167 lines;
- `app/inventory/routes.py`: 1,195 lines;
- `app/kubernetes/inventory/topology/service.py`: 1,109 lines;
- `build_topology_graph()`: 766 lines and approximately 148 branch points;
- `get_workloads()`: 317 lines;
- `get_pods()`: 251 lines.

There is no behavior test for topology graph construction, relationship direction, missing-parent handling, or hierarchy/dependency mode. Adding more resource kinds directly to this function will increase regression risk sharply.

Required decomposition:

```text
app/kubernetes/inventory/topology/
├── application.py       # request/use-case orchestration
├── index.py             # canonical resource and relation indexes
├── hierarchy.py         # hierarchy-mode graph builder
├── dependency.py        # dependency-mode graph builder
├── nodes.py             # element factories by resource type
├── edges.py             # relation factories and deduplication
├── contracts.py         # graph/node/edge contracts
└── presentation.py      # UI payload only
```

Routes must be split by resource family and call application services; they must not accumulate query, pagination, permission, and presentation logic in one 1,000-line module.

### P1 — Analytics remains a collection of giant live-query services

Current Analytics size:

- 44 modules plus the new shared coercion module;
- approximately 21,000 lines;
- 32 broad exception handlers;
- only Alerts has behavior characterization tests.

Largest services:

| Module | Lines |
|---|---:|
| `analytics/kubernetes/workload/service.py` | 2,505 before helper consolidation |
| `analytics/kubernetes/top_consumers/service.py` | 2,218 before helper consolidation |
| `analytics/kubernetes/forecast/service.py` | 2,171 before helper consolidation |
| `analytics/kubernetes/overview/service.py` | 1,943 before helper consolidation |
| `analytics/kubernetes/storage/service.py` | 1,644 before helper consolidation |
| `analytics/kubernetes/utilization/service.py` | 1,275 |
| `analytics/kubernetes/capacity/service.py` | 1,245 before helper consolidation |

High-risk functions include:

- `get_workload_analysis_context()` — 435 lines;
- `get_tenant_quota_summary()` — 373 lines;
- `get_storage_capacity_summary()` — 340 lines and 13 arguments;
- `get_workload_mapping_payload()` — 334 lines;
- Analytics Utilization route handler — 270 lines.

Each domain should be decomposed behind a stable snapshot contract:

```text
provider query plan
    → provider execution
    → normalized observations
    → domain aggregation
    → canonical snapshot
    → page/report/intelligence presenters
```

No new page feature should query Prometheus directly from a route or construct a second report-specific calculation path.

### P1 — Reports duplicate Analytics composition

Report sections instantiate Analytics services and Prometheus services directly. This couples reporting to live provider access and lets interactive pages and exported reports diverge.

Required resolution: complete canonical Analytics snapshots first, then make pages, reports, Intelligence, schedules, and future automation consume the same stored/versioned snapshot contract.

### P1 — Behavior coverage is insufficient

Existing behavior coverage is concentrated in Alerts and Inventory generation/persistence boundaries. There are no behavior tests for:

- Inventory topology;
- Capacity;
- Forecast;
- Storage Analytics;
- Top Consumers;
- Utilization;
- Workload Analytics;
- Analytics Overview composition.

Before each service split, add controlled provider fakes and characterize:

- selected-cluster and all-cluster boundaries;
- missing/disabled/unready provider behavior;
- query errors and partial evidence;
- empty result behavior;
- malformed metric payloads;
- unit conversions and rounding;
- pagination/filter consistency;
- current-generation consistency;
- report/page snapshot equivalence.

### P1 — Two dependency-cycle envelopes remain

The architecture gate currently allows but freezes two cycles:

1. `auth ↔ common ↔ extensions ↔ models ↔ notifications ↔ rbac`;
2. `alertmanager ↔ cluster ↔ integrations ↔ inventory ↔ prometheus`.

No new domain may join these envelopes. The second cycle directly affects Inventory and provider ownership and should be reduced before broad Analytics expansion.

Priority edges to remove:

- `integrations → alertmanager` presentation dependency;
- `integrations → inventory` synchronization dependency;
- `inventory → integrations` compatibility dependency;
- `cluster → prometheus/alertmanager` provider repository/resolver dependency;
- provider services importing WTForms.

### P2 — Broad exception debt remains high

There are 198 `except Exception`/bare-except handlers. Some are correct process/provider boundaries, but many large services convert all failures to empty values, which can hide programming errors as “no data.”

Burn-down rule:

- catch provider/network/database exceptions at explicit boundaries;
- let programming errors fail tests and error monitoring;
- preserve provider error codes and evidence;
- do not add to the 198-handler ceiling.

### P2 — Source archive process was bypassed

The submitted ZIP contained 1,274 bytecode/cache files. The repository already has a Git-based source archive script that excludes generated artifacts, but the supplied archive was not produced through that path.

Release and review archives must use `scripts/build_source_archive.sh` from a clean Git checkout. Manual directory ZIP creation is not an accepted release path.

## Mandatory work sequence

### Batch A — Characterization safety net

1. Add topology graph behavior tests.
2. Add one controlled-provider behavior suite for each Analytics domain.
3. Add report/page snapshot equivalence tests.
4. Run tests against PostgreSQL, Redis, Celery workers, and representative provider fakes.

### Batch B — Inventory decomposition

1. Split `build_topology_graph()` by graph mode and resource relation.
2. Split Inventory routes by resource family.
3. Keep current-generation filtering in one canonical read boundary.
4. Add graph contracts and deterministic ordering.

### Batch C — Canonical Analytics snapshots

1. Define versioned snapshot contracts per domain.
2. Separate query planning/execution from aggregation.
3. Move live queries to worker-owned application use cases.
4. Add cache/materialization ownership and freshness metadata.
5. Switch pages, reports, and Intelligence to the same snapshots.

### Batch D — Dependency direction cleanup

1. Remove service-to-WTForms dependencies.
2. Move provider presentation adapters out of canonical integration services.
3. Shrink the provider/cluster/inventory cycle.
4. Reduce broad exception handlers while preserving explicit provider diagnostics.

### Batch E — Production proof

1. Run `bash scripts/quality_gate.sh --all` in the Dev Container/CI.
2. Validate application startup for development, testing, and production config.
3. Validate Alembic upgrade from supported existing states and fresh bootstrap.
4. Run Redis/Celery task registration and queue-consumption smoke tests.
5. Run worker-loss, retry, stale lease, and broker restart tests.
6. Build and start `compose.production.yml`; verify readiness and worker health.

## GO criteria

Inventory/Analytics expansion becomes **GO** only when all conditions below are true:

- full static, runtime, frontend, and migration gates pass in Dev Container/CI;
- every Analytics domain has behavior characterization;
- Inventory topology has deterministic graph behavior tests;
- `build_topology_graph()` is below 160 lines or is replaced by focused builders each below that threshold;
- no Inventory/Analytics module exceeds 800 lines without an approved temporary debt entry and concrete exit issue;
- no new broad exception, architecture-cycle, service-to-form, idle-worker, or compatibility-path debt is introduced;
- pages and reports consume canonical snapshots rather than independent live-query composition;
- Resolver production enablement has proven durable redelivery ownership.

## Validation completed in this environment

Passed:

```text
python -m compileall -q app migrations tests scripts
python scripts/verify_architecture_boundaries.py
python scripts/verify_celery_topology.py
python scripts/verify_code_health.py
python scripts/verify_migration_graph.py
pytest -q tests/contracts tests/migrations -m 'contract or migration'
pytest -q tests/analytics/test_common_coercion.py
```

Not executable here:

```text
python -m ruff check app migrations tests scripts
pytest -q -m 'not debug'
npm ci && npm run build-frontend && npm run verify-frontend
application/Celery/Redis/PostgreSQL/provider integration smoke tests
```
