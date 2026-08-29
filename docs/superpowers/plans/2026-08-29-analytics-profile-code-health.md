# Analytics Profile Code-Health Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `app/reports/export/xlsx/analytics_profiles.py` below KAORI's default code-health ceiling and retire its oversized/branch-heavy preparer debt without changing Analytics XLSX behavior or public imports.

**Architecture:** Keep `analytics_profiles.py` as a small compatibility facade. Move declarative profiles to `analytics_profile_catalog.py`, shared preparation primitives to `analytics_preparation/common.py`, and category-specific preparation into focused modules under `analytics_preparation/`. Category modules depend only on schema and common support; the facade imports the catalog and preparers and owns report-type dispatch.

**Tech Stack:** Python 3, Flask Reports domain, dataclass-style Analytics XLSX schema objects, pytest, Ruff, Pyright, existing KAORI architecture/code-health verifiers, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-26-kaori-analytics-xlsx-design.md`

## Global Constraints

- Work item: GitHub Issue #13, delivered through draft PR #33.
- Base remains `kaori/staging@376542456fdd149b685e54ef954198c883dcbb4d` unless the PR base explicitly changes.
- Work branch: `kaori/tech-13-reports-code-health`.
- Existing public symbols remain import-compatible from `app.reports.export.xlsx.analytics_profiles`: `ANALYTICS_WORKBOOK_PROFILES`, `ANALYTICS_XLSX_REPORT_TYPES`, `get_analytics_workbook_profile`, `prepare_analytics_workbook_data`.
- `app/reports/export/xlsx/__init__.py` keeps its current lazy-renderer boundary and continues importing Analytics profile API from the facade.
- Preparer callable contract remains `(payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile) -> AnalyticsWorkbookData`.
- Preparation is deterministic and side-effect free: no provider calls, persistence reads, forecast calculation, recommendation synthesis, or silent source fallback.
- Preserve all current profile report types, titles, descriptions, metric specs, sheet names, primary visual types, table schemas, rows, readouts, chart data, units, and missing-evidence semantics.
- Default code-health ceilings remain exactly module `800`, function `160`, branch points `30`, arguments `8`.
- Newly created modules/functions must comply with default ceilings immediately; do not create a new catch-all debt module.
- Broad-exception count must not increase from the current exact ledger.
- Do not create custom verification scripts; use existing tests and verifiers.
- Debt ledger entries may only be removed after GREEN Static/code-health evidence on the corresponding source structure.

---

### Task 1: Lock facade, catalog, and package ownership with a RED contract

**Files:**
- Modify: `tests/contracts/reports/test_reports_code_health_refactor_contract.py`
- Create after RED: `app/reports/export/xlsx/analytics_profile_catalog.py`
- Create after RED: `app/reports/export/xlsx/analytics_preparation/__init__.py`

**Interfaces:**
- Consumes: current `analytics_profiles.py` facade API.
- Produces: structural contract requiring catalog ownership and category-preparation package boundaries.

- [ ] **Step 1: Add the failing structural contract**

Append a contract equivalent to:

```python
def test_analytics_profiles_is_a_stable_facade_over_focused_preparation_modules() -> None:
    facade = read('app/reports/export/xlsx/analytics_profiles.py')
    catalog = read('app/reports/export/xlsx/analytics_profile_catalog.py')

    assert 'from app.reports.export.xlsx.analytics_profile_catalog import (' in facade
    assert 'ANALYTICS_WORKBOOK_PROFILES' in facade
    assert 'ANALYTICS_XLSX_REPORT_TYPES' in facade
    assert 'def get_analytics_workbook_profile(' in facade
    assert 'def prepare_analytics_workbook_data(' in facade
    assert 'AnalyticsWorkbookProfile(' in catalog

    for module in (
        'overview',
        'resource_utilization',
        'capacity',
        'storage',
        'workload',
        'forecast',
        'top_consumers',
        'alerts',
        'object_storage',
    ):
        source = read(f'app/reports/export/xlsx/analytics_preparation/{module}.py')
        assert 'def prepare_' in source
