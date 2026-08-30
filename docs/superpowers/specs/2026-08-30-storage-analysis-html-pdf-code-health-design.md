# Storage Analysis HTML/PDF Code-Health Refactor Design

**Date:** 2026-08-30  
**Issue:** #38  
**Parent:** #35  
**Governance parent:** #6  
**Predecessor:** #36  
**Branch:** `kaori/tech-38-storage-html-pdf-debt`  
**Base:** `kaori/staging@8005c20520ba9e3eb66a089cc5419917e0906ad9`  
**Status:** In-chat architecture approved; written specification pending final user review before implementation planning.

## 1. Purpose

Reduce Storage Analysis HTML/PDF code-health debt into cohesive Storage-owned modules while preserving the accepted Storage publication contract, nine-page PDF structure, template-facing presentation shape, evidence semantics, rendering behavior, and KAORI delivery gates.

This is a structural refactor. It is not a report redesign. It must not change the report schema, Jinja template contract, WeasyPrint renderer, Analytics publication standard, typography, spacing, chart/table meaning, recommendation semantics, data-source authority, or accepted decision wording except where an existing regression test demonstrates a defect that is separately admitted to scope.

## 2. Current Debt Boundary

The active #38 debt boundary is:

- module line debt: `app/reports/export/html_pdf/storage_analysis.py` = approximately `1210` lines;
- function line debt: `build_storage_analysis_presentation` = approximately `472` lines;
- function branch debt: `build_storage_analysis_presentation` = approximately `57` branch points;
- current entrypoint signature carries `11` arguments; exact argument-ledger reconciliation is permitted only if the canonical scanner proves the corresponding entry stale/resolved after the caller boundary is safely narrowed.

The global code-health defaults remain fixed:

- module lines: `800`;
- function lines: `160`;
- branch points: `30`;
- arguments: `8`.

No threshold increase, broad-exception increase, variadic wrapper, metric-only file shuffle, dead compatibility shim, or renamed oversized catch-all module is permitted.

## 3. Existing Publication Contract

### 3.1 Page and section order

Storage Analysis remains a governed Analytics publication with exactly nine pages/section contracts in this order:

1. Cover
2. Executive Brief
3. Capacity
4. Filesystem
5. Persistent Storage
6. Risk
7. Trend
8. Recommendations
9. Methodology and Evidence Boundary

The final presentation mapping retains these top-level section keys:

- `cover`;
- `executive`;
- `capacity`;
- `filesystem`;
- `persistent`;
- `risk`;
- `trend`;
- `recommendations`;
- `methodology`.

Publication metadata remains compatible with `v3.0-storage-analysis-publication`, the shared Analytics publication standard, `reports/pdf/storage_analysis.html`, `storage_analysis.css`, and the existing Jinja/WeasyPrint rendering path.

### 3.2 Evidence semantics that must not drift

- Missing aggregate filesystem evidence stays explicit `Not Available` and never becomes `0% used`, `100% headroom`, or `Normal`.
- Aggregate capacity and localized filesystem risk remain separate evidence boundaries.
- PV/PVC inventory count does not imply filesystem utilization.
- PVC utilization remains unavailable when pressure/usage evidence is unavailable.
- PV lifecycle state and claim-binding risk remain explicit and retain their existing severity/tone semantics.
- StorageClass expansion support remains unknown unless positive committed evidence exists; it is never inferred from PV/PVC counts or storage class names.
- Missing trend/forecast evidence remains unavailable; no synthetic historical or forecast line may be generated.
- Committed payload evidence remains authoritative during report rendering; no live Prometheus/Kubernetes fallback is introduced.
- Recommendation/risk output remains advisory and does not authorize expansion, cleanup, migration, or local-volume remediation by itself.
- Threshold interpretation remains Normal below 70%, Warning from 70% to 84.9%, and Critical at 85% or above.

### 3.3 Existing behavioral characterization

`tests/reports/test_storage_analysis_pdf_template.py` is the primary Storage behavioral lock and must remain green. It already covers representative full-evidence and degraded-evidence states, including:

