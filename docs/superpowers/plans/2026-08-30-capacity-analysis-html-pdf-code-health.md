# Capacity Analysis HTML/PDF Code-Health Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Capacity Analysis HTML/PDF presentation ownership into a Capacity-local package while preserving the accepted nine-page publication contract and retiring only scanner-proven Capacity code-health debt.

**Architecture:** Keep `app/reports/export/html_pdf/capacity_analysis.py` as the stable Capacity module/symbol boundary and move cohesive responsibilities into `capacity/model.py`, `capacity/charts.py`, `capacity/forecast.py`, `capacity/actions.py`, and `capacity/sections.py`. The central builder remains the only report-routing authority; where caller audit proves safe, Capacity adopts the existing `ReportDocumentContext` pattern instead of retaining eleven scalar metadata arguments.

**Tech Stack:** Python 3, Flask Reports domain, Jinja2, WeasyPrint, pytest, Ruff, Pyright, KAORI code-health/architecture/release verifiers.

**Spec:** `docs/superpowers/specs/2026-08-30-capacity-analysis-html-pdf-code-health-design.md`

## Global Constraints

- Preserve the Capacity Analysis report-generation route, `capacity_analysis.py` module path, and `build_capacity_analysis_presentation` symbol.
- Preserve exactly nine A4 publication pages and the existing `reports/pdf/capacity_analysis.html` template contract.
- Preserve missing-storage semantics: unavailable evidence must not become zero, healthy, or normal.
- Preserve forecast, risk, recommendation, allocation, node-participation, methodology, and evidence semantics.
- Keep the existing Jinja/WeasyPrint renderer path and publication standard; no renderer, schema, or visual redesign.
- Do not introduce a generic/catch-all HTML/PDF presentation framework in #36.
- Source-inspection tests must follow real ownership; never retain fake imports/comments in the facade.
- Default code-health ceilings remain exactly module `800`, function `160`, branch points `30`, arguments `8`.
- Broad-exception baseline must not increase.
- Exact debt baseline changes occur only after fresh scanner evidence reports Capacity entries stale/resolved.
- No new ad-hoc verification scripts; use existing KAORI checks.

---

## File Structure Lock

**Create:**
- `app/reports/export/html_pdf/capacity/__init__.py` — package marker only; no cross-family abstraction.
- `app/reports/export/html_pdf/capacity/model.py` — Capacity-local normalization and derived state.
- `app/reports/export/html_pdf/capacity/charts.py` — pure SVG construction and chart-label ownership.
- `app/reports/export/html_pdf/capacity/forecast.py` — forecast normalization, projection semantics, and forecast section state.
- `app/reports/export/html_pdf/capacity/actions.py` — findings, risks, recommendations, owners, source/methodology evidence.
- `app/reports/export/html_pdf/capacity/sections.py` — focused template-facing section builders.
- `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py` — structural ownership and dependency contract.

**Modify:**
- `app/reports/export/html_pdf/capacity_analysis.py` — reduce to Capacity facade/orchestration.
- `app/reports/export/html_pdf/builder.py` — only if caller audit proves `ReportDocumentContext` signature migration safe.
- `tests/reports/test_capacity_analysis_pdf_template.py` — redirect source-inspection assertion to the true chart owner while preserving all behavioral assertions.
- `docs/architecture/code-health-debt-baseline.json` — remove only scanner-proven stale Capacity entries.
- Issue #36 / parent #35 governance records — evidence/status only; no implementation instructions in bodies.

## Interface Lock

The final report-facing function remains importable as:

```python
from app.reports.export.html_pdf.capacity_analysis import build_capacity_analysis_presentation
```

Preferred final repository-internal signature, only after caller audit:

```python
def build_capacity_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
    ...
```

If a supported repository caller beyond `builder.py` requires the existing eleven-argument signature, preserve an explicit compatibility boundary and retain only the truly unavoidable argument-debt entry. Do not use `*args` or `**kwargs` to evade the metric.

---

### Task 1: Structural Ownership RED Contract

**Files:**
- Create: `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`
- Read only: `app/reports/export/html_pdf/capacity_analysis.py`

**Interfaces:**
- Consumes: current monolithic Capacity module.
- Produces: failing ownership contract that defines the package boundary without constraining internal helper names unnecessarily.

- [ ] **Step 1: Write the failing structural contract**

