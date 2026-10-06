# KAORI Reports Generate — Final Review (2026-08)

## Decision

Generate remains a published-contract workspace. A report type is exposed only after its scope contract, collector/exporter, renderer, persistence boundary, and worker handoff are available.

## Format policy

- Analytics reports: PDF is the governed human-readable default; CSV remains available for machine-readable evidence, downstream analysis, and audit extraction.
- Inventory reports: XLSX is the governed workbook default; CSV remains available for flat export and automation.
- Analytics does not add XLSX by default because it duplicates the CSV machine-readable contract without meaningful additional governance value.

The Generate workspace no longer repeats the global Analytics/Inventory format policy beside every request. The Artifact step uses one unified three-part contract surface: Output Format, Selected Artifact behavior, and Publication Contract. The selected-format explanation follows the operator's actual format choice, while Default and Allowed remain canonical report-contract metadata.

## Published Object Storage contracts

The provider-neutral report asset scope is implemented end to end. Generate publishes the first two Object Storage report contracts:

1. Object Storage Inventory Report — XLSX default, CSV alternative.
2. Object Storage Analysis Report — PDF default, CSV alternative.

Object Storage reports bind one registered Object Storage System. Kubernetes reports continue to bind one Kubernetes Cluster with an optional Namespace. Both are persisted through the canonical `scope_asset_type` / `scope_asset_id` boundary while legacy `cluster_id` / `namespace` remain available for backward compatibility.

## Generate hierarchy

Hero → Report Contract → Infrastructure Scope → Artifact Contract → Report Content → Review & Queue.

The scope control is contract-owned:

- Kubernetes report → Kubernetes Cluster + optional Namespace.
- Object Storage report → Object Storage System.

Only published contracts are selectable. Remaining Object Storage Forecast, Top Consumers, and Alerts & Anomalies coverage stays non-executable until each focused contract is separately published.

## Final UI and maintenance audit

The final polish locks these decisions:

- Report Type optgroups are generated from the canonical report catalog through `report_type_groups`; the Jinja template does not hardcode Kubernetes/Object Storage or Analytics/Inventory group loops.
- Inventory content is displayed as **Locked**, not **Selected**, because workbook sections are contract-owned and cannot be modified by the operator.
- Analytics content remains operator-selectable and uses **Selected** semantics.
- Review & Queue treats worker availability as asynchronous execution context, not queue-admission eligibility. A disconnected worker is surfaced by the dedicated warning above the workspace; it is not duplicated as a blocking readiness badge.
- Queue admission is governed by infrastructure scope, content validity, and artifact-storage write readiness. Worker recovery determines when an admitted request starts processing.
- The selected report summary and final Review & Queue serve different purposes: the former confirms catalog identity while configuring; the latter confirms the concrete request that will be persisted and queued.

## Definition Registry boundary

System-owned report contracts and worker definitions remain Definition Registry data. Static contracts must validate canonical YAML plus the Python adapter/registry boundary rather than requiring definition literals to be copied back into Python modules.

## Final visual refinement

The final composition removes the narrow Artifact-versus-wide-Content split. Artifact output is a compact full-width contract row, Report Content owns its own full-width section, and Review & Queue uses four equal request-summary dimensions: Report, Scope, Output, and Content. This keeps the sequential 01–05 workflow while avoiding nested cards, narrow explanatory panels, and unused horizontal space.

The Artifact Contract now uses one unified bordered surface with three desktop columns:

1. **Output Format** — the operator selects one allowed format.
2. **Selected Artifact** — explains the behavior of the format actually selected (PDF publication, XLSX workbook, or CSV export).
3. **Publication Contract** — shows the canonical Default and Allowed formats for the report type.

This removes the previous long horizontal explanation and floating right-side badges. Selected-format behavior and contract metadata no longer compete for the same line.

## Migration graph alignment

`20260815_report_asset_scope` is rebased onto `20260814_obj_storage_rbac`, the current preceding head in the cumulative KAORI migration graph. This is intentional because the report asset-scope revision had not been applied: `flask db upgrade` stopped on the multiple-head condition before executing the revision. Reparenting the unapplied revision restores a single linear head without introducing a permanent merge-only migration.