- canonical Storage template and nine-page publication contract;
- committed aggregate capacity values and normalized percentages;
- explicit missing filesystem evidence;
- PV/PVC inventory-versus-utilization separation;
- no synthesized trend when forecast evidence is absent;
- methodology/source tables and single-line register behavior;
- exact nine-page A4 WeasyPrint output.

Relevant shared Analytics publication contracts remain additive protection and are not replaced by #38 structural tests.

## 4. Caller and Compatibility Boundary

Repository inspection shows the production Storage presentation call is controlled by `app/reports/export/html_pdf/builder.py`. The builder already creates `ReportDocumentContext` before dispatching by report type.

Current Storage call shape passes `report`, `payload`, and nine publication metadata arguments. The `report` object is not required as a supported external publication API merely because it appears in the internal function signature.

Preferred repository-internal boundary, subject to the implementation-time full call-surface audit, is:

```python
build_storage_analysis_presentation(
    payload,
    *,
    context: ReportDocumentContext,
    classification: str,
)
```

This mirrors the accepted Capacity and Object Storage builder boundary and uses the existing canonical context instead of creating another metadata container.

The module path and symbol `app.reports.export.html_pdf.storage_analysis.build_storage_analysis_presentation` remain recognizable. The external KAORI report-generation API, report type `storage_analysis`, builder routing, template name, artifact contract, and report schema do not change.

If a real supported caller outside the builder is discovered during the complete call-surface audit, preserve an intentional compatibility boundary and leave any unavoidable argument debt visible rather than hiding it with `*args`, `**kwargs`, duplicate metadata wrappers, or a threshold exception increase.

## 5. Chosen Architecture

Use a Storage-local package, following the proven Capacity ownership pattern without introducing a generic cross-report framework.

```text
app/reports/export/html_pdf/
├── storage_analysis.py
└── storage/
    ├── __init__.py
    ├── model.py
    ├── records.py
    ├── trend.py
    ├── actions.py
    └── sections.py
```

`storage_analysis.py` becomes a thin facade/orchestrator. Shared publication utilities that already exist, such as `count_donut_svg`, remain shared; #38 does not create a Storage chart module unless implementation evidence shows genuinely Storage-owned SVG logic that cannot remain a small direct dependency.

No new generic HTML/PDF abstraction is introduced in #38. Capacity and Storage may demonstrate similar shapes, but semantic reuse is promoted only when identical behavior is proven rather than inferred from naming similarity.

## 6. Module Responsibilities

### 6.1 `storage_analysis.py`

Role: stable report-family facade and high-level orchestration.

Responsibilities:

- expose `build_storage_analysis_presentation` under the existing module path;
- receive committed payload plus canonical `ReportDocumentContext` when caller audit permits;
- invoke Storage-local state, record, trend, action, and section builders;
- assemble publication metadata and the final top-level presentation mapping;
- retain only small orchestration logic.

Non-responsibilities:

- no raw payload normalization loops;
- no filesystem/PV/PVC record loops;
- no large risk/recommendation construction;
- no trend normalization details;
- no multi-page section dictionaries assembled inline.

Target: module below 800 lines; main presentation function below 160 lines and 30 branch points.

### 6.2 `storage/model.py`

Role: low-level Storage input normalization and canonical Storage-local state primitives.

Owns:

- safe mapping/sequence/number/text conversion where the behavior is Storage-local;
- threshold/status/tone helpers used consistently by Storage evidence;
- raw cluster/storage/filesystem/persistent partitions from the committed payload;
- normalized raw row collections for filesystem, PV, and PVC evidence;
- small immutable/internal state objects where they reduce argument fan-out and clarify dependencies;
- node/source identity primitives that logically belong to Storage input state.

It must not construct full Jinja page dictionaries, recommendations, risk registers, or renderer output.

### 6.3 `storage/records.py`

Role: normalized capacity and storage-record evidence.

Owns:

- aggregate capacity resource derivation;
- filesystem records and localized risk counts;
- PV summary and PV records;
- PVC summary and PVC records;
- binding coverage;
- explicit expansion-evidence availability;
- record sorting and display normalization;
- small record-level risk label/tone interpretation.

