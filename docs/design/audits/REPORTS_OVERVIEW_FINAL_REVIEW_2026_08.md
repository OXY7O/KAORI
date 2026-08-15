# Reports Overview — Full Review & Audit (2026-08)

## Decision

Reports Overview is the operational landing workspace for the Reports domain. It summarizes generation readiness, artifact estate, publication coverage, and reusable automation. It does not become an artifact registry, scheduler editor, template editor, storage configuration screen, or product-roadmap page.

The active hierarchy is intentionally limited to three layers:

1. Canonical KAORI Hero — page identity, infrastructure scope, artifact-storage boundary, reporting-domain count, and artifact readiness.
2. Reporting Operational Posture — worker/queue readiness, active schedules, storage health, generation demand, completion quality, and a compact storage incident when degraded.
3. Report Coverage & Artifact Estate — reporting-domain publication state, retained artifact footprint, output contract, published report families, schedules, and reusable templates.

## Audit findings

### 1. Object Storage was missing from the active Overview

Object Storage Inventory and Object Storage Analytics already provide committed and qualified evidence, but the Reports Overview rendered only Analytics/Inventory report families. The service built infrastructure-domain coverage separately and the active page never displayed it.

Object Storage is now a first-class reporting domain with the status **Evidence Ready**. This is deliberately not `Published` or `Available`: KAORI has committed Object Storage inventory/analytics evidence, but no canonical Object Storage report contract/renderer has been admitted to the Generate workflow yet.

The reporting-domain states are now explicit:

- Kubernetes — **Published**
- Object Storage — **Evidence Ready**
- Server & VM — **Planned**
- HCI — **Reserved**

### 2. Report family and report domain were conflated

`Analytics` and `Inventory` are report families. `Kubernetes`, `Object Storage`, `Server & VM`, and `HCI` are infrastructure/reporting domains. The previous active page exposed only family cards, which made cross-domain coverage invisible.

The page now presents both dimensions separately:

- Reporting Domain Coverage — publication/admission state by infrastructure domain.
- Published Contract Families — executable Analytics and Inventory family counts/formats.

### 3. Candidate definitions were too easy to read as executable contracts

Planned/reserved coverage definitions are product definitions, not Generate contracts. The Overview now uses these terms consistently:

- **Published** — selectable by the governed Generate workflow.
- **Evidence Ready** — qualified evidence exists, but no report contract/renderer is published.
- **Planned** — intended future coverage; not executable.
- **Reserved** — namespace/product boundary retained without an active delivery commitment.

The active published-contract count therefore excludes Object Storage candidate definitions, Server/VM plans, and HCI reservations.

### 4. Overview performed unnecessary legacy work

The redesigned page uses only runtime health, report counts, storage readiness, artifact statistics, report coverage, and worker readiness. The service previously still loaded notification-delivery and legacy pipeline/context payloads even though the active template no longer rendered them.

`get_reports_overview_payload()` now loads only state used by the active landing page. Legacy builders remain available for rolling-deployment compatibility and older presentation contracts but are no longer executed on every Overview request.

### 5. Artifact estate and capability needed a clearer hierarchy

The old `Artifact Estate & Report Capability` block mixed retained artifacts, report families, schedules, templates, and future domain coverage without making publication state visible.

It is now `Report Coverage & Artifact Estate` with three internal concerns:

1. Reporting Domain Coverage.
2. Artifact Estate.
3. Contracts & Automation.

This keeps the number of page-level surfaces small while making domain ownership explicit.

### 6. Hero needed to signal multi-domain reporting

The Hero remains provider-neutral and now surfaces the number of reporting domains rather than a generic `Governed Artifact Lifecycle` label. Artifact storage remains a separate boundary because report output storage must not be confused with Object Storage as a source/reporting domain.

## Object Storage boundary

Object Storage has two distinct meanings in Reports and must remain explicit:

- **Object Storage reporting domain** — committed Object Storage Inventory and qualified Analytics evidence that can feed future reports.
- **S3-compatible artifact storage** — the backend where generated report files may be retained.

They are not the same capability. Reports Overview keeps them in separate visual and data boundaries.

## Candidate Object Storage report coverage

The Definition Registry now records candidate Object Storage report coverage without making it executable:

- Object Storage Inventory Report
- Object Storage Capacity Analysis Report
- Object Storage Forecast Report
- Object Storage Top Consumers Report
- Object Storage Alerts & Anomalies Report

Publishing any of these later requires a canonical report type, allowed output contract, renderer/export implementation, authorization/scope contract, tests, and Generate integration. Adding a YAML candidate alone must never make a report executable.

## Ownership boundary

- Reports Overview: readiness, domain publication coverage, artifact estate, aggregate activity, and published capability.
- Generate: request composition and published report-contract selection.
- Generated Reports: artifact registry, retained status, download/archive lifecycle.
- Templates: protected and custom reusable structures.
- Schedules: recurring report definitions and execution history.
- Storage: artifact backend readiness, integrity, retention, and configuration.
- Object Storage Inventory / Analytics: source evidence ownership for the Object Storage reporting domain.

## Definition boundary

Executable report types and output formats remain in `reports/catalog.yaml`. Non-published domain coverage belongs in `reports/coverage.yaml`. The Reports catalog validates status/tone and exposes definition objects to the service; Jinja never reads YAML directly.

The current Object Storage state is therefore intentionally:

```text
Object Storage evidence
        ↓
Inventory + Analytics ready
        ↓
Report coverage definition: Evidence Ready
        ↓
NO executable Generate contract yet
```

This prevents product coverage from bypassing the governed report publication boundary.

## Artifact Estate visual refinement

The first multi-domain pass made Reporting Domain Coverage substantially denser than the Artifact Estate column. When the retained estate was empty, the right side collapsed into a footprint value, two short family rows, three isolated format tiles, and a large unused vertical area. That imbalance made the block look unfinished even though the data contract was correct.

Artifact Estate now uses one consistent vertical hierarchy:

1. **Estate Snapshot** — retained artifact count and stored footprint share one equal-width surface.
2. **Estate Distribution** — Artifact Families and Output Formats use parallel bordered lists rather than unrelated tile styles.
3. **Output Contract** — family-owned output formats and the candidate-domain publication gate are shown as explicit contract rows at the bottom of the column.

The column is a full-height flex surface, so the Output Contract remains anchored to the lower rhythm when Reporting Domain Coverage is taller. This preserves visual balance without inventing additional statistics or changing report runtime semantics.

The refinement also removes page-local arbitrary `text-[11px]` utilities. Reports Overview now uses the canonical KAORI typography scale and therefore does not require an exception in the UI style-debt baseline.
