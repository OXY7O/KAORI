# Storage Analysis HTML/PDF Code-Health Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Storage Analysis HTML/PDF presentation assembly into cohesive Storage-local modules while preserving the accepted nine-page publication contract and removing only scanner-proven Storage code-health debt.

**Architecture:** Keep `app/reports/export/html_pdf/storage_analysis.py` as a thin report-family facade. Move normalized input/state into `storage/model.py`, filesystem/PV/PVC evidence into `storage/records.py`, committed historical/forecast semantics into `storage/trend.py`, findings/risk/recommendations into `storage/actions.py`, and page-facing dictionaries into `storage/sections.py`. Use the existing `ReportDocumentContext` at the builder boundary after the caller contract is proven safe.

**Tech Stack:** Python 3, Flask report builder, Jinja, WeasyPrint, pytest, Ruff, Pyright, KAORI code-health/architecture verifiers.

**Spec:** `docs/superpowers/specs/2026-08-30-storage-analysis-html-pdf-code-health-design.md`

## Global Constraints

- Preserve exactly nine Storage publication pages in this order: Cover, Executive Brief, Capacity, Filesystem, Persistent Storage, Risk, Trend, Recommendations, Methodology and Evidence Boundary.
- Preserve top-level template keys: `cover`, `executive`, `capacity`, `filesystem`, `persistent`, `risk`, `trend`, `recommendations`, `methodology`.
- Missing aggregate filesystem evidence stays explicit `Not Available`; it must not become zero or Normal.
- PV/PVC inventory does not imply utilization evidence.
- Expansion support is unavailable unless positive committed evidence exists.
- Missing trend/forecast evidence remains unavailable; never synthesize a line.
- Committed report payload remains authoritative; no live source fallback.
- Preserve threshold semantics: Normal below 70%, Warning 70%–84.9%, Critical 85% and above.
- Keep code-health defaults unchanged: module 800 lines, function 160 lines, branch points 30, arguments 8.
- Do not increase the broad-exception baseline or add metric-only compatibility wrappers.
- Do not change renderer, report schema, template name, CSS/publication standard, security/DAST gates, or release gates.

---

### Task 1: Lock Storage ownership and canonical builder boundary with RED contracts

**Files:**
- Create: `tests/contracts/reports/test_storage_analysis_context_boundary_contract.py`
- Create: `tests/contracts/reports/test_storage_html_pdf_code_health_contract.py`
- Read-only reference: `app/reports/export/html_pdf/builder.py`
- Read-only reference: `app/reports/export/html_pdf/storage_analysis.py`

**Interfaces:**
- Consumes: current `build_storage_analysis_presentation(report, payload, *, ...)` implementation.
- Produces: structural contract for `build_storage_analysis_presentation(payload, *, context, classification)` and Storage-local ownership modules.

- [ ] **Step 1: Add the failing context-boundary contract**

```python
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STORAGE_PATH = 'app/reports/export/html_pdf/storage_analysis.py'
BUILDER_PATH = 'app/reports/export/html_pdf/builder.py'


def _module(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(encoding='utf-8'))


def _function(module: ast.Module, name: str) -> ast.FunctionDef:
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'{name} was not found')


def _call(module: ast.Module, name: str) -> ast.Call:
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name:
            return node
    raise AssertionError(f'{name} call was not found')


def test_storage_analysis_uses_report_document_context_boundary() -> None:
    function = _function(_module(STORAGE_PATH), 'build_storage_analysis_presentation')
    positional = [argument.arg for argument in (*function.args.posonlyargs, *function.args.args)]
    keyword_only = [argument.arg for argument in function.args.kwonlyargs]

    assert positional == ['payload']
    assert keyword_only == ['context', 'classification']

    call = _call(_module(BUILDER_PATH), 'build_storage_analysis_presentation')
    assert len(call.args) == 1
    assert isinstance(call.args[0], ast.Name) and call.args[0].id == 'payload'
    assert [keyword.arg for keyword in call.keywords] == ['context', 'classification']
```

- [ ] **Step 2: Add the failing ownership contract**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HTML_PDF = ROOT / 'app' / 'reports' / 'export' / 'html_pdf'


def test_storage_refactor_uses_focused_local_package() -> None:
    expected = (
        'storage/model.py',
        'storage/records.py',
        'storage/trend.py',
        'storage/actions.py',
        'storage/sections.py',
    )
    missing = [relative for relative in expected if not (HTML_PDF / relative).is_file()]
    assert not missing, f'missing Storage ownership modules: {missing}'


