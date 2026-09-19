# Capacity Analysis HTML/PDF Code-Health Refactor Design

**Date:** 2026-08-30  
**Issue:** #36  
**Parent:** #35  
**Governance parent:** #6  
**Branch:** `kaori/tech-36-capacity-html-pdf-debt`  
**Base:** `kaori/staging@76c7657abac2dadee91f3868ee15c71d86c7e3a2`  
**Status:** In-chat architecture approved; written specification pending final review before implementation planning.

## 1. Purpose

Reduce the Capacity Analysis HTML/PDF code-health debt without changing the published Capacity report contract, accepted nine-page PDF structure, template-facing presentation shape, evidence semantics, or KAORI release gates.

This work is a structural refactor. It is not a report redesign and it must not change the report schema, renderer engine, publication standard, visual language, source semantics, or accepted decision text except where an existing regression test proves an implementation defect that is explicitly admitted to scope.

## 2. Current Debt Boundary

The exact code-health baseline currently records four Capacity-specific exceptions:

- module line debt: `app/reports/export/html_pdf/capacity_analysis.py` = `1255` lines;
- function line debt: `build_capacity_analysis_presentation` = `475` lines;
- function branch debt: `build_capacity_analysis_presentation` = `77` branch points;
- function argument debt: `build_capacity_analysis_presentation` = `11` arguments.

The global defaults remain fixed and are not negotiable in this work:

- module lines: `800`;
- function lines: `160`;
- branch points: `30`;
- arguments: `8`.

The broad-exception baseline is not increased by this work.

## 3. Existing Publication Contract

### 3.1 External report behavior

Capacity Analysis remains a governed Analytics publication with exactly nine pages:

1. Cover
2. Executive Brief
3. Compute Capacity
4. Scheduling Capacity
5. Storage Capacity
6. Capacity Forecast
7. Capacity Risk Register
8. Recommendation Plan
9. Methodology and Evidence Boundary

The report remains rendered by the existing Jinja/WeasyPrint path and continues to use `reports/pdf/capacity_analysis.html` with the existing isolated Capacity stylesheet and shared Analytics publication stylesheet.

### 3.2 Template-facing presentation shape

The presentation dictionary consumed by the template must retain its established top-level contract, including at minimum:

- publication metadata and layout contract;
- `cover`;
- `executive`;
- `compute`;
- `scheduling`;
- `storage`;
- `forecast`;
- `risks`;
- `recommendations`;
- methodology/evidence data used by the final page.

Nested keys already asserted by regression tests or consumed by the template must remain compatible. Internal typed models may be introduced, but the final Jinja-facing payload remains ordinary mapping/sequence data with the same semantics.

### 3.3 Evidence semantics that must not drift

- Missing storage evidence remains explicitly unavailable and must never become `0% used`, `100% headroom`, or a healthy/normal state.
- Available storage evidence preserves the existing unit, percentage, and headroom interpretation.
- Forecast absence remains an explicit unavailable state.
- Forecast thresholds, projection assessment, and recommendation semantics remain unchanged.
- Node readiness/participation remains based on the committed cut-off evidence.
- Allocation, risk, recommendation, source, and methodology rows retain their current ordering and meaning.

### 3.4 Existing behavioral regression protection

`tests/reports/test_capacity_analysis_pdf_template.py` remains the primary behavioral characterization suite. It already protects:

- nine-page publication and A4 page count;
- publication/layout contract values;
- missing-storage behavior;
- available-storage behavior;
- methodology table separation and single-line behavior;
- node-participation SVG behavior;
- forecast SVG font/label behavior;
- explicit forecast-unavailable behavior;
- isolated stylesheet behavior.

These tests are not replaced by structural tests. Structural tests only protect the new ownership boundary.

One existing test source-inspects `capacity_analysis.py` for `resolve_vertical_labels`. After chart ownership moves, that assertion must follow the real chart owner. The implementation must not retain a fake import, dead reference, or comment in the facade merely to satisfy a source-based test.

## 4. Chosen Architecture

Use a Capacity-local package and keep `capacity_analysis.py` as the stable report-family facade/orchestrator.

```text
app/reports/export/html_pdf/
├── capacity_analysis.py
└── capacity/
    ├── __init__.py
    ├── model.py
    ├── sections.py
    ├── forecast.py
    ├── actions.py
    └── charts.py
```

No generic HTML/PDF presentation framework is introduced in #36. Shared code across report families is deferred until at least two independently refactored report families demonstrate identical semantics.

## 5. Module Responsibilities

### 5.1 `capacity_analysis.py`

Role: compatibility facade and high-level orchestration only.

