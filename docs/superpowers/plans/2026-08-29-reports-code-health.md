# Reports Code-Health Debt Burn-down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce active Reports code-health debt while preserving publication behavior and make KAORI test evidence concise and structured.

**Architecture:** Keep existing public report/export entrypoints stable and move internal responsibilities behind focused modules. Start with Analytics XLSX because it has the highest branch-heavy validator debt, then reduce the generic XLSX builder, and only continue into HTML/PDF builders when XLSX contracts are green. Test-result presentation is changed only in the existing quality-gate surface; test taxonomy and coverage gates stay untouched.

**Tech Stack:** Python 3, Flask Reports domain, openpyxl, pytest, Ruff, Pyright, existing KAORI verifier scripts, GitHub Actions.

**Spec:** GitHub issue #13 (`Burn down Reports code-health debt`).

## Global Constraints

- Base branch: `kaori/staging`.
- Work branch: `kaori/tech-13-reports-code-health`.
- Base SHA: `376542456fdd149b685e54ef954198c883dcbb4d`.
- Default code-health ceilings stay exactly: module `800`, function `160`, branch points `30`, arguments `8`.
- No threshold increases.
- No metric-only file shuffling.
- Keep `app.reports.export.xlsx` public imports/signatures stable.
- Preserve sheet names, cells, formulas, charts/series, navigation, metadata, formula protection, and validation failure semantics.
- Do not create new ad-hoc verification scripts; reuse existing KAORI quality gates.
- Human-facing test evidence uses concise `PASS — KAORI …` / `FAIL — KAORI …` presentation; raw logs remain diagnostic evidence.
- Existing test taxonomy, domain architecture, and coverage gates stay unchanged.

---

### Task 1: Characterize Analytics XLSX validation boundary

**Files:**
- Test: `tests/reports/test_analytics_xlsx_standard.py`
- Create after RED: `app/reports/export/xlsx/analytics_validation.py`
- Modify after RED: `app/reports/export/xlsx/analytics_builder.py`

**Interfaces:**
- Consumes: generated Analytics XLSX artifacts from `build_analytics_workbook(...)`.
- Produces: `validate_analytics_xlsx_artifact(output_path: Path) -> None` with the same public behavior as today.

- [ ] Add a failing architecture contract asserting validation ownership lives in `analytics_validation.py` and `analytics_builder.py` delegates to it.
- [ ] Trigger CI and verify RED is caused by the missing validation module/delegation, not syntax or fixture errors.
- [ ] Move workbook-structure, metadata, overview-navigation, and chart-specific validation into focused helpers in `analytics_validation.py`.
- [ ] Keep `analytics_builder.validate_analytics_xlsx_artifact` as a compatibility import/delegation surface.
- [ ] Run Analytics XLSX tests and code-health verifier; verify validator function debt is removed.
- [ ] Commit the green implementation.

### Task 2: Reduce Analytics profile module debt

**Files:**
- Test: `tests/reports/test_analytics_xlsx_standard.py`
- Create after RED: focused modules under `app/reports/export/xlsx/analytics_profiles/`
- Modify after RED: current Analytics profile registry/facade surface.

**Interfaces:**
- Consumes: canonical Analytics payload + `AnalyticsExportContext`.
- Produces: unchanged `ANALYTICS_WORKBOOK_PROFILES`, `ANALYTICS_XLSX_REPORT_TYPES`, `get_analytics_workbook_profile(...)`, and `prepare_analytics_workbook_data(...)` contracts.

- [ ] Add failing contract coverage for stable registry/public API with decomposed profile ownership.
- [ ] Verify RED.
- [ ] Extract preparation by report family while retaining a small compatibility facade.
- [ ] Keep all workbook profile names, metric specs, sheet names, visual types, and readouts behaviorally identical.
- [ ] Run Analytics XLSX tests and code-health verifier; lower/remove resolved profile debt entries only after evidence is green.
- [ ] Commit the green implementation.

### Task 3: Reduce generic XLSX builder debt

**Files:**
- Test: `tests/reports/test_inventory_xlsx_standard.py`
- Modify: `app/reports/export/xlsx/builder.py`
- Create only if cohesive responsibility requires it: focused existing-package XLSX helper modules.

**Interfaces:**
- Consumes: existing inventory workbook schema/profile data.
- Produces: unchanged inventory XLSX renderer and validator contracts.

- [ ] Add failing architecture/behavior contract for the extraction boundary.
- [ ] Verify RED.
- [ ] Extract metadata/validation stages without changing workbook output semantics.
- [ ] Run Inventory XLSX tests and code-health verifier; remove only resolved baseline entries.
- [ ] Commit the green implementation.

### Task 4: Normalize human-facing test evidence

**Files:**
- Test: existing contract test surface under `tests/contracts/`
- Modify: `scripts/quality_gate.sh`

**Interfaces:**
- Consumes: existing verifier/pytest commands and their exit statuses.
- Produces: concise phase/test evidence in terminal and GitHub Actions while preserving raw command output for diagnostics.

- [ ] Add a failing contract test that requires short pytest tracebacks and KAORI PASS/FAIL summaries from the existing quality gate.
- [ ] Verify RED.
- [ ] Update `quality_gate.sh` in place; do not introduce a new script.
- [ ] Use concise pytest traceback presentation and phase summaries; preserve command exit codes.
- [ ] When `GITHUB_STEP_SUMMARY` exists, append compact Markdown evidence without replacing raw logs.
- [ ] Run contract tests and the quality-gate phases.
- [ ] Commit the green implementation.

### Task 5: Reconcile exact code-health debt ledger

**Files:**
- Modify: `docs/architecture/code-health-debt-baseline.json`
- Test: existing `scripts/verify_code_health.py` and `scripts/verify_code_health_baseline_integrity.py`

**Interfaces:**
- Consumes: current scanner metrics after Tasks 1–4.
- Produces: exact current debt ledger with no stale/resolved entries and unchanged defaults.

- [ ] Run code-health validation before editing the baseline and record stale/resolved Reports entries.
- [ ] Lower or remove only entries demonstrated resolved by the refactor.
- [ ] Verify the exact debt ledger and baseline-integrity gate are green.
- [ ] Commit baseline reconciliation.

### Task 6: Integrated verification and delivery

**Files:**
- No new product files unless a real regression requires a fix.

**Interfaces:**
- Consumes: all prior commits.
- Produces: reviewable PR to `kaori/staging` with CI evidence.

- [ ] Run targeted Reports XLSX tests.
- [ ] Run Reports functional tests.
- [ ] Run Ruff format/check, Pyright, code-health, code-health baseline integrity, test taxonomy/domain architecture/coverage gates, and existing report verification scripts.
- [ ] Open PR with issue #13 metadata and exact changed-file/debt evidence.
- [ ] Require full KAORI CI Admission success.
- [ ] Review diff for behavior drift and unresolved review comments.
- [ ] Merge using expected-head SHA only after Admission is green.
- [ ] Verify `kaori/staging` contains the merge and update/close issue #13 with merge SHA and CI evidence.
