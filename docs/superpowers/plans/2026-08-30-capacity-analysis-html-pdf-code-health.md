# Capacity Analysis HTML/PDF Code-Health Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Capacity Analysis HTML/PDF into focused Capacity-local ownership while preserving the accepted nine-page publication and retiring only scanner-proven Capacity debt.

**Architecture:** `capacity_analysis.py` remains the stable Capacity module/symbol boundary. Capacity-specific normalization, charts, forecast semantics, action/evidence derivation, and section assembly move into `capacity/`; the central Reports builder remains routing authority and may pass the existing `ReportDocumentContext` after caller audit proves that migration safe.

**Tech Stack:** Python, Flask Reports, Jinja2, WeasyPrint, pytest, Ruff, Pyright, KAORI code-health/architecture/release verifiers.

**Spec:** `docs/superpowers/specs/2026-08-30-capacity-analysis-html-pdf-code-health-design.md`

## Global Constraints

- Keep `app.reports.export.html_pdf.capacity_analysis.build_capacity_analysis_presentation` available.
- Keep exactly nine A4 pages and existing `reports/pdf/capacity_analysis.html` semantics.
- Missing storage stays explicit `Not Available`; never synthesize zero/healthy state.
- Preserve forecast, risk, recommendation, allocation, node, methodology, source, and chart semantics.
- No renderer/schema/visual redesign and no cross-family catch-all framework.
- Source-inspection tests follow actual ownership; no fake imports/comments.
- Code-health defaults remain `800 / 160 / 30 / 8`; broad-exception baseline does not increase.
- Baseline changes require fresh scanner evidence.
- Use existing KAORI verification only; no ad-hoc scripts.

## Files

Create:
- `app/reports/export/html_pdf/capacity/__init__.py`
- `app/reports/export/html_pdf/capacity/model.py`
- `app/reports/export/html_pdf/capacity/charts.py`
- `app/reports/export/html_pdf/capacity/forecast.py`
- `app/reports/export/html_pdf/capacity/actions.py`
- `app/reports/export/html_pdf/capacity/sections.py`
- `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`

Modify:
- `app/reports/export/html_pdf/capacity_analysis.py`
- `app/reports/export/html_pdf/builder.py` only if caller audit confirms builder-controlled signature migration
- `tests/reports/test_capacity_analysis_pdf_template.py`
- `docs/architecture/code-health-debt-baseline.json` only after scanner proof

---

### Task 1: Structural Ownership RED

- [x] Structural contract committed at `15a2771705f132a036bdd4717a7f6ee75d247caf`.
- [x] RED observed in KAORI CI #276: Static failed while `capacity/model.py` was absent on that SHA.

### Task 2: Model / Derived State

- [x] Capacity-local package boundary and normalization implementation prepared atomically.
- [ ] Verify structural GREEN + existing Capacity behavior + Ruff on branch head.
- [ ] Wire Capacity facade to local owners during the single facade rewrite in Task 6; delete duplicated dead helper bodies then so the connector does not repeatedly rewrite the 1,255-line source.

### Task 3: Chart Ownership RED/GREEN

- [ ] Redirect source-inspection to `capacity/charts.py`, observe RED, move chart rendering, run Capacity regression, commit.

### Task 4: Forecast Preparation

- [ ] Lock forecast method/row order, extract forecast functions, run Capacity regression, commit.

### Task 5: Actions / Evidence

- [ ] Capture literal action/evidence outputs, extract action/evidence logic, run Capacity regression, commit.

### Task 6: Section Builders RED/GREEN

- [ ] Add structural RED that facade delegates section assembly.
- [ ] Move existing `cover`, `executive`, `compute`, `scheduling`, `storage`, `risks`, `recommendations`, and methodology/evidence mapping blocks to focused builders in `capacity/sections.py`.
- [ ] During the same full-file facade rewrite, replace all model/chart/forecast/action helper calls with Capacity-local owners and remove duplicated helper bodies from `capacity_analysis.py`.
- [ ] Run structural contract + full Capacity PDF regression; commit facade reduction.

### Task 7: Caller Audit / `ReportDocumentContext`

- [ ] Search every supported caller/import of `build_capacity_analysis_presentation`.
- [ ] For builder-only ownership, add RED for `context=context`, migrate to existing `ReportDocumentContext`, run regression, commit.
- [ ] If another supported caller exists, retain explicit compatibility without variadic metric evasion.

### Task 8: Exact Ledger

Current Capacity exceptions are module `1255`, function lines `475`, branch points `77`, arguments `11`.

- [ ] Run existing code-health/baseline-integrity verification before editing baseline.
- [ ] Confirm all Capacity boundaries satisfy defaults or retain a proven compatibility exception.
- [ ] Remove only scanner-proven stale Capacity entries; preserve unrelated debt/defaults/broad-exception limit.
- [ ] Rerun verification and commit ledger reconciliation.

### Task 9: Admission / PR / Staging / UAT

- [ ] Require full branch KAORI CI Admission PASS.
- [ ] Open/update governed Draft PR to `kaori/staging`; Project/sidebar instructions remain chat-only.
- [ ] Review mapping equivalence, storage semantics, forecast SVG labels, context mapping, ledger diff, ownership boundaries.
- [ ] Move #36 to `Review` only after branch Admission PASS.
- [ ] Merge reviewed head to staging; require staging Admission PASS; move #36 to `UAT`.
- [ ] On explicit `UAT PASS #36`, set `Done`, close completed, update #35, reassess #38 for `Ready`.
