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

- [ ] Create `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py` with:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HTML_PDF = ROOT / "app" / "reports" / "export" / "html_pdf"


def test_capacity_refactor_uses_focused_local_package() -> None:
    expected = (
        "capacity/model.py",
        "capacity/charts.py",
        "capacity/forecast.py",
        "capacity/actions.py",
        "capacity/sections.py",
    )
    missing = [relative for relative in expected if not (HTML_PDF / relative).is_file()]
    assert not missing, f"missing Capacity ownership modules: {missing}"


def test_capacity_package_never_imports_facade() -> None:
    package = HTML_PDF / "capacity"
    assert package.is_dir()
    for path in package.glob("*.py"):
        source = path.read_text()
        assert "from app.reports.export.html_pdf.capacity_analysis" not in source
        assert "import app.reports.export.html_pdf.capacity_analysis" not in source


def test_capacity_facade_keeps_symbol() -> None:
    source = (HTML_PDF / "capacity_analysis.py").read_text()
    assert "def build_capacity_analysis_presentation(" in source
```

- [ ] Run `pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`; expected RED because package modules are absent.
- [ ] Commit only this test as `test(reports): lock capacity html pdf ownership`.

### Task 2: Model / Derived State

- [ ] Create all six `capacity/` package files so Task 1 can turn GREEN without import-broken intermediate commits.
- [ ] Move these exact existing helpers from `capacity_analysis.py` to `capacity/model.py`: `_mapping`, `_sequence`, `_float`, `_int`, `_ratio_percent`, `_percent`, `_optional_percent`, `_metric`, `_risk_metric`, `_capacity_resource`, `_quantity`, `_headroom_status`, `_allocation_resource` plus constants used only by them.
- [ ] Import the moved helpers from the facade; do not move forecast/action/section/SVG logic yet.
- [ ] Run:

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
ruff format --check app/reports/export/html_pdf/capacity_analysis.py app/reports/export/html_pdf/capacity tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
ruff check app/reports/export/html_pdf/capacity_analysis.py app/reports/export/html_pdf/capacity tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
```

- [ ] Commit `refactor(reports): extract capacity presentation model`.

### Task 3: Chart Ownership RED/GREEN

- [ ] Before production change, redirect the source-inspection in `test_capacity_analysis_forecast_has_no_svg_font_collision` to `app/reports/export/html_pdf/capacity/charts.py` while leaving rendered SVG/font assertions unchanged:

```python
source = (
    Path(__file__).resolve().parents[2]
    / "app" / "reports" / "export" / "html_pdf" / "capacity" / "charts.py"
).read_text()
assert "resolve_vertical_labels" in source
```

- [ ] Run that single test; expected RED.
- [ ] Move `_capacity_forecast_chart_svg`, `_empty_chart_svg`, `_participation_donut_svg`, `_RESOURCE_COLORS`, and their chart-only geometry/label logic to `capacity/charts.py`; import `resolve_vertical_labels` there.
- [ ] Run full Capacity PDF tests plus Ruff on changed files; expected GREEN.
- [ ] Commit `refactor(reports): extract capacity chart rendering`.

### Task 4: Forecast Preparation

- [ ] Before extraction, extend existing forecast characterization to assert current method/row order:

```python
assert document.presentation["forecast"]["available"] is True
assert document.presentation["forecast"]["method"] == "Holt-Winters"
assert tuple(row["resource"] for row in document.presentation["forecast"]["rows"]) == (
    "CPU", "Memory", "Pods"
)
```

- [ ] Run `pytest -q tests/reports/test_capacity_analysis_pdf_template.py -k forecast`; expected characterization GREEN.
- [ ] Move `_forecast_percent`, `_history_percent`, `_forecast_points_percent`, `_forecast_row`, `_projection_status`, `_projection_tone`, `_forecast_interpretation` to `capacity/forecast.py`.
- [ ] Add `build_forecast_section(forecast_payload: Mapping[str, Any], resources: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, float | None], dict[str, Any]]`; it returns projections plus the same template-facing forecast mapping and calls `capacity.charts` for SVG.
- [ ] Run full Capacity PDF tests; commit `refactor(reports): extract capacity forecast preparation`.

### Task 5: Actions / Evidence

- [ ] Use the current fixture to capture literal risk refs, recommendation refs/priorities, and source-row order before extraction; add those literal values to regression assertions rather than inventing expectations.
- [ ] Run the full Capacity test file and confirm characterization GREEN.
- [ ] Move `_executive_interpretation`, `_executive_findings`, `_risk_rows`, `_recommendation_rows`, `_priority_code`, `_owner_summary`, `_source_rows`, `_format_datetime`, `_latency`, `_risk_interpretation` to `capacity/actions.py`; preserve strings/order/refs/statuses.
- [ ] Run Capacity tests and Ruff; commit `refactor(reports): extract capacity action evidence`.

