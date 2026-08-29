# Capacity Analysis HTML/PDF Code-Health Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Capacity Analysis HTML/PDF presentation ownership into a Capacity-local package while preserving the accepted nine-page publication contract and retiring only scanner-proven Capacity code-health debt.

**Architecture:** Keep `app/reports/export/html_pdf/capacity_analysis.py` as the stable Capacity module/symbol boundary and move cohesive responsibilities into `capacity/model.py`, `capacity/charts.py`, `capacity/forecast.py`, `capacity/actions.py`, and `capacity/sections.py`. The central builder remains the report-routing authority; after caller audit, Capacity uses the existing `ReportDocumentContext` pattern if `builder.py` is the only supported caller.

**Tech Stack:** Python 3, Flask Reports domain, Jinja2, WeasyPrint, pytest, Ruff, Pyright, KAORI code-health/architecture/release verifiers.

**Spec:** `docs/superpowers/specs/2026-08-30-capacity-analysis-html-pdf-code-health-design.md`

## Global Constraints

- Preserve Capacity report routing, `capacity_analysis.py` module path, and `build_capacity_analysis_presentation` symbol.
- Preserve exactly nine A4 pages and `reports/pdf/capacity_analysis.html` template semantics.
- Missing storage stays explicit `Not Available`; it must never become zero/healthy/normal.
- Preserve forecast, risk, recommendation, allocation, node participation, methodology, and evidence semantics.
- Keep Jinja/WeasyPrint and existing publication standard; no renderer/schema/visual redesign.
- No generic catch-all HTML/PDF framework in #36.
- Source-inspection tests follow real ownership; no fake imports/comments.
- Code-health defaults remain exactly module `800`, function `160`, branch points `30`, arguments `8`.
- Broad-exception baseline must not increase.
- Edit the exact debt baseline only after fresh scanner evidence.
- Do not create new verification scripts.

---

## File Structure Lock

**Create:**
- `app/reports/export/html_pdf/capacity/__init__.py`
- `app/reports/export/html_pdf/capacity/model.py`
- `app/reports/export/html_pdf/capacity/charts.py`
- `app/reports/export/html_pdf/capacity/forecast.py`
- `app/reports/export/html_pdf/capacity/actions.py`
- `app/reports/export/html_pdf/capacity/sections.py`
- `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`

**Modify:**
- `app/reports/export/html_pdf/capacity_analysis.py`
- `app/reports/export/html_pdf/builder.py` only after caller audit confirms builder-controlled signature migration.
- `tests/reports/test_capacity_analysis_pdf_template.py`
- `docs/architecture/code-health-debt-baseline.json` only after scanner proof.

## Final Boundary

The symbol remains importable from:

```python
from app.reports.export.html_pdf.capacity_analysis import build_capacity_analysis_presentation
```

Preferred repository-internal signature after caller audit:

```python
def build_capacity_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
    return build_capacity_presentation(payload, context=context, classification=classification)
```

If repository search proves another supported caller needs the eleven-argument signature, keep an explicit compatibility wrapper and retain only the unavoidable argument exception. Never use `*args` or `**kwargs` to evade the metric.

---

### Task 1: Structural Ownership RED

**Files:** Create `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`.

**Produces:** a failing contract proving the Capacity-local package does not exist yet.

- [ ] **Step 1: Add the RED contract**

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


def test_capacity_facade_keeps_public_symbol() -> None:
    source = (HTML_PDF / "capacity_analysis.py").read_text()
    assert "def build_capacity_analysis_presentation(" in source
```

- [ ] **Step 2: Observe RED**

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
```

Expected: failure reports missing `capacity/*.py` ownership modules.

- [ ] **Step 3: Commit RED only**

```bash
git add tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
git commit -m "test(reports): lock capacity html pdf ownership"
```

---

### Task 2: Model / Derived-State Extraction

**Files:** Create `capacity/__init__.py`, `capacity/model.py`, import-safe `charts.py`, `forecast.py`, `actions.py`, `sections.py`; modify `capacity_analysis.py`.

**Produces:** Capacity normalization owned outside the facade without behavior change.

- [ ] **Step 1: Move these exact helpers to `capacity/model.py`**

Move `_mapping`, `_sequence`, `_float`, `_int`, `_ratio_percent`, `_percent`, `_optional_percent`, `_metric`, `_risk_metric`, `_capacity_resource`, `_quantity`, `_headroom_status`, and `_allocation_resource` with their current implementations and constants needed only by those helpers.

- [ ] **Step 2: Wire the facade to model ownership**

Replace moved bodies in `capacity_analysis.py` with imports from `capacity.model`. Do not move forecast, action, section, or SVG code in this task.