Inventory, utilization, expansion, and lifecycle evidence remain distinct. This module must not convert unavailable evidence into healthy defaults.

### 6.4 `storage/trend.py`

Role: Storage historical and forecast evidence semantics.

Owns:

- Storage forecast item selection from committed forecast payload;
- historical/projected percentage extraction;
- trend availability and method labels;
- projection/status/tone derivation;
- chart SVG/string state already produced by the current Storage implementation, if any;
- trend interpretation and trend register data.

When history or forecast evidence is absent, returned state must preserve the current explicit unavailable behavior and an empty chart string where the current template expects it.

### 6.5 `storage/actions.py`

Role: findings, risk, recommendation, ownership, and operational-decision evidence derived from normalized Storage state.

Owns:

- recommendation-card normalization;
- executive findings;
- risk register rows;
- recommendation plan;
- owner selection/summary;
- actionable counts;
- executive/risk/recommendation interpretation helpers;
- validation and governance decision data that is not page-layout specific.

This module must not render HTML or infer authorization for operational changes.

### 6.6 `storage/sections.py`

Role: final page-facing contract assembly.

Owns focused builders for:

- cover;
- executive brief;
- capacity;
- filesystem;
- persistent storage;
- risk;
- trend;
- recommendations;
- methodology/evidence boundary.

Each builder receives small normalized state objects/mappings and returns the same mapping/tuple semantics already consumed by `storage_analysis.html`. Section builders may use existing shared publication helpers such as `count_donut_svg`; they must not re-read the raw payload when normalized state already exists.

No single section builder may become a replacement 400-line presentation function.

## 7. Dependency Direction

Allowed direction:

```text
builder.py
  -> storage_analysis.py
       -> storage.model
       -> storage.records
       -> storage.trend
       -> storage.actions
       -> storage.sections

storage.records  -> storage.model
storage.trend    -> storage.model
storage.actions  -> storage.model / storage.records / storage.trend
storage.sections -> storage.model / storage.records / storage.trend / storage.actions
```

Disallowed:

- Storage package modules importing the facade;
- circular imports between model, records, trend, actions, and sections;
- `sections.py` re-normalizing the raw payload;
- `actions.py` importing Jinja/templates/renderers;
- a generic shared report framework created solely to reduce metrics;
- metric-only relocation into another oversized module.

## 8. Data Flow

1. `builder.py` creates the existing `ReportDocumentContext` and selects `storage_analysis`.
2. `storage_analysis.py` receives the committed report payload and canonical context.
3. `model.py` normalizes the payload partitions and raw row collections.
4. `records.py` derives aggregate capacity, filesystem evidence, PV/PVC summaries, lifecycle/binding state, and explicit expansion availability.
5. `trend.py` derives historical/forecast availability, projections, chart state, and interpretation without synthesizing missing evidence.
6. `actions.py` derives findings, risks, recommendations, owners, actionable counts, and governance decision evidence.
7. `sections.py` builds the nine template-facing page mappings from normalized state.
8. The facade assembles the unchanged top-level presentation mapping and publication metadata.
9. The existing Storage Jinja template and WeasyPrint path render the artifact.

No stage performs live source lookup or silently substitutes another evidence source.

## 9. TDD and Implementation Strategy

Implementation follows characterized RED/GREEN checkpoints.

### Characterization checkpoint

Before structural extraction, run the existing Storage PDF/template suite and relevant Analytics publication contracts on the branch base. The representative full-evidence, missing-filesystem, missing-persistent, and missing-forecast states are the behavioral reference.

Where current behavior is not sufficiently asserted for a helper that will move, add characterization assertions before extraction. Characterization tests must encode accepted observable behavior, not implementation details.

### RED 1 — context/caller boundary

Add a focused structural contract analogous to the accepted Capacity context contract. It should prove the intended repository-internal signature and builder call shape only after the complete call-surface audit shows the builder-controlled boundary is safe.

This test must fail against the pre-refactor Storage implementation.

### RED 2 — ownership/decomposition boundary

Add a focused code-health/ownership contract asserting:

- Storage-local package modules exist;
- `storage_analysis.py` remains the facade;
- record/trend/action/section ownership is delegated to focused modules;
- Storage package modules do not import the facade;
- no fake/dead references are retained solely to satisfy source-based tests.

This must fail before extraction.

### GREEN 1 — input and record normalization

Move low-level normalization and filesystem/PV/PVC evidence logic first. Keep final presentation output unchanged and rerun Storage characterization tests.

### GREEN 2 — trend extraction

Move committed trend/forecast semantics while preserving explicit absence, projection meaning, and chart state. Rerun Storage characterization tests.

### GREEN 3 — action/risk extraction

Move findings, risk registers, recommendation cards/plans, owner derivation, and related interpretation. Rerun Storage characterization tests.

### GREEN 4 — section decomposition and facade reduction

Move page-facing mapping construction into focused section builders. Reduce the facade and main presentation function below default ceilings without changing page order or template keys.

### GREEN 5 — canonical context boundary

When the caller audit remains clean, update `builder.py` to pass `payload + ReportDocumentContext + classification`. Remove the unused report/metadata fan-out from the Storage entrypoint. Do not introduce a second metadata wrapper.

### Exact-ledger reconciliation

Run the canonical code-health scanner after the implementation is behaviorally green. Remove or lower only Storage entries the scanner explicitly reports stale/resolved. Candidate debt is the current Storage module/function/branch/argument boundary, but the baseline is never edited in anticipation of success.

## 10. Verification Matrix

At meaningful GREEN checkpoints:

- focused Storage structural/context contracts;
- `tests/reports/test_storage_analysis_pdf_template.py`;
- relevant Analytics publication contracts that include Storage;
- Ruff format/check on changed Python files;
- Pyright using the repository configuration when the checkpoint reaches normal Static validation.

Before PR integration:

- canonical exact code-health verifier;
- code-health baseline-integrity verifier;
- architecture/import-boundary verification;
- complete report regression coverage applicable to Storage;
- full KAORI CI Admission on the final branch head;
- governed PR to `kaori/staging`;
- structured review with no unresolved Critical/Important finding;
- PR CI Admission;
- post-merge staging Admission;
- exact Local Dev Container UAT on the accepted staging SHA when required by the #35/#38 lifecycle;
- governed staging-to-main promotion and post-main verification before #38 reaches `Done`.

No custom verification script or weakened gate is introduced.

## 11. Behavioral Acceptance Lock

The refactor is rejected if any of these occur:

- page count changes from nine;
- section order or top-level template keys change;
- missing filesystem/PV/PVC/trend evidence becomes a synthesized zero, healthy, or available state;
- inventory is treated as utilization evidence;
- expansion support is inferred without committed positive evidence;
- threshold, risk, recommendation, owner, or decision semantics drift unintentionally;
- committed source authority is replaced by a live fallback;
- template or WeasyPrint geometry changes unexpectedly;
- Storage report generation no longer routes through the normal builder/template path;
- a new Storage module exceeds 800 lines without explicit scanner-governed justification;
- a targeted function exceeds 160 lines or 30 branch points without explicitly retained debt;
- broad exception count increases;
- argument debt is hidden with variadic or duplicate compatibility wrappers;
- default code-health thresholds, DAST/security checks, or release gates are weakened.

## 12. Expected Completion State

On successful completion of #38:

- `storage_analysis.py` is a focused facade below the 800-line module ceiling;
- Storage normalization, records, trend, action, and section ownership are separated into cohesive modules;
- no new Storage module exceeds the default module ceiling;
- targeted Storage functions remain below the 160-line and 30-branch ceilings;
- the Storage presentation entrypoint is at or below the 8-argument ceiling when caller audit proves the canonical context migration safe, otherwise any real compatibility debt remains explicit;
- the nine-page Storage publication is behaviorally unchanged and regression-protected;
- only scanner-proven Storage debt is removed from the exact baseline;
- branch, PR, staging, UAT, main-promotion, and post-main gates complete before #38 reaches `Done`;
- #39 remains inactive until #38 is fully complete.
