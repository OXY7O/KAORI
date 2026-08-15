# KAORI Reports Generate — Final Review (2026-08)

## Decision

Generate remains a published-contract workspace. A report type is exposed only after its scope contract, collector/exporter, renderer, persistence boundary, and worker handoff are available.

## Format policy

- Analytics reports: PDF is the governed human-readable default; CSV remains available for machine-readable evidence, downstream analysis, and audit extraction.
- Inventory reports: XLSX is the governed workbook default; CSV remains available for flat export and automation.
- Analytics does not add XLSX by default because it duplicates the CSV machine-readable contract without meaningful additional governance value.

## Published Object Storage contracts

The provider-neutral report asset scope is now implemented end to end. Generate publishes the first two Object Storage report contracts:

1. Object Storage Inventory Report — XLSX default, CSV alternative.
2. Object Storage Analysis Report — PDF default, CSV alternative.

Object Storage reports bind one registered Object Storage System. Kubernetes reports continue to bind one Kubernetes Cluster with an optional Namespace. Both are persisted through the canonical `scope_asset_type` / `scope_asset_id` boundary while legacy `cluster_id` / `namespace` remain available for backward compatibility.

## Generate hierarchy

Hero → Report Contract → Infrastructure Scope → Artifact / Format Policy → Report Content → Review & Queue.

The scope control is contract-owned:

- Kubernetes report → Kubernetes Cluster + optional Namespace.
- Object Storage report → Object Storage System.

Only published contracts are selectable. Remaining Object Storage Forecast, Top Consumers, and Alerts & Anomalies coverage stays non-executable until each focused contract is separately published.