def test_storage_package_never_imports_facade() -> None:
    package = HTML_PDF / 'storage'
    assert package.is_dir()
    for path in package.glob('*.py'):
        source = path.read_text(encoding='utf-8')
        assert 'from app.reports.export.html_pdf.storage_analysis' not in source
        assert 'import app.reports.export.html_pdf.storage_analysis' not in source


def test_storage_facade_keeps_symbol() -> None:
    source = (HTML_PDF / 'storage_analysis.py').read_text(encoding='utf-8')
    assert 'def build_storage_analysis_presentation(' in source
```

- [ ] **Step 3: Run the RED contracts**

Run:

```bash
pytest -q \
  tests/contracts/reports/test_storage_analysis_context_boundary_contract.py \
  tests/contracts/reports/test_storage_html_pdf_code_health_contract.py
```

Expected: failures because Storage still has the legacy argument fan-out and the `storage/` ownership modules do not exist.

- [ ] **Step 4: Commit RED characterization**

```bash
git add \
  tests/contracts/reports/test_storage_analysis_context_boundary_contract.py \
  tests/contracts/reports/test_storage_html_pdf_code_health_contract.py
git commit -m "test(reports): characterize Storage presentation debt #38"
```

### Task 2: Extract Storage input state and filesystem/PV/PVC record semantics

**Files:**
- Create: `app/reports/export/html_pdf/storage/__init__.py`
- Create: `app/reports/export/html_pdf/storage/model.py`
- Create: `app/reports/export/html_pdf/storage/records.py`
- Modify: `app/reports/export/html_pdf/storage_analysis.py`
- Test: `tests/reports/test_storage_analysis_pdf_template.py`

**Interfaces:**
- Produces `StorageInputState` from `build_storage_input_state(payload)`.
- Produces `StorageRecordState` from `build_storage_record_state(state)`.
- Record state owns aggregate capacity, filesystem rows, PV/PVC summaries/records, localized risk counts, binding coverage, and expansion-evidence availability.

- [ ] **Step 1: Add `StorageInputState` and normalization primitives**

Implement `storage/model.py` with an immutable dataclass containing `payload`, `cluster`, `storage_summary`, `filesystem`, `filesystem_summary`, `persistent`, `pv`, `pvc`, `filesystem_rows`, `pv_rows`, and `pvc_rows`. Move the existing Storage-local `_mapping`, `_rows`, `_safe_float`, `_safe_int`, `_text`, `_percent`, `_status_from_percent`, `_risk_tone`, and `_risk_label` behavior without semantic changes.

Required constructor:

```python
def build_storage_input_state(payload: Mapping[str, Any]) -> StorageInputState:
    ...
```

- [ ] **Step 2: Move record/capacity behavior into `storage/records.py`**

Provide:

```python
@dataclass(frozen=True, slots=True)
class StorageRecordState:
    capacity: dict[str, Any]
    filesystem_records: tuple[dict[str, Any], ...]
    pv_summary: dict[str, Any]
    pvc_summary: dict[str, Any]
    pv_records: tuple[dict[str, Any], ...]
    pvc_records: tuple[dict[str, Any], ...]
    local_risks: int
    pv_risks: int
    pvc_risks: int
    binding_coverage: str
    expansion_available: bool


def build_storage_record_state(state: StorageInputState) -> StorageRecordState:
    ...
```

Move the exact existing behavior for capacity calculation, filesystem records, risk counting, PV/PVC summaries and records, binding coverage, and expansion-evidence detection. Keep `allow_expansion` / `expansion_supported` as the only positive expansion signals.

- [ ] **Step 3: Delegate equivalent work from the facade**

Replace raw filesystem/PV/PVC normalization at the top of `build_storage_analysis_presentation` with:

```python
state = build_storage_input_state(payload)
records = build_storage_record_state(state)
```

Use `records.capacity`, `records.filesystem_records`, `records.pv_summary`, `records.pvc_summary`, and the record risk counts without changing the final presentation mapping yet.

- [ ] **Step 4: Run Storage behavior regression**

```bash
pytest -q tests/reports/test_storage_analysis_pdf_template.py
```

Expected: all Storage behavior tests pass, including explicit missing filesystem/PV/PVC evidence and exact nine-page WeasyPrint output.

- [ ] **Step 5: Run focused Ruff**

```bash
ruff format --check \
  app/reports/export/html_pdf/storage_analysis.py \
  app/reports/export/html_pdf/storage