### Task 6: Section Builders RED/GREEN

- [ ] Add structural RED:

```python
def test_capacity_facade_delegates_section_assembly() -> None:
    source = (HTML_PDF / "capacity_analysis.py").read_text()
    assert "from app.reports.export.html_pdf.capacity.sections import" in source
    facade = source.split("def build_capacity_analysis_presentation(", 1)[1]
    assert "'executive': {" not in facade
    assert "'compute': {" not in facade
    assert "'scheduling': {" not in facade
    assert "'storage': {" not in facade
```

- [ ] Run only that test; expected RED.
- [ ] In `capacity/sections.py`, move the exact existing mapping blocks for `cover`, `executive`, `compute`, `scheduling`, `storage`, `risks`, `recommendations`, and methodology/evidence into focused builders. Each builder accepts one normalized state mapping plus at most one keyword-only metadata value; no function may exceed 8 arguments. Decision derivation remains in `actions.py`, forecast derivation remains in `forecast.py`, SVG remains in `charts.py`.
- [ ] The facade retains publication metadata/layout contract and calls those section builders; it no longer contains the major inline section dictionaries.
- [ ] Run structural contract + full Capacity PDF tests; commit `refactor(reports): reduce capacity presentation facade`.

### Task 7: Caller Audit / `ReportDocumentContext`

- [ ] Search every import/call of `build_capacity_analysis_presentation` and record exact supported callers in #36 evidence.
- [ ] If `builder.py` is the only supported caller, add RED:

```python
def test_capacity_builder_uses_report_document_context() -> None:
    source = (HTML_PDF / "builder.py").read_text()
    branch = source.split("elif report.report_type == 'capacity_analysis':", 1)[1].split("elif ", 1)[0]
    assert "context=context" in branch
    assert "report_id=context.report_id" not in branch
    assert "generated_by=context.generated_by_label" not in branch
```

- [ ] For builder-only ownership, change the call to:

```python
presentation = build_capacity_analysis_presentation(
    payload,
    context=context,
    classification=classification,
)
```

and the facade signature to:

```python
def build_capacity_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
```

Map metadata from the existing `ReportDocumentContext` fields. If caller audit proves another supported caller, keep a deliberate compatibility wrapper and leave only the required argument exception; never use variadic parameters to game the metric.
- [ ] Run structural + Capacity regression; commit `refactor(reports): use report context for capacity presentation` when migrated.

### Task 8: Exact Ledger

Current Capacity exceptions are module `1255`, function lines `475`, branch points `77`, arguments `11`.

- [ ] Run existing `scripts/verify_code_health.py` and baseline-integrity verification before editing baseline.
- [ ] Confirm every Capacity module <=800, function <=160, branch points <=30, arguments <=8 except a proven compatibility exception.
- [ ] Remove only scanner-proven stale Capacity entries from `docs/architecture/code-health-debt-baseline.json`; do not alter unrelated debt, defaults, or `broad_exception_limit`.
- [ ] Rerun code-health/baseline integrity; expected PASS.
- [ ] Commit `chore(reports): reconcile capacity code health debt`.

### Task 9: Admission / PR / Staging / UAT

- [ ] Require full branch CI PASS: Static/Architecture/Governance, Security/SAST/Dependencies, Functional/Integration, Frontend, Production Image/Container Security/Runtime/DAST, final Admission.
- [ ] Open/update governed Draft PR to `kaori/staging`; body follows Summary → Why/Scope/Changes → Evidence → UAT/Release impact → Reviewer checklist. Project/sidebar instructions stay chat-only.
- [ ] Review mapping equivalence, storage unavailable/available semantics, forecast SVG labels, context mapping, ledger diff, no catch-all abstraction, no fake source ownership.
- [ ] Move #36 to `Review` only after full branch Admission PASS.
- [ ] Merge reviewed PR with reviewed head SHA locked; no staging release tag.
- [ ] Require post-merge staging Admission PASS; move #36 to `UAT`.
- [ ] UAT checks: PDF opens, exactly nine pages, storage missing/available variants, forecast available/unavailable variants, no chart-label collision, readable methodology/evidence page.
- [ ] On explicit `UAT PASS #36`, set `Done`, close completed, update #35, then reassess #38 for `Ready`.