Create tests that assert the planned module files exist, the facade still defines/imports `build_capacity_analysis_presentation`, package modules do not import `capacity_analysis`, and SVG ownership is no longer expected to remain in the facade once extraction starts.

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HTML_PDF = ROOT / "app" / "reports" / "export" / "html_pdf"


def test_capacity_refactor_uses_focused_local_package() -> None:
    for relative in (
        "capacity/model.py",
        "capacity/charts.py",
        "capacity/forecast.py",
        "capacity/actions.py",
        "capacity/sections.py",
    ):
        assert (HTML_PDF / relative).is_file(), relative


def test_capacity_package_does_not_import_facade() -> None:
    for path in (HTML_PDF / "capacity").glob("*.py"):
        source = path.read_text()
        assert "from app.reports.export.html_pdf.capacity_analysis" not in source
        assert "import app.reports.export.html_pdf.capacity_analysis" not in source
```

Add one facade-source assertion that the symbol remains available but avoid asserting an exact list of helper function names.

- [ ] **Step 2: Run RED**

Run:

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
```

Expected: FAIL because the `capacity/` modules do not exist yet.

- [ ] **Step 3: Commit RED only**

```bash
git add tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
git commit -m "test(reports): lock capacity html pdf ownership"
```

Do not modify production code in this commit.

---

### Task 2: Capacity Model / Derived-State Extraction

**Files:**
- Create: `app/reports/export/html_pdf/capacity/__init__.py`
- Create: `app/reports/export/html_pdf/capacity/model.py`
- Modify: `app/reports/export/html_pdf/capacity_analysis.py`
- Test: `tests/reports/test_capacity_analysis_pdf_template.py`
- Test: `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`

**Interfaces:**
- Produces focused Capacity-local primitives for mapping/sequence/number conversion, resource normalization, allocation normalization, quantity/headroom/status/tone derivation, and node participation state.
- `capacity_analysis.py` consumes those functions without changing final presentation values.

- [ ] **Step 1: Move only normalization/derived-state functions**

Move cohesive logic currently represented by functions such as `_mapping`, `_sequence`, `_float`, `_int`, `_ratio_percent`, `_percent`, `_optional_percent`, `_metric`, `_risk_metric`, `_capacity_resource`, `_quantity`, `_headroom_status`, and `_allocation_resource` into `capacity/model.py`.

Keep names private unless a cross-module call requires an explicit exported name. Prefer a small typed internal context only if it clearly reduces repeated argument fan-out; do not invent a second publication metadata model.

- [ ] **Step 2: Wire the facade to model ownership**

Replace the moved bodies in `capacity_analysis.py` with imports from `capacity.model`. Do not move forecast, action, section, or SVG behavior in this task.

- [ ] **Step 3: Run targeted behavioral regression**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
```

Expected: Capacity behavioral suite PASS; structural contract may remain partially RED only for boundaries not yet created if split into separate assertions. If Task 1 contract is all-or-nothing, create all package placeholder files in the same atomic GREEN commit but keep them behavior-free until their tasks.

- [ ] **Step 4: Run format/lint on changed Python files**

```bash
ruff format --check app/reports/export/html_pdf/capacity_analysis.py app/reports/export/html_pdf/capacity tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
ruff check app/reports/export/html_pdf/capacity_analysis.py app/reports/export/html_pdf/capacity tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
```

Expected: PASS.

- [ ] **Step 5: Commit model extraction**

```bash
git add app/reports/export/html_pdf/capacity_analysis.py app/reports/export/html_pdf/capacity tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
git commit -m "refactor(reports): extract capacity presentation model"
```

---

### Task 3: Capacity Chart Ownership Extraction

**Files:**
- Create/Modify: `app/reports/export/html_pdf/capacity/charts.py`
- Modify: `app/reports/export/html_pdf/capacity_analysis.py`
- Modify: `tests/reports/test_capacity_analysis_pdf_template.py`

**Interfaces:**
- Produces SVG helpers receiving normalized values only and returning `str`.
- Owns `resolve_vertical_labels` usage for Capacity forecast rendering.
- Must not receive/read raw report payloads.

- [ ] **Step 1: Update the source-ownership regression first**

Change only the source-inspection portion of `test_capacity_analysis_forecast_has_no_svg_font_collision` so it reads:

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

Keep all rendered-HTML/font assertions unchanged.

- [ ] **Step 2: Run the test and verify RED**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py::test_capacity_analysis_forecast_has_no_svg_font_collision
```