ruff check \
  app/reports/export/html_pdf/storage_analysis.py \
  app/reports/export/html_pdf/storage
```

Expected: PASS.

- [ ] **Step 6: Commit model/records extraction**

```bash
git add app/reports/export/html_pdf/storage_analysis.py app/reports/export/html_pdf/storage
git commit -m "refactor(reports): extract Storage evidence state #38"
```

### Task 3: Extract committed trend semantics and action/risk ownership

**Files:**
- Create: `app/reports/export/html_pdf/storage/trend.py`
- Create: `app/reports/export/html_pdf/storage/actions.py`
- Modify: `app/reports/export/html_pdf/storage_analysis.py`
- Test: `tests/reports/test_storage_analysis_pdf_template.py`

**Interfaces:**
- `build_storage_trend_state(payload, *, current_percent) -> dict[str, Any]` preserves existing trend keys and empty-chart behavior.
- `build_storage_action_state(payload, *, records, trend) -> StorageActionState` owns findings, risk register, recommendation plan, actionable count, and executive/action interpretation data.

- [ ] **Step 1: Move trend helpers into `storage/trend.py`**

Move the existing `_storage_trend` and its trend-only helpers without changing output keys. Expose:

```python
def build_storage_trend_state(
    payload: Mapping[str, Any],
    *,
    current_percent: float,
) -> dict[str, Any]:
    ...
```

When forecast evidence is absent, preserve `available is False` and `chart_svg == ''`.

- [ ] **Step 2: Move recommendation/risk helpers into `storage/actions.py`**

Create an immutable `StorageActionState` carrying `recommendation_cards`, `actionable_count`, `findings`, `risk_register`, and `recommendations`. Move the exact current recommendation-card normalization, owner derivation, executive findings/title/body, risk rows, recommendation plan/title/metrics, owner summary, and related action interpretation.

Expose:

```python
def build_storage_action_state(
    payload: Mapping[str, Any],
    *,
    records: StorageRecordState,
    trend: Mapping[str, Any],
) -> StorageActionState:
    ...
```

- [ ] **Step 3: Delegate trend/action derivation from the facade**

Use:

```python
trend = build_storage_trend_state(payload, current_percent=records.capacity['used_percent'])
actions = build_storage_action_state(payload, records=records, trend=trend)
```

Retain the final section dictionaries in the facade for this checkpoint.

- [ ] **Step 4: Run Storage regression and shared publication contract**

```bash
pytest -q \
  tests/reports/test_storage_analysis_pdf_template.py \
  tests/contracts/reports/test_analytics_pdf_publication_v3_contract.py
```

Expected: PASS.

- [ ] **Step 5: Commit trend/action extraction**

```bash
git add \
  app/reports/export/html_pdf/storage_analysis.py \
  app/reports/export/html_pdf/storage/trend.py \
  app/reports/export/html_pdf/storage/actions.py
git commit -m "refactor(reports): isolate Storage trend and actions #38"
```

### Task 4: Decompose the nine page-facing section contracts

**Files:**
- Create: `app/reports/export/html_pdf/storage/sections.py`
- Modify: `app/reports/export/html_pdf/storage_analysis.py`
- Test: `tests/reports/test_storage_analysis_pdf_template.py`
- Test: `tests/contracts/reports/test_storage_html_pdf_code_health_contract.py`

**Interfaces:**
- Section builders return the existing Jinja-facing dictionaries for `cover`, `executive`, `capacity`, `filesystem`, `persistent`, `risk`, `trend`, `recommendations`, and `methodology`.
- `count_donut_svg` remains an existing shared publication helper, not reimplemented.

- [ ] **Step 1: Add focused section builders**

Implement these functions in `storage/sections.py`:

```python
def build_cover_section(...) -> dict[str, Any]: ...
def build_executive_section(...) -> dict[str, Any]: ...
def build_capacity_section(...) -> dict[str, Any]: ...
def build_filesystem_section(...) -> dict[str, Any]: ...
def build_persistent_section(...) -> dict[str, Any]: ...
def build_risk_section(...) -> dict[str, Any]: ...
def build_trend_section(...) -> dict[str, Any]: ...
def build_recommendation_section(...) -> dict[str, Any]: ...
def build_methodology_section(...) -> dict[str, Any]: ...
```

Move existing page-facing dictionary construction verbatim by semantic unit. Do not re-normalize raw payload where `StorageInputState`, `StorageRecordState`, trend, or actions already provide the value.

- [ ] **Step 2: Reduce `storage_analysis.py` to orchestration**

The facade should perform only state derivation plus publication mapping assembly. Its return shape must remain:

```python
{
    'presentation_version': 'v3.0-storage-analysis-publication',
    'publication_family': ANALYTICS_PUBLICATION_FAMILY,
    'publication_standard': ANALYTICS_PUBLICATION_STANDARD,
    'canonical_reference': ANALYTICS_CANONICAL_REFERENCE,
    'page_count': 9,
    'layout_contract': analytics_layout_contract(...),
    # report metadata,
    'cover': ...,
    'executive': ...,
    'capacity': ...,
    'filesystem': ...,
    'persistent': ...,
    'risk': ...,
    'trend': ...,
    'recommendations': ...,
    'methodology': ...,
}
```

- [ ] **Step 3: Run Storage behavior and ownership contracts**

```bash
pytest -q \
  tests/reports/test_storage_analysis_pdf_template.py \
  tests/contracts/reports/test_storage_html_pdf_code_health_contract.py
