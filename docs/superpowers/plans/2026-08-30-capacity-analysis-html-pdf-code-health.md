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

- [x] Create `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py` with:

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

- [x] Run `pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`; RED observed in CI run #276 because `capacity/model.py` was absent on SHA `15a2771705f132a036bdd4717a7f6ee75d247caf`.
- [x] Commit only this test as `test(reports): lock capacity html pdf ownership`.

### Task 2: Model / Derived State

- [x] Create all six `capacity/` package files so Task 1 can turn GREEN without import-broken intermediate commits.
- [x] Move the current normalization implementations into `capacity/model.py`: mapping/sequence/number conversion, resource normalization, allocation normalization, quantity/headroom/status/tone helpers.
- [ ] Wire the facade to model ownership and delete the dead duplicated helper bodies from `capacity_analysis.py` during the single facade rewrite in Task 6; this avoids repeated full-file rewrites through the GitHub connector.
- [ ] Verify structural contract + Capacity PDF regression + Ruff after the atomic boundary commit reaches CI.

### Task 3: Chart Ownership RED/GREEN

- [ ] Redirect source-inspection to `capacity/charts.py`, observe RED, move chart rendering, run Capacity regression, commit.

### Task 4: Forecast Preparation

- [ ] Lock forecast method/row order, extract forecast functions, run Capacity regression, commit.

### Task 5: Actions / Evidence

- [ ] Capture literal action/evidence outputs, extract action/evidence logic, run Capacity regression, commit.

### Task 6: Section Builders RED/GREEN

- [ ] Add structural RED that facade delegates section assembly.
- [ ] Move existing `cover`, `executive`, `compute`, `scheduling`, `storage`, `risks`, `recommendations`, and methodology/evidence mapping blocks to focused builders in `capacity/sections.py`.
- [ ] During this same full-file facade rewrite, replace all model/chart/forecast/action helper calls with their Capacity-local owners and remove dead duplicated helper bodies from `capacity_analysis.py`.
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