Expected: FAIL while chart ownership has not moved.

- [ ] **Step 3: Move SVG implementation**

Move the current forecast chart, empty chart, node participation donut, and chart-only helpers into `capacity/charts.py`. Import `resolve_vertical_labels` there. Keep colors, geometry, label text, aria labels, font declarations, and empty-state strings byte-for-byte equivalent where practical.

- [ ] **Step 4: Run full Capacity regression**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
```

Expected: PASS including exact nine-page WeasyPrint geometry.

- [ ] **Step 5: Commit chart extraction**

```bash
git add app/reports/export/html_pdf/capacity/charts.py app/reports/export/html_pdf/capacity_analysis.py tests/reports/test_capacity_analysis_pdf_template.py
git commit -m "refactor(reports): extract capacity chart rendering"
```

---

### Task 4: Capacity Forecast Ownership Extraction

**Files:**
- Create/Modify: `app/reports/export/html_pdf/capacity/forecast.py`
- Modify: `app/reports/export/html_pdf/capacity_analysis.py`
- Test: `tests/reports/test_capacity_analysis_pdf_template.py`

**Interfaces:**
- Consumes normalized resources plus raw forecast section mapping only.
- Produces projection mapping, forecast rows, method/availability, interpretation, and final `forecast` section mapping.
- May call `capacity.charts`; must not call the facade.

- [ ] **Step 1: Add a focused characterization assertion if needed**

If existing tests do not directly lock forecast method, rows, and unavailable-state values, extend `test_capacity_analysis_pdf_template.py` with assertions against `document.presentation["forecast"]` before moving code.

- [ ] **Step 2: Observe characterization GREEN before extraction**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py -k forecast
```

Expected: PASS on current behavior.

- [ ] **Step 3: Extract forecast semantics**

Move `_forecast_percent`, `_history_percent`, `_forecast_points_percent`, `_forecast_row`, `_projection_status`, `_projection_tone`, and `_forecast_interpretation` plus forecast-section assembly into `capacity/forecast.py`.

Provide one explicit preparation interface, for example:

```python
def build_forecast_state(
    forecast_payload: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    ...
```

The returned mapping must expose the same template-facing `forecast` keys as before.

- [ ] **Step 4: Run regression**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
```

Expected: PASS.

- [ ] **Step 5: Commit forecast extraction**

```bash
git add app/reports/export/html_pdf/capacity/forecast.py app/reports/export/html_pdf/capacity_analysis.py tests/reports/test_capacity_analysis_pdf_template.py
git commit -m "refactor(reports): extract capacity forecast preparation"
```

---

### Task 5: Findings, Risks, Recommendations, and Evidence Extraction

**Files:**
- Create/Modify: `app/reports/export/html_pdf/capacity/actions.py`
- Modify: `app/reports/export/html_pdf/capacity_analysis.py`
- Test: `tests/reports/test_capacity_analysis_pdf_template.py`

**Interfaces:**
- Consumes committed payload plus normalized resources/projections/node state.
- Produces executive findings, risk rows, recommendation rows, owner summary, source rows, risk/recommendation interpretation, and methodology/action evidence.
- Must not render HTML/SVG or read live integrations.

- [ ] **Step 1: Lock existing action/evidence shapes**

Add narrow assertions only where current suite does not already assert these shapes. Assert stable refs/priorities/statuses/order for representative risk/recommendation/source rows using the existing `_payload()` fixture.

- [ ] **Step 2: Run characterization before extraction**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
```

Expected: PASS.

- [ ] **Step 3: Extract action/evidence logic**

Move `_executive_interpretation`, `_executive_findings`, `_risk_rows`, `_recommendation_rows`, `_priority_code`, `_owner_summary`, `_source_rows`, `_format_datetime`, `_latency`, and `_risk_interpretation` where their semantics belong. Keep Capacity-specific text and row ordering unchanged.

Do not move generic sanitation helpers from `normalization.py` into Capacity.

