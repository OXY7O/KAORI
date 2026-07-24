# KAORI Pre-Inventory and Analytics Foundation Audit

**Audit date:** 2026-07-24  
**Source:** `X(1).zip`  
**Scope:** application code, tests, scripts, migrations, Celery topology, repository hygiene, folder structure, and reusable UI boundaries.

## Executive Verdict

KAORI is **ready to accept this hardening patch**, but it is **not yet approved for broad Inventory and Analytics feature expansion**.

The repository now has enforceable gates for the failure classes found during the audit: missing imported symbols, circular runtime imports, orphan modules, debug-test leakage, malformed Jinja, source ZIP contamination, and new inline UI debt. Functional characterization was added for the current Inventory and Analytics foundations.

Before broad feature implementation begins, two conditions remain mandatory:

1. Run the complete quality gate inside the KAORI Dev Container, where Flask, Celery, Ruff, djLint, Pyright, Node dependencies, PostgreSQL, and Redis are available.
2. Decompose the highest-risk Inventory and Analytics functions behind the new characterization tests instead of increasing their debt ceilings.

## Audit Results by Requirement

### 1. Tests must validate feature and logic behavior

Changes:

- Added one canonical marker hook in `tests/conftest.py`.
- Removed duplicate marker hooks from nested test folders.
- Kept temporary diagnostics exclusively under `tests/debug/` and excluded them from the release run.
- Added `scripts/verify_test_taxonomy.py`.
- Added `scripts/verify_feature_test_coverage.py`.
- Added functional characterization for:
  - Analytics Capacity;
  - Forecast;
  - Storage;
  - Top Consumers;
  - Utilization;
  - Workload;
  - Inventory quantity presentation;
  - Inventory topology selector and graph limiting.
- Added explicit release execution:

```bash
pytest -q tests/analytics tests/inventory tests/kubernetes -m functional
```

Current test estate:

| Bucket | Modules | Top-level tests |
| --- | ---: | ---: |
| Analytics | 9 | 48 |
| Inventory | 2 | 4 |
| Kubernetes inventory foundation | 5 | 8 |
| Contracts | 60 | 199 |
| Migrations | 1 | 4 |
| Entire repository | 122 | 414 |

Contracts remain supporting evidence. The new suites execute calculation, filtering, normalization, risk, forecast, presentation, and graph-limiting behavior rather than only checking static UI text.

### 2. Legacy code, shim, and wrapper cleanup

Removed dormant modules with no runtime, test, configuration, or script consumer:

```text
app/jobs/query_execution.py
app/jobs/query_planning.py
app/jobs/resource_limits.py
```

They represented a future Analytics worker foundation but were not used by any task. Their names are now retired by the architecture gate so they cannot silently return as unused placeholders.

Additional cleanup:

- Removed obsolete root `RUN.md` patch instructions.
- Replaced the patch-specific root README with a real KAORI project README.
- Moved six historical integration cutover documents from active architecture documentation to `docs/archive/integration-cutover/`.
- Removed an active RBAC compatibility fallback. Users without a persisted role now fail closed; the explicit super-admin flag remains the break-glass authority.
- Scanned non-package modules for import-only façade candidates; no remaining compatibility façade or wrapper module was found.
- Canonical compatibility modules under `app/integrations/*/compatibility.py` remain because they implement supported-provider lifecycle and API-version behavior; they are not migration shims.

### 3. Normal execution, warnings, formatter, and linter

The quality gate now requires:

```bash
python -m ruff check app migrations tests scripts
python -m ruff format --check app migrations tests scripts
python -m djlint app/templates --check
python -m pyright --project pyrightconfig.json
npm run check-format
```

Additional static gates detect:

- Python syntax without generating bytecode;
- missing internal modules;
- missing imported symbols;
- runtime circular imports;
- orphan application modules;
- malformed Jinja templates;
- test taxonomy drift;
- UI inline-debt growth.

Sandbox limitation: Ruff, djLint, Pyright, Flask, Celery, and installed frontend dependencies were not available from the execution environment. The full formatter/linter/type/runtime suite therefore must be executed in the Dev Container before the expansion verdict can become GO.

### 4. Foundation readiness

Verified in the audited source:

- 426 application modules are reachable.
- The runtime module graph is acyclic across 1,352 dependency edges.
- All internal imported modules and explicit top-level symbols resolve across 3,493 import statements.
- Celery topology is closed: 11 tasks, 11 explicit routes, and 6 consumed queues.
- Alembic has 83 revisions, one root, and one head: `20260723_resolver_readiness`.
- Source hygiene scans archives even when `.git` is absent.
- All 408 Jinja templates parse successfully.
- Aggregate `app.extensions` imports were removed from domain modules; only application bootstrap uses the aggregate package.
- The health blueprint cycle was removed by making `app.health.routes` own the blueprint.

### 5. File and folder structure

The overall domain layout is usable and aligned with the documented Flask/Jinja/HTMX architecture. The following improvements were made:

- one test taxonomy hook rather than one hook per folder;
- historical cutover documents moved out of active architecture guidance;
- application modules require a real importer or runtime/test consumer;
- extension objects are imported from their owning modules;
- reusable UI implementation lives under `app/templates/components/`;
- future query-planning modules must be introduced with the first real worker and behavior tests.

Residual structural debt remains significant:

| Module | Lines |
| --- | ---: |
| `app/intelligence/recommendation_engine.py` | 2,572 |
| `app/analytics/workload/service.py` | 2,456 |
| `app/analytics/top_consumers/service.py` | 2,185 |
| `app/analytics/forecast/service.py` | 2,119 |
| `app/analytics/overview/service.py` | 1,938 |
| `app/analytics/storage/service.py` | 1,592 |
| `app/analytics/utilization/service.py` | 1,275 |
| `app/analytics/capacity/service.py` | 1,234 |
| `app/inventory/routes.py` | 1,195 |
| `app/inventory/topology/service.py` | 1,109 |

Highest-risk functions:

| Function | Lines | Branch points | Arguments |
| --- | ---: | ---: | ---: |
| `build_topology_graph()` | 766 | 148 | 4 |
| `get_workload_analysis_context()` | 435 | 30 | 1 |
| `get_tenant_quota_summary()` | 373 | 14 | 2 |
| `build_workload_actionable_recommendations()` | 357 | 50 | 1 |
| `get_storage_capacity_summary()` | 340 | 19 | 13 |
| `get_workload_mapping_payload()` | 334 | 6 | 3 |
| `get_workloads()` | 317 | 60 | 3 |
| `get_pods()` | 251 | 80 | 3 |

The code-health gate prevents these values from increasing, but the baseline does not make them maintainable. New feature work should begin by extracting tested use cases from these locations.

### 6. Shared and consistent UI

A shared progress component now owns all dynamic width styling:

```text
app/templates/components/progress_bar.html
```

It provides regular and stacked progress bars. There are now 33 component calls across 26 templates.

Inline style reduction:

```text
Before audit: 56 template inline styles
After audit:   3 template inline styles
```

All three remaining styles are encapsulated in the shared progress component. Templates outside that component are prohibited from using `style=`.

The UI gate also:

- parses every Jinja template;
- rejects template-local `<style>` blocks;
- blocks new inline styles;
- prevents inline script and event-handler debt from increasing.

Remaining burn-down debt:

```text
28 inline script blocks
38 inline event handlers
```

These are bounded, but should be migrated incrementally to static JavaScript modules, Alpine behavior, or HTMX attributes when their owning pages are changed.

### 7. Unused scripts and repository artifacts

The uploaded ZIP contained 803 cache or compiled artifacts. The revised hygiene gate no longer skips validation when `.git` is unavailable and rejects:

- `__pycache__`;
- `.pyc` and `.pyo`;
- pytest, Ruff, and mypy caches;
- `node_modules`;
- local instance/runtime data;
- generated reports and temporary files;
- nested ZIP files.

Application reachability analysis found and removed the three dormant query-execution modules. Remaining operational scripts have concrete references from Compose, Dev Container setup, package scripts, quality gates, tests, or documentation.

## Remaining Debt and Entry Criteria

### P0 — Validation evidence required

Before starting broad feature work, run in the Dev Container:

```bash
bash scripts/quality_gate.sh --all
```

This must include a green full pytest run, Ruff lint and format checks, djLint, Pyright, frontend Prettier/build validation, PostgreSQL migration tests, and Redis/Celery integration tests.

### P1 — Inventory decomposition

Decompose `build_topology_graph()` behind the new characterization tests into:

- query/read-model extraction;
- node builders;
- edge builders;
- relationship policies;
- filtering and depth selection;
- graph limiting;
- presentation serialization.

Split `app/inventory/routes.py` by resource boundary or move request-independent logic into resource/application modules.

### P1 — Analytics decomposition

Do not add more responsibilities to the large service modules. First extract:

- input/selection contracts;
- provider query execution;
- normalization;
- calculation/assessment;
- recommendation assembly;
- presentation payload;
- persisted snapshot boundary for heavy queries.

### P1 — Existing architecture debt

The architecture ledger still contains:

- two top-level domain cycle envelopes;
- three service-to-WTForms dependencies;
- 198 broad exception handlers.

Runtime module cycles are now zero, but domain ownership still needs gradual correction. The debt ceilings may shrink, not expand.

### P2 — Frontend behavior debt

Migrate the remaining 28 inline scripts and 38 inline event handlers when their pages are next changed. Do not add new ones.

## Validation Completed in Sandbox

```text
Source archive hygiene: PASS — 1,367 files checked
Python in-memory syntax: PASS — 647 source files
Architecture boundaries: PASS — 2,815 imports
Internal import symbols: PASS — 3,493 imports
Runtime import cycles: PASS — 426 modules / 1,352 edges / 0 cycles
Module reachability: PASS — 426 modules
Celery topology: PASS — 11 tasks / 11 routes / 6 queues
Code-health ceiling: PASS — 426 modules / 2,692 functions
Migration graph: PASS — 83 revisions / 1 root / 1 head
Test taxonomy: PASS — 122 test modules
Feature characterization manifest: PASS — 14 required modules
Jinja and UI reuse: PASS — 408 templates / 3 shared inline styles
Selected pure contract tests: PASS — 28 tests
```

Not executable in the sandbox because the required packages or services were unavailable:

```text
Full Flask/Celery application pytest suite
Ruff lint and formatter
Pyright
DjLint command
Prettier and frontend build
PostgreSQL and Redis integration execution
Docker Compose runtime validation
```

## Final Decision

- **GO:** apply this foundation hardening patch.
- **GO:** run the complete Dev Container quality gate.
- **GO:** begin Inventory topology and Analytics decomposition using the new characterization suites.
- **NO-GO:** add broad Inventory or Analytics features before the full gate is green and the touched oversized module is decomposed rather than expanded.