- [ ] **Step 3: Verify**

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
ruff format --check app/reports/export/html_pdf/capacity_analysis.py app/reports/export/html_pdf/capacity tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
ruff check app/reports/export/html_pdf/capacity_analysis.py app/reports/export/html_pdf/capacity tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add app/reports/export/html_pdf/capacity_analysis.py app/reports/export/html_pdf/capacity tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
git commit -m "refactor(reports): extract capacity presentation model"
```

---

### Task 3: Chart Ownership RED/GREEN

**Files:** Modify `capacity/charts.py`, `capacity_analysis.py`, `tests/reports/test_capacity_analysis_pdf_template.py`.

**Produces:** SVG rendering isolated in `capacity/charts.py`; raw payload never enters the chart module.

- [ ] **Step 1: Redirect source-inspection before production change**

```python
source = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "reports"
    / "export"
    / "html_pdf"
    / "capacity"
    / "charts.py"
).read_text()
assert "resolve_vertical_labels" in source
```

Keep all rendered SVG/font assertions unchanged.

- [ ] **Step 2: Observe RED**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py::test_capacity_analysis_forecast_has_no_svg_font_collision
```

Expected: FAIL because `charts.py` does not yet own `resolve_vertical_labels`.

- [ ] **Step 3: Move exact chart responsibilities**

Move `_capacity_forecast_chart_svg`, `_empty_chart_svg`, `_participation_donut_svg`, `_RESOURCE_COLORS`, and chart-only geometry/label code into `capacity/charts.py`. Import `resolve_vertical_labels` there. Preserve SVG strings, fonts, aria labels, threshold markers, and geometry.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
ruff format --check app/reports/export/html_pdf/capacity/charts.py app/reports/export/html_pdf/capacity_analysis.py tests/reports/test_capacity_analysis_pdf_template.py
ruff check app/reports/export/html_pdf/capacity/charts.py app/reports/export/html_pdf/capacity_analysis.py tests/reports/test_capacity_analysis_pdf_template.py
git add app/reports/export/html_pdf/capacity/charts.py app/reports/export/html_pdf/capacity_analysis.py tests/reports/test_capacity_analysis_pdf_template.py
git commit -m "refactor(reports): extract capacity chart rendering"
```

---

### Task 4: Forecast Preparation Extraction

**Files:** Modify `capacity/forecast.py`, `capacity_analysis.py`, `tests/reports/test_capacity_analysis_pdf_template.py`.

**Produces:** one forecast boundary returning the established `presentation['forecast']` mapping.

- [ ] **Step 1: Lock forecast state before moving it**

Add assertions using the established fixture:

```python
assert document.presentation["forecast"]["available"] is True
assert document.presentation["forecast"]["method"] == "Holt-Winters"
assert tuple(row["resource"] for row in document.presentation["forecast"]["rows"]) == (
    "CPU",
    "Memory",
    "Pods",
)
```

- [ ] **Step 2: Confirm characterization GREEN**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py -k forecast
```

- [ ] **Step 3: Move forecast functions**

Move `_forecast_percent`, `_history_percent`, `_forecast_points_percent`, `_forecast_row`, `_projection_status`, `_projection_tone`, and `_forecast_interpretation` into `capacity/forecast.py` and implement:

```python
def build_forecast_section(
    forecast_payload: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, float | None], dict[str, Any]]:
    """Return projections by resource and the established forecast mapping."""
```

The function calls `capacity.charts` for SVG rendering and preserves CPU, Memory, Pods row order.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
git add app/reports/export/html_pdf/capacity/forecast.py app/reports/export/html_pdf/capacity_analysis.py tests/reports/test_capacity_analysis_pdf_template.py
git commit -m "refactor(reports): extract capacity forecast preparation"
```

---

### Task 5: Action / Evidence Extraction

**Files:** Modify `capacity/actions.py`, `capacity_analysis.py`, `tests/reports/test_capacity_analysis_pdf_template.py`.

**Produces:** findings, risks, recommendations, ownership, source rows, and methodology evidence without HTML/SVG rendering.

- [ ] **Step 1: Capture representative action/evidence outputs from the current fixture**

Run the existing test fixture through `build_report_document` and record the literal risk refs, recommendation refs/priorities, and source-row order in new assertions. Do not invent expected values; copy them from current pre-extraction output.

- [ ] **Step 2: Confirm characterization GREEN**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
```

- [ ] **Step 3: Move exact action/evidence helpers**

Move `_executive_interpretation`, `_executive_findings`, `_risk_rows`, `_recommendation_rows`, `_priority_code`, `_owner_summary`, `_source_rows`, `_format_datetime`, `_latency`, and `_risk_interpretation` into `capacity/actions.py`. Preserve text, ordering, refs, priority mapping, owners, statuses, and source rows.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
ruff format --check app/reports/export/html_pdf/capacity/actions.py app/reports/export/html_pdf/capacity_analysis.py
ruff check app/reports/export/html_pdf/capacity/actions.py app/reports/export/html_pdf/capacity_analysis.py
git add app/reports/export/html_pdf/capacity/actions.py app/reports/export/html_pdf/capacity_analysis.py tests/reports/test_capacity_analysis_pdf_template.py
git commit -m "refactor(reports): extract capacity action evidence"
```

---

### Task 6: Section Builders RED/GREEN and Facade Reduction

**Files:** Modify `capacity/sections.py`, `capacity_analysis.py`, structural contract, Capacity PDF tests.

**Produces:** focused section builders; facade owns only high-level orchestration and publication metadata.

- [ ] **Step 1: Add structural RED**

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

- [ ] **Step 2: Observe RED**

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py::test_capacity_facade_delegates_section_assembly
```