- [ ] **Step 4: Run regression and targeted code quality**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
ruff format --check app/reports/export/html_pdf/capacity/actions.py app/reports/export/html_pdf/capacity_analysis.py
ruff check app/reports/export/html_pdf/capacity/actions.py app/reports/export/html_pdf/capacity_analysis.py
```

Expected: PASS.

- [ ] **Step 5: Commit action/evidence extraction**

```bash
git add app/reports/export/html_pdf/capacity/actions.py app/reports/export/html_pdf/capacity_analysis.py tests/reports/test_capacity_analysis_pdf_template.py
git commit -m "refactor(reports): extract capacity action evidence"
```

---

### Task 6: Section Builders and Facade Reduction

**Files:**
- Create/Modify: `app/reports/export/html_pdf/capacity/sections.py`
- Modify: `app/reports/export/html_pdf/capacity_analysis.py`
- Test: `tests/reports/test_capacity_analysis_pdf_template.py`
- Test: `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`

**Interfaces:**
- `capacity.sections` returns the established `cover`, `executive`, `compute`, `scheduling`, `storage`, `risks`, `recommendations`, and methodology/evidence mappings.
- The facade owns only top-level publication metadata plus orchestration.

- [ ] **Step 1: Add/strengthen structural RED for facade size/ownership**

Add a structural assertion that the facade delegates section assembly and does not retain inline construction for all major section keys. Prefer AST/source-boundary assertions that prove ownership without depending on exact internal helper names.

- [ ] **Step 2: Verify RED**

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
```

Expected: FAIL until section assembly moves.

- [ ] **Step 3: Extract focused section builders**

Create builders such as:

```python
def build_cover_section(...)->dict[str, Any]: ...
def build_executive_section(...)->dict[str, Any]: ...
def build_compute_section(...)->dict[str, Any]: ...
def build_scheduling_section(...)->dict[str, Any]: ...
def build_storage_section(...)->dict[str, Any]: ...
```

Use small context objects/mappings to keep each function at or below 8 arguments. Do not solve argument debt by variadic parameters.

The facade should assemble the final publication mapping and call these focused builders rather than constructing hundreds of inline lines.

- [ ] **Step 4: Run structural + behavioral regression**

```bash
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
```

Expected: PASS.

- [ ] **Step 5: Commit section/facade extraction**

```bash
git add app/reports/export/html_pdf/capacity/sections.py app/reports/export/html_pdf/capacity_analysis.py tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py tests/reports/test_capacity_analysis_pdf_template.py
git commit -m "refactor(reports): reduce capacity presentation facade"
```

---

### Task 7: Caller Audit and `ReportDocumentContext` Signature Migration

**Files:**
- Modify: `app/reports/export/html_pdf/builder.py`
- Modify: `app/reports/export/html_pdf/capacity_analysis.py`
- Possibly modify imports/types in `app/reports/export/html_pdf/capacity/*`
- Test: `tests/reports/test_capacity_analysis_pdf_template.py`
- Test: `tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py`

**Interfaces:**
- Preferred producer: `builder.py` calls `build_capacity_analysis_presentation(payload, context=context, classification=classification)`.
- Facade consumes existing `ReportDocumentContext`; no duplicate publication metadata dataclass.

- [ ] **Step 1: Audit repository callers**

Use repository code search and tests to identify every call/import of `build_capacity_analysis_presentation`. Confirm whether `builder.py` is the only supported call site.

- [ ] **Step 2: Add a failing contract for the narrowed internal call if safe**

If caller audit confirms builder-only ownership, assert builder source passes `context=context` rather than eleven metadata scalars. Run the contract and observe RED.

If another supported caller exists, document it in #36 and skip the incompatible signature migration; keep only the necessary argument-debt entry.

- [ ] **Step 3: Migrate the controlled call boundary**

For builder-only ownership, change Capacity to:

```python
def build_capacity_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
    ...
```

Map existing metadata directly from `context`: `report_id`, `report_name`, `cluster_scope`, `namespace_scope`, `period_label`, `data_cutoff`, `generated_at_label`, and `generated_by_label`.

- [ ] **Step 4: Run Capacity and builder regression**

```bash
pytest -q tests/reports/test_capacity_analysis_pdf_template.py
pytest -q tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
```

Expected: PASS.

- [ ] **Step 5: Commit signature migration or compatibility finding**

```bash
git add app/reports/export/html_pdf/builder.py app/reports/export/html_pdf/capacity_analysis.py tests/contracts/reports/test_capacity_html_pdf_code_health_contract.py
git commit -m "refactor(reports): use report context for capacity presentation"
```

If migration is unsafe, commit only the documented/contractual compatibility decision if repository files need updating; do not fabricate a code change.