Responsibilities:

- accept the Capacity report payload through the builder-controlled entrypoint;
- obtain or receive canonical publication metadata/context;
- call Capacity-local normalization and section builders;
- assemble the final top-level presentation mapping;
- expose `build_capacity_analysis_presentation` under the existing module path.

Non-responsibilities:

- no SVG construction;
- no large risk/recommendation loops;
- no resource normalization details;
- no multi-page section dictionaries assembled inline;
- no duplicated publication metadata model.

Target: well below the 800-line module ceiling; `build_capacity_analysis_presentation` below 160 lines and 30 branch points.

### 5.2 `capacity/model.py`

Role: Capacity-specific normalization and derived state.

Owns cohesive primitives such as:

- safe mapping/sequence/number conversion where Capacity-specific ownership is appropriate;
- capacity resource normalization for CPU, memory, pods, and storage;
- allocation normalization;
- headroom/status/tone derivation;
- node counts and participation derivation;
- small metric/value formatting helpers that are genuinely Capacity-local;
- typed internal context/dataclasses where they reduce argument fan-out and clarify dependencies.

This module must not build Jinja page dictionaries or SVG markup.

### 5.3 `capacity/forecast.py`

Role: Capacity forecast semantics and forecast-section preparation.

Owns:

- forecast item normalization;
- historical/projected percentage extraction;
- projection status/tone;
- forecast rows;
- forecast availability/method selection;
- forecast interpretation;
- forecast-section data assembly, excluding raw SVG rendering.

It may depend on small model primitives and chart functions, but charts must not depend back on forecast orchestration.

### 5.4 `capacity/actions.py`

Role: decision/evidence registers derived from Capacity state.

Owns:

- executive findings;
- capacity risk rows;
- recommendation rows;
- priority normalization;
- owner summary;
- source/evidence rows;
- risk/recommendation interpretation helpers;
- methodology/action data that logically belongs to decision evidence rather than page layout.

This module must not render HTML or SVG.

### 5.5 `capacity/charts.py`

Role: pure Capacity SVG presentation helpers.

Owns:

- capacity forecast chart SVG;
- empty-forecast SVG;
- node participation donut SVG;
- chart-only geometry/label helpers;
- `resolve_vertical_labels` usage for Capacity forecast labels.

The module receives normalized values and returns SVG strings. It must not read the raw report payload or construct report sections.

### 5.6 `capacity/sections.py`

Role: final section contract assembly for the template.

Owns focused builders for:

- cover;
- executive brief;
- compute capacity;
- scheduling capacity;
- storage capacity;
- risk register;
- recommendation plan;
- methodology/evidence section.

Each section builder receives a small internal context/model and returns the same mapping/tuple shapes currently consumed by the template. No single section builder may become a replacement 400-line presentation function.

Forecast section assembly may remain in `forecast.py` because forecast normalization and the section are tightly coupled; `sections.py` orchestrates it through an explicit interface rather than duplicating forecast semantics.

## 6. Canonical Metadata / Argument-Debt Strategy

The refactor must not introduce a second publication metadata object when KAORI already has `ReportDocumentContext` in the HTML/PDF builder path.

Repository visibility check: `app/reports/export/html_pdf/__init__.py` does not export the Capacity presentation function. The supported product boundary remains the report-generation flow through `builder.py`. For #36, “stable entrypoint” therefore means the Capacity report type, builder routing, template name, module path, and function symbol remain recognizable; the repository-internal callable signature may be narrowed only after caller audit proves that no supported consumer depends on the current 11-argument form.

Preferred repository-internal call contract:

```python
build_capacity_analysis_presentation(
    payload,
    *,
    context: ReportDocumentContext,
    classification: str,
)
```

The central builder already owns `ReportDocumentContext`, and Object Storage already demonstrates context-based presentation construction. The implementation plan must validate the full repository call surface before changing the Capacity signature.

If the builder is the only controlled caller, update that internal call boundary and retire the 11-argument debt. If a real supported caller outside the builder depends on the current signature, preserve a deliberate compatibility boundary and keep any unavoidable argument debt visible rather than hiding it with `*args`, `**kwargs`, a dummy wrapper, or a baseline threshold increase.

The external KAORI report-generation API, report type, report schema, template name, and rendered artifact contract do not change.

## 7. Dependency Direction

Allowed dependency direction:

```text
builder.py
  -> capacity_analysis.py
       -> capacity.sections
       -> capacity.forecast
       -> capacity.actions
       -> capacity.model
       -> capacity.charts

capacity.sections -> capacity.model / capacity.actions / capacity.forecast / capacity.charts as needed
capacity.forecast -> capacity.model / capacity.charts
capacity.actions  -> capacity.model
capacity.charts   -> chart_labels + low-level standard helpers only
```