- [ ] **Step 3: Move section assembly with these exact interfaces**

```python
def build_cover_section(cluster: Mapping[str, Any], *, cluster_scope: str) -> dict[str, Any]:
    ...


def build_executive_section(state: Mapping[str, Any]) -> dict[str, Any]:
    ...


def build_compute_section(state: Mapping[str, Any]) -> dict[str, Any]:
    ...


def build_scheduling_section(state: Mapping[str, Any]) -> dict[str, Any]:
    ...


def build_storage_section(state: Mapping[str, Any]) -> dict[str, Any]:
    ...
```

The implementations are the exact existing mapping contents moved from the facade. Use one state mapping/dataclass so every function stays <=8 arguments. Move risk, recommendation, and methodology page-facing mapping assembly into focused section functions while keeping decision semantics in `actions.py`.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
git add app/reports/export/html_pdf/capacity/sections.py app/reports/export/html_pdf/capacity_analysis.py tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
git commit -m "refactor(reports): reduce capacity presentation facade"
```

---

### Task 7: Caller Audit and `ReportDocumentContext` Migration

**Files:** Modify `builder.py`, `capacity_analysis.py`, structural contract when builder-only ownership is confirmed.

- [ ] **Step 1: Audit every call/import of `build_capacity_analysis_presentation`**

Record exact call sites in #36 evidence. The known central caller is `builder.py`.

- [ ] **Step 2: For builder-only ownership, add RED contract**

```python
def test_capacity_builder_uses_report_document_context() -> None:
    source = (HTML_PDF / "builder.py").read_text()
    branch = source.split("elif report.report_type == 'capacity_analysis':", 1)[1].split("elif ", 1)[0]
    assert "context=context" in branch
    assert "report_id=context.report_id" not in branch
    assert "generated_by=context.generated_by_label" not in branch
```

- [ ] **Step 3: Migrate builder-controlled signature**

```python
presentation = build_capacity_analysis_presentation(
    payload,
    context=context,
    classification=classification,
)
```

```python
def build_capacity_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
```

Map metadata from `context.report_id`, `context.report_name`, `context.cluster_scope`, `context.namespace_scope`, `context.period_label`, `context.data_cutoff`, `context.generated_at_label`, and `context.generated_by_label`.

If audit finds another supported caller, preserve compatibility and retain only the argument exception; do not use variadic parameters.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
git add app/reports/export/html_pdf/builder.py app/reports/export/html_pdf/capacity_analysis.py tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
git commit -m "refactor(reports): use report context for capacity presentation"
```

---

### Task 8: Exact Code-Health Ledger Reconciliation

**Current Capacity entries:** module `1255`; function lines `475`; branch points `77`; arguments `11` for `build_capacity_analysis_presentation`.

- [ ] **Step 1:** Run existing `scripts/verify_code_health.py` and baseline-integrity verification before editing baseline.
- [ ] **Step 2:** Confirm all new Capacity modules <=800 lines, functions <=160 lines, branch points <=30, arguments <=8 except a proven compatibility exception.
- [ ] **Step 3:** Remove only scanner-proven stale Capacity entries from `docs/architecture/code-health-debt-baseline.json`; leave unrelated entries, defaults, and `broad_exception_limit` unchanged.
- [ ] **Step 4:** Rerun code-health and baseline integrity; expected PASS with no new debt.
- [ ] **Step 5:** Commit:

```bash
git add docs/architecture/code-health-debt-baseline.json
git commit -m "chore(reports): reconcile capacity code health debt"
```

---

### Task 9: Full Admission, PR, Staging, and UAT

- [ ] **Step 1:** Require full branch KAORI CI PASS: Static/Architecture/Governance, Security/SAST/Dependencies, Functional/Integration, Frontend Reproducibility, Production Image/Container Security/Runtime/DAST, final Admission.
- [ ] **Step 2:** Open/update governed Draft PR to `kaori/staging`; PR body uses Summary → Why/Scope/Changes → Evidence → UAT/Release impact → Reviewer checklist. Project/sidebar instructions remain chat-only.
- [ ] **Step 3:** Review mapping equivalence, missing-storage state, forecast SVG labels, context mapping, exact ledger diff, no catch-all abstraction, and no fake source-inspection ownership.
- [ ] **Step 4:** Move #36 record to `Review` only after branch Admission PASS.
- [ ] **Step 5:** Merge reviewed PR to `kaori/staging` with reviewed head SHA locked; no release tag at staging.
- [ ] **Step 6:** Require post-merge staging Admission PASS.
- [ ] **Step 7:** Move #36 to `UAT`; manual checks cover PDF opens, exactly nine pages, storage missing/available variants, forecast available/unavailable variants, no chart-label collision, and readable methodology/evidence page.
- [ ] **Step 8:** On explicit `UAT PASS #36`, record acceptance, set `Done`, close as `completed`, update #35, and review #38 against Definition of Ready. No release tag unless promotion to `main` is separately approved.