```

Expected: Storage behavior PASS and Storage package ownership PASS. The context-boundary test may still be RED until Task 5.

- [ ] **Step 4: Commit section decomposition**

```bash
git add \
  app/reports/export/html_pdf/storage_analysis.py \
  app/reports/export/html_pdf/storage/sections.py
git commit -m "refactor(reports): decompose Storage publication sections #38"
```

### Task 5: Migrate the Storage facade to canonical `ReportDocumentContext`

**Files:**
- Modify: `app/reports/export/html_pdf/storage_analysis.py`
- Modify: `app/reports/export/html_pdf/builder.py`
- Test: `tests/contracts/reports/test_storage_analysis_context_boundary_contract.py`
- Test: `tests/reports/test_storage_analysis_pdf_template.py`

**Interfaces:**
- Final repository-internal entrypoint:

```python
def build_storage_analysis_presentation(
    payload: Mapping[str, Any],
    *,
    context: ReportDocumentContext,
    classification: str,
) -> dict[str, Any]:
    ...
```

- [ ] **Step 1: Re-run repository caller search before changing the signature**

```bash
rg -n "build_storage_analysis_presentation" .
```

Expected supported production caller: `app/reports/export/html_pdf/builder.py`; tests/contracts may inspect the symbol but no supported production caller should depend on the old 11-argument form.

- [ ] **Step 2: Change facade signature and metadata access**

Import `ReportDocumentContext` and replace metadata fan-out with `context.report_id`, `context.report_name`, `context.cluster_scope`, `context.namespace_scope`, `context.period_label`, `context.data_cutoff`, `context.generated_at_label`, and `context.generated_by_label`.

- [ ] **Step 3: Change builder dispatch**

Replace the legacy Storage call with:

```python
presentation = build_storage_analysis_presentation(
    payload,
    context=context,
    classification=classification,
)
```

- [ ] **Step 4: Run context RED-to-GREEN plus Storage regression**

```bash
pytest -q \
  tests/contracts/reports/test_storage_analysis_context_boundary_contract.py \
  tests/contracts/reports/test_storage_html_pdf_code_health_contract.py \
  tests/reports/test_storage_analysis_pdf_template.py
```

Expected: PASS.

- [ ] **Step 5: Commit context migration**

```bash
git add \
  app/reports/export/html_pdf/storage_analysis.py \
  app/reports/export/html_pdf/builder.py \
  tests/contracts/reports/test_storage_analysis_context_boundary_contract.py