Disallowed:

- package modules importing the facade;
- `charts.py` importing section/action orchestration;
- generic shared HTML/PDF modules being created solely to reduce line counts;
- circular imports between model, actions, forecast, sections, and charts.

## 8. Data Flow

1. `builder.py` creates the existing `ReportDocumentContext` and selects Capacity Analysis.
2. `capacity_analysis.py` receives the committed payload plus canonical publication context.
3. `model.py` normalizes resources, allocations, node state, and small derived values.
4. `forecast.py` normalizes forecast evidence and derives projections/forecast section state.
5. `actions.py` derives risks, findings, recommendations, ownership, source rows, and methodology evidence.
6. `charts.py` renders SVG strings from normalized state only.
7. `sections.py` builds the page-facing section mappings.
8. The facade assembles the unchanged top-level presentation mapping.
9. The existing Jinja template and WeasyPrint pipeline render the same publication contract.

No stage silently substitutes live data for committed report payload evidence.

## 9. TDD Strategy

Implementation follows RED/GREEN/refactor checkpoints.

### RED 1 — structural ownership contract

Add a focused contract test asserting:

- Capacity-local package/modules exist;
- `capacity_analysis.py` remains the public facade;
- the facade delegates to focused normalization/section boundaries;
- large SVG bodies and large risk/recommendation loops are not retained in the facade;
- package modules do not import the facade.

This test must fail before extraction.

### GREEN 1 — model/context extraction

Move normalization/derived-state code first while keeping final presentation output unchanged. Run Capacity behavioral regression tests.

### GREEN 2 — chart extraction

Move forecast/node SVG generation and update the source-inspection regression to inspect the real chart owner. Run Capacity regression tests including WeasyPrint page count.

### GREEN 3 — action/evidence extraction

Move findings, risk, recommendations, owners, source rows, and related interpretation logic. Run Capacity regression tests.

### GREEN 4 — section decomposition and facade reduction

Move page-facing mapping construction into focused section builders. Reduce the facade and main presentation function below their default ceilings.

### GREEN 5 — argument debt

After repository call-surface verification, use canonical `ReportDocumentContext` at the builder boundary when safe and remove the 11-argument debt. Do not use variadic wrappers to game the metric.

### Ledger reconciliation

Run the canonical code-health verifier. Remove or lower only Capacity entries that the scanner explicitly reports stale/resolved. Expected candidate removals are the four current Capacity exceptions, but no baseline edit is made before fresh scanner evidence.

## 10. Verification Matrix

At each meaningful GREEN checkpoint:

- targeted structural contract;
- `tests/reports/test_capacity_analysis_pdf_template.py`;
- relevant Analytics publication-standard tests;
- Ruff check/format on changed Python files;
- Pyright through the canonical repository configuration where the checkpoint reaches the normal Static gate.

Before PR integration:

- exact code-health verifier and baseline-integrity verifier;
- architecture/import-boundary verification;
- full KAORI CI Admission on the final branch head;
- governed PR to `kaori/staging`;
- post-merge staging Admission;
- Local UAT / explicit acceptance before `Done`.

No custom verification script is introduced.

## 11. Behavioral Acceptance Lock

The refactor is rejected if any of the following occur:

- page count changes from nine;
- a template key disappears or changes meaning;
- missing evidence becomes an implicit zero/healthy state;
- forecast/risk/recommendation semantics change unintentionally;
- SVG/chart labels regress or collide;
- WeasyPrint page geometry changes;
- public report generation no longer resolves Capacity Analysis through the normal builder;
- a new module/function exceeds default code-health ceilings without an explicit, justified ledger entry;
- broad exception count increases;
- a source-inspection test is satisfied through dead/fake ownership evidence;
- default code-health thresholds or test/release gates are weakened.

## 12. Expected Completion State

On successful completion of #36:

- `capacity_analysis.py` is a focused compatibility/orchestration facade below 800 lines;
- no new Capacity module exceeds 800 lines;
- targeted Capacity functions are below 160 lines and 30 branch points;
- argument count is at or below 8 unless a real compatibility requirement is proven and explicitly retained;
- Capacity publication behavior is unchanged and regression-protected;
- scanner-proven Capacity debt is removed from the exact ledger;
- full branch and staging Admission pass;
- Local UAT is explicitly accepted before #36 reaches `Done`;
- learnings from #36 may inform #38 and later children, but no shared abstraction is promoted until reuse is demonstrated by at least two report families.