```

- [ ] **Step 2: Trigger CI and verify RED**

Expected failure: missing `analytics_profile_catalog.py` and/or `analytics_preparation/*` ownership; preceding architecture/code-health gates should remain unchanged.

- [ ] **Step 3: Commit RED evidence**

Commit only the contract test with a message such as `test(reports): lock analytics profile preparation boundaries`.

### Task 2: Extract the declarative Analytics profile catalog

**Files:**
- Create: `app/reports/export/xlsx/analytics_profile_catalog.py`
- Modify: `app/reports/export/xlsx/analytics_profiles.py`
- Test: `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- Produces: `ANALYTICS_WORKBOOK_PROFILES: dict[str, AnalyticsWorkbookProfile]`, `ANALYTICS_XLSX_REPORT_TYPES: frozenset[str]`, and catalog validation executed at import time.
- Facade re-exports the two constants without changing object semantics.

- [ ] **Step 1: Move profile-construction helpers and definitions**

Move `_metric`, `_column`, the full nine-profile `ANALYTICS_WORKBOOK_PROFILES` mapping, `ANALYTICS_XLSX_REPORT_TYPES`, and `_validate_profiles()` into `analytics_profile_catalog.py`.

- [ ] **Step 2: Re-export catalog values from the facade**

Use explicit imports in `analytics_profiles.py`; do not duplicate the registry or recompute a divergent report-type set.

- [ ] **Step 3: Verify public profile behavior**

Run the existing profile contract:

`pytest -q tests/reports/test_analytics_xlsx_standard.py::test_analytics_xlsx_profiles_cover_every_published_analytics_category --tb=short`

Expected: PASS with the exact same nine report types and profile metadata.

- [ ] **Step 4: Run architecture/import checks through CI**

The catalog must not import any preparer, builder, renderer, or facade.

- [ ] **Step 5: Commit the catalog extraction**

Commit message: `refactor(reports): extract analytics profile catalog`.

### Task 3: Extract shared preparation primitives without creating a catch-all

**Files:**
- Create: `app/reports/export/xlsx/analytics_preparation/__init__.py`
- Create: `app/reports/export/xlsx/analytics_preparation/common.py`
- Modify: `app/reports/export/xlsx/analytics_profiles.py`
- Test: `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- `common.py` may own only helpers used by at least two categories, including mapping/sequence/number/text normalization, first-value lookup, shared metric/table construction, shared recommendation rows, and shared column specifications where usage is genuinely cross-category.
- Category-specific resource-unit rules remain outside common support.

- [ ] **Step 1: Extract reusable normalization primitives**

Move the semantics of `_mapping`, `_sequence`, `_number`, `_int`, `_text`, `_first`, `_percent_from_resource`, `_metric_value`, `_table`, and genuinely shared column/recommendation helpers to `common.py` with stable typed signatures.

- [ ] **Step 2: Keep package `__init__.py` minimal**

Do not eagerly import every preparer from `analytics_preparation/__init__.py`; it should remain package documentation/type-neutral unless a proven import contract requires otherwise.

- [ ] **Step 3: Verify representative preparation behavior**

Run:

`pytest -q tests/reports/test_analytics_xlsx_standard.py -k 'resource_utilization_preparation or alerts_preparation or object_storage_preparation' --tb=short`

Expected: PASS.

- [ ] **Step 4: Commit**

Commit message: `refactor(reports): extract analytics preparation support`.

### Task 4: Extract Kubernetes category preparers

**Files:**
- Create: `app/reports/export/xlsx/analytics_preparation/overview.py`
- Create: `app/reports/export/xlsx/analytics_preparation/resource_utilization.py`
- Create: `app/reports/export/xlsx/analytics_preparation/capacity.py`
- Create: `app/reports/export/xlsx/analytics_preparation/storage.py`
- Create: `app/reports/export/xlsx/analytics_preparation/workload.py`
- Create: `app/reports/export/xlsx/analytics_preparation/forecast.py`
- Create: `app/reports/export/xlsx/analytics_preparation/top_consumers.py`
- Create: `app/reports/export/xlsx/analytics_preparation/alerts.py`
- Modify: `app/reports/export/xlsx/analytics_profiles.py`
- Test: `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- Each module exports one public internal preparer named for its report type: `prepare_overview`, `prepare_resource_utilization`, `prepare_capacity`, `prepare_storage`, `prepare_workload`, `prepare_forecast`, `prepare_top_consumers`, `prepare_alerts`.
- Each accepts exactly `(payload, context, profile)` and returns `AnalyticsWorkbookData`.

- [ ] **Step 1: Extract Overview preparation**

Move `_prepare_overview` plus only Overview-specific helpers into `overview.py`. Preserve Current-vs-Projected posture semantics, forecast evidence handling, alerts snapshot usage, readout text, and empty-forecast behavior.

Run:

`pytest -q tests/reports/test_analytics_xlsx_standard.py -k 'analytics_overview' --tb=short`

- [ ] **Step 2: Extract Resource Utilization preparation**

Move its preparation and category-only trend/consumer helpers into `resource_utilization.py`.

Run the Resource Utilization tests in `test_analytics_xlsx_standard.py`.

- [ ] **Step 3: Extract Capacity, Storage, Workload, and Forecast preparers one module at a time**

After each extraction run the matching Analytics XLSX tests and commit only when the category is behaviorally green.

- [ ] **Step 4: Extract Top Consumers preparation**

Move `_prepare_top_consumers` and resource-specific ranking/unit normalization to `top_consumers.py`. Decompose internal selection/normalization helpers so no function exceeds 30 branch points.

Run all tests whose names contain `top_consumers`, `ranked`, or consumer-unit normalization.

- [ ] **Step 5: Extract Alerts preparation**

Move Alerts & Anomalies preparation and severity/composition-specific helpers to `alerts.py`; preserve Unclassified denominator behavior.

Run:

`pytest -q tests/reports/test_analytics_xlsx_standard.py -k 'alerts' --tb=short`

- [ ] **Step 6: Commit the Kubernetes preparer extraction**

Use cohesive commits if CI attribution benefits from category checkpoints; do not combine a failing category with unrelated modules.

### Task 5: Extract Object Storage Analytics preparation

**Files:**
- Create: `app/reports/export/xlsx/analytics_preparation/object_storage.py`
- Modify: `app/reports/export/xlsx/analytics_profiles.py`
- Test: `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- Produces: `prepare_object_storage(payload, context, profile) -> AnalyticsWorkbookData`.
- Owns Object Storage-specific capacity/usage parsing, consumer ranking, storage-unit normalization, performance/trend/alert evidence mapping.

- [ ] **Step 1: Extract `_prepare_object_storage` and its domain-only helpers**

Do not move provider/storage-specific normalization into `common.py` unless another category demonstrably uses the exact same semantic rule.

- [ ] **Step 2: Split the current 182-line function into focused helper stages**

Use helpers for summary metrics, analysis rows, consumer rows/chart, optional trends/alerts, and final `AnalyticsWorkbookData` assembly so each function remains <=160 lines and <=30 branch points.

- [ ] **Step 3: Verify Object Storage behavior**

Run:

`pytest -q tests/reports/test_analytics_xlsx_standard.py -k 'object_storage' --tb=short`

Expected: ranked consumer chart remains `ranked_bar`; first `thanos` example remains normalized to `64.25`; table ownership and scope semantics remain unchanged.

- [ ] **Step 4: Commit**

Commit message: `refactor(reports): extract object storage analytics preparation`.

### Task 6: Reduce the facade to lookup and dispatch only

**Files:**
- Modify: `app/reports/export/xlsx/analytics_profiles.py`
- Test: `tests/contracts/reports/test_reports_code_health_refactor_contract.py`
- Test: `tests/reports/test_analytics_xlsx_standard.py`

**Interfaces:**
- Facade owns `_Preparer`, `_PREPARERS`, `get_analytics_workbook_profile`, and `prepare_analytics_workbook_data` plus explicit imports/re-exports.
- `_PREPARERS` maps the exact nine report-type keys to focused preparers.

- [ ] **Step 1: Replace old in-file preparers with explicit imports**

The facade must not contain `_column`, `_table`, `_number`, chart-model construction, row construction, or domain-specific preparation functions.

- [ ] **Step 2: Preserve fail-fast behavior**

`get_analytics_workbook_profile()` continues raising bounded `ValueError` for unsupported types; `prepare_analytics_workbook_data()` continues rejecting `context.report_type != report_type` before dispatch.

- [ ] **Step 3: Verify all Analytics preparation and workbook tests**

Run:

`pytest -q tests/reports/test_analytics_xlsx_standard.py --tb=short`

Expected: all tests PASS.

- [ ] **Step 4: Verify public/lazy XLSX boundary**

Run existing report runtime import and tabular verifier gates through Static CI. `app/reports/export/xlsx/__init__.py` remains unchanged unless a failing existing contract proves otherwise.

### Task 7: Reconcile exact profile debt ledger

**Files:**
- Modify: `docs/architecture/code-health-debt-baseline.json`

**Interfaces:**
- Removes only debt proven absent by the refactor.

- [ ] **Step 1: Run code-health before editing the ledger**

Require `scripts/verify_code_health.py` to identify stale entries for:

- `app/reports/export/xlsx/analytics_profiles.py` module size `1766`;
- `app/reports/export/xlsx/analytics_profiles.py::_prepare_object_storage` function lines `182`;
- `app/reports/export/xlsx/analytics_profiles.py::_prepare_overview` function lines `183`;
- `app/reports/export/xlsx/analytics_profiles.py::_prepare_top_consumers` branch points `31`.

- [ ] **Step 2: Remove exactly those entries only when current source is compliant**

Do not touch unrelated HTML/PDF or Reports service debt.

- [ ] **Step 3: Verify exact ledger integrity**

Require both `verify_code_health.py` and `verify_code_health_baseline_integrity.py` PASS with defaults unchanged and broad-exception count not increased.

- [ ] **Step 4: Commit**

Commit message: `chore(quality): retire analytics profile debt`.

### Task 8: Integrated review, full Admission, and metadata evidence

**Files:**
- Update evidence only: GitHub Issue #13 and PR #33 bodies after proof exists.
- No new implementation files unless a real regression requires a fix.

**Interfaces:**
- Produces: review-ready PR with exact CI/debt evidence; no release or `main` promotion.

- [ ] **Step 1: Run/observe final Static Foundation on final head**

Require Ruff, Ruff format, djLint, Pyright, architecture boundaries, import symbols/cycles/reachability, code-health, exact baseline integrity, taxonomy/domain architecture/coverage, and contract/migration tests PASS.

- [ ] **Step 2: Require downstream branch/PR gates**

Require Security, Functional & Integration, Frontend/reproducibility, Production Runtime/DAST, and Admission to complete without unexplained failure or unexpected skip.

- [ ] **Step 3: Review PR diff**

Confirm no public report type, profile metadata, workbook contract, test taxonomy, threshold, broad exception, schema, migration, or security-boundary drift.

- [ ] **Step 4: Synchronize Issue #13 and PR #33 evidence**

Update only metadata records/current implementation/CI evidence; do not place sidebar/Project fill instructions in Issue or PR body.

- [ ] **Step 5: Move PR out of Draft only after full final-head Admission is green**

Merge to `kaori/staging` only after normal review/merge guard conditions are satisfied. Then require staging CI and applicable Local UAT before Issue #13 can become `Done`.
