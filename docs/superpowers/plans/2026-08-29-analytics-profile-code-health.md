# Analytics Profile Code-Health Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `app/reports/export/xlsx/analytics_profiles.py` below KAORI's default code-health ceiling and retire its oversized/branch-heavy preparer debt without changing Analytics XLSX behavior or public imports.

**Architecture:** Keep `analytics_profiles.py` as a small compatibility facade. Move declarative profiles to `analytics_profile_catalog.py`, shared preparation primitives to `analytics_preparation/common.py`, and category-specific preparation into focused modules under `analytics_preparation/`. Category modules depend only on schema and common support; the facade imports the catalog and preparers and owns report-type dispatch.

**Tech Stack:** Python 3, Flask Reports domain, dataclass-style Analytics XLSX schema objects, pytest, Ruff, Pyright, existing KAORI architecture/code-health verifiers, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-26-kaori-analytics-xlsx-design.md`

## Execution State

- [x] Architectural design approved.
- [x] Focused implementation plan committed.
- [x] RED structural contract committed at `35ef601a2815e65b46308cba792b959035818e95`.
- [x] RED CI #213 / `33253816502`: exactly `1 failed, 2184 passed`, failing because `analytics_profile_catalog.py` did not yet exist; all preceding static/code-health gates passed.
- [ ] GREEN atomic profile/preparation split integrated and verified.
- [ ] Exact profile debt ledger reconciled.
- [ ] Final full KAORI Admission passed.

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

## Task Checklist

### Task 1 — RED ownership contract
- [x] Lock stable facade, catalog, and focused category module ownership.
- [x] Observe RED through KAORI CI.

### Task 2 — Profile catalog
- [ ] Extract profile construction, registry, report-type set, and catalog validation to `analytics_profile_catalog.py`.
- [ ] Preserve exact nine profile definitions and public re-export semantics.

### Task 3 — Shared preparation support
- [ ] Create import-light `analytics_preparation/__init__.py`.
- [ ] Extract only cross-category normalization/table/metric/unit helpers to `analytics_preparation/common.py`.

### Task 4 — Kubernetes category preparers
- [ ] Extract `overview.py`.
- [ ] Extract `resource_utilization.py`.
- [ ] Extract `capacity.py`.
- [ ] Extract `storage.py`.
- [ ] Extract `workload.py`.
- [ ] Extract `forecast.py`.
- [ ] Extract `top_consumers.py` with branch-heavy logic decomposed.
- [ ] Extract `alerts.py`.

### Task 5 — Object Storage preparation
- [ ] Extract `object_storage.py` with summary, consumer, forecast, alerts, chart, and readout stages bounded below default function ceilings.

### Task 6 — Stable facade
- [ ] Reduce `analytics_profiles.py` to explicit re-exports, profile lookup, preparer mapping, and dispatch.
- [ ] Preserve unsupported-type and context-mismatch fail-fast behavior.

### Task 7 — Exact debt ledger
- [ ] Confirm source compliance first.
- [ ] Remove exactly the resolved module/function/branch entries for Analytics profile debt.
- [ ] Keep default ceilings and broad-exception ledger unchanged.

### Task 8 — Integrated delivery
- [ ] Analytics XLSX regression suite PASS.
- [ ] Static/code-health/exact-baseline PASS.
- [ ] Security PASS.
- [ ] Functional & Integration PASS.
- [ ] Frontend/reproducibility PASS.
- [ ] Production Runtime/DAST PASS.
- [ ] Admission PASS.
- [ ] PR/Issue evidence synchronized without GitHub-UI fill instructions in body.
- [ ] Ready-for-review only after final-head Admission green.