---

### Task 8: Code-Health Scanner and Exact Ledger Reconciliation

**Files:**
- Modify only if scanner proves stale: `docs/architecture/code-health-debt-baseline.json`
- Read/verify: all Capacity modules.

**Interfaces:**
- Consumes final Capacity source.
- Produces exact baseline with only still-existing debt exceptions.

- [ ] **Step 1: Run canonical code-health verification before baseline edit**

Use existing KAORI verification, including the canonical code-health scanner/baseline integrity commands already used by CI. The expected scanner result is that some or all of these are stale:

```text
app/reports/export/html_pdf/capacity_analysis.py = 1255 module lines
...::build_capacity_analysis_presentation = 475 function lines
...::build_capacity_analysis_presentation = 77 branch points
...::build_capacity_analysis_presentation = 11 arguments
```

Do not edit baseline until the scanner says they are resolved/stale.

- [ ] **Step 2: Inspect all new Capacity files against defaults**

Confirm every new module is <=800 lines, every function <=160 lines and <=30 branch points, and every function <=8 arguments unless a justified residual entry is intentionally retained.

- [ ] **Step 3: Remove only stale Capacity entries**

Edit `docs/architecture/code-health-debt-baseline.json` minimally. Do not alter unrelated debt or defaults; `broad_exception_limit` remains `181` unless an existing verifier independently proves a justified reduction.

- [ ] **Step 4: Rerun exact baseline verification**

Expected: code-health and baseline-integrity PASS with no new debt.

- [ ] **Step 5: Commit ledger reconciliation**

```bash
git add docs/architecture/code-health-debt-baseline.json
git commit -m "chore(reports): reconcile capacity code health debt"
```

---

### Task 9: Full Branch Verification, Draft PR, and Review Evidence

**Files:**
- No source changes unless an actual verification failure requires a focused fix.
- GitHub: Issue #36, parent #35, PR body/metadata.

**Interfaces:**
- Consumes final branch head.
- Produces reviewable PR with full Admission evidence.

- [ ] **Step 1: Run/observe full KAORI CI on final branch head**

Require all normal stages to pass: Static/Architecture/Governance, Security/SAST/Dependencies, Functional/Integration, Frontend Reproducibility, Production Image/Container Security/Runtime/DAST, and final Admission.

- [ ] **Step 2: Create/update governed Draft PR to `kaori/staging`**

PR body follows KAORI closed examples: Summary, Why/Scope/Changes, Evidence, UAT/Release impact, Reviewer checklist. Do not place instructions for GitHub Project/sidebar metadata in the PR body.

- [ ] **Step 3: Review high-risk diffs**

Review at minimum:
- final presentation mapping equivalence;
- missing-storage behavior;
- forecast SVG/label behavior;
- `ReportDocumentContext` mapping if migrated;
- exact debt baseline diff;
- no cross-family/catch-all abstraction;
- no fake source-inspection evidence.

- [ ] **Step 4: Move Issue #36 lifecycle record to `Review` only after full branch Admission is PASS**

Keep repository Issue open.

---

### Task 10: Staging Integration and UAT Handoff

**Files:**
- No implementation file changes expected.
- GitHub: PR, Issue #36, parent #35, Epic #6 evidence records.

**Interfaces:**
- Consumes reviewed PR with branch Admission PASS.
- Produces staging merge + staging Admission + explicit Local UAT handoff.

- [ ] **Step 1: Merge governed PR to `kaori/staging`**

Lock merge to the reviewed head SHA. Do not tag a release at this staging boundary.

- [ ] **Step 2: Verify post-merge staging CI**

Require the same complete Admission chain on the merge commit.

- [ ] **Step 3: Move #36 to `UAT` and provide Capacity-specific UAT instructions in chat**

UAT must verify at least:
- generated Capacity PDF opens successfully;
- exactly nine pages;
- missing-storage and available-storage variants remain correct;
- forecast available/unavailable states remain correct;
- no chart label collision;
- methodology/evidence page remains readable;
- accepted layout/typography has no regression.

- [ ] **Step 4: Close #36 only after explicit user acceptance**

On `UAT PASS #36`, record acceptance, set lifecycle `Done`, close as `completed`, and update #35 so #38 can be considered for `Ready` after its own Definition of Ready review.

No release tag is created unless an explicit release/promotion boundary to `main` is separately approved.