git commit -m "refactor(reports): use Storage publication context boundary #38"
```

### Task 6: Reconcile only scanner-proven Storage debt and run full branch verification

**Files:**
- Modify only when scanner explicitly reports resolved/stale entries: `docs/architecture/code-health-debt-baseline.json`
- Test: all Storage contracts/regressions plus canonical KAORI quality gates.

**Interfaces:**
- Consumes final #38 implementation.
- Produces exact baseline with only currently existing debt and a branch head eligible for governed staging PR.

- [ ] **Step 1: Run exact code-health verifier without editing the baseline first**

```bash
python scripts/verify_code_health.py
```

Expected: FAIL only with Storage entries reported as `resolved ... debt; remove it from the baseline` or `stale ... debt entry; remove it from the baseline`; any new debt is an implementation defect and must be fixed before baseline changes.

- [ ] **Step 2: Remove only the exact Storage keys reported stale/resolved**

Edit `docs/architecture/code-health-debt-baseline.json` only for scanner-proven Storage entries. Keep defaults exactly `800 / 160 / 30 / 8` and do not increase `broad_exception_limit`.

- [ ] **Step 3: Verify code-health baseline integrity**

```bash
python scripts/verify_code_health.py
python scripts/verify_code_health_baseline_integrity.py
```

Expected: PASS.

- [ ] **Step 4: Run focused report tests**

```bash
pytest -q \
  tests/reports/test_storage_analysis_pdf_template.py \
  tests/contracts/reports/test_storage_analysis_context_boundary_contract.py \
  tests/contracts/reports/test_storage_html_pdf_code_health_contract.py \
  tests/contracts/reports/test_analytics_pdf_publication_v3_contract.py
```

Expected: PASS.

- [ ] **Step 5: Run format/static checks on changed Python**

```bash
ruff format --check \
  app/reports/export/html_pdf/storage_analysis.py \
  app/reports/export/html_pdf/storage \
  tests/contracts/reports/test_storage_analysis_context_boundary_contract.py \
  tests/contracts/reports/test_storage_html_pdf_code_health_contract.py
ruff check \
  app/reports/export/html_pdf/storage_analysis.py \
  app/reports/export/html_pdf/storage \
  tests/contracts/reports/test_storage_analysis_context_boundary_contract.py \
  tests/contracts/reports/test_storage_html_pdf_code_health_contract.py
pyright -p pyrightconfig.json
```

Expected: PASS.

- [ ] **Step 6: Run canonical architecture and final release verification**

```bash
python scripts/verify_architecture_boundaries.py
python scripts/verify_final_release.py --all
```

Expected: PASS.

- [ ] **Step 7: Commit exact-ledger reconciliation**

```bash
git add docs/architecture/code-health-debt-baseline.json
git commit -m "chore(ci): reconcile Storage code-health debt #38"
```

- [ ] **Step 8: Require full GitHub branch KAORI CI Admission on the exact final head**

Do not create the governed staging PR until the branch workflow reports final `KAORI CI Admission` PASS. If any job fails, diagnose the exact failing job/step and repair only the demonstrated cause.

### Task 7: Governed staging integration and acceptance

**Files:**
- GitHub Issue #38 evidence/comments.
- Governed PR from `kaori/tech-38-storage-html-pdf-debt` to `kaori/staging`.

**Interfaces:**
- Consumes exact branch head with full Admission PASS.
- Produces accepted staging lineage eligible for Local Dev Container UAT and later main promotion.

- [ ] **Step 1: Open governed PR to `kaori/staging`**

Title:

```text
refactor(reports): burn down Storage Analysis HTML/PDF debt
```

Body must summarize scope, TDD evidence, exact scanner reconciliation, preserved nine-page/evidence contracts, verification, and relationships to #38/#35/#6. Do not put manual Project-field instructions in the PR body.

- [ ] **Step 2: Apply repository metadata available through GitHub**

Use assignee `lethisa` and labels `scope:ci`, `quality:reliability`, `quality:ux`, `area:reports`, `scope:backend`. Do not add a milestone unless an actual release target exists.

- [ ] **Step 3: Require structured review and PR CI**

No unresolved Critical/Important review finding; PR CI must report final KAORI CI Admission PASS on the exact PR head.

- [ ] **Step 4: Merge to `kaori/staging` and require post-merge Admission**

Record the exact merge SHA and require post-merge staging KAORI CI Admission PASS.

- [ ] **Step 5: Stop at exact Local Dev Container UAT when required**

Provide the exact accepted staging SHA. Do not reuse #36 UAT evidence or fabricate acceptance.

- [ ] **Step 6: After explicit UAT PASS, promote the exact accepted staging lineage to `main`**

Use the governed staging-to-main PR path, require promotion CI/review/no drift, merge with expected-head protection, then require post-main KAORI CI Admission PASS.

- [ ] **Step 7: Finalize #38 and only then activate #39**

Record final evidence, close #38 as completed, set Project Status `Done`, and leave #39 inactive until this lifecycle is complete.
