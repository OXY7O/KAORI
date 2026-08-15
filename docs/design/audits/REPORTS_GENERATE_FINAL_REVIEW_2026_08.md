# KAORI Reports Generate — Final Review (2026-08)

## Decision

Generate remains a published-contract workspace. A report type is not exposed until its scope contract, collector/exporter, renderer, and persistence boundary are available.

## Format policy

- Analytics reports: PDF is the governed human-readable default; CSV remains available for machine-readable evidence, downstream analysis, and audit extraction.
- Inventory reports: XLSX is the governed workbook default; CSV remains available for flat export and automation.
- Analytics does not add XLSX by default because it duplicates the CSV machine-readable contract without meaningful additional governance value.

## Object Storage gap

Object Storage evidence is ready, but Generate still persists Kubernetes scope through `cluster_id` and optional namespace. Publishing Object Storage report types before a provider-neutral asset-scope contract would create a false executable surface.

The first Object Storage report contracts should be:

1. Object Storage Inventory Report — XLSX + CSV.
2. Object Storage Analysis Report — PDF + CSV.

Before publication, add a provider-neutral report scope that can identify an Object Storage System and update request persistence, schedules, collectors, exporters, generated-report presentation, and report-reference metadata.

## Generate hierarchy

Hero → Report Contract → Infrastructure Scope → Artifact / Format Policy → Report Content → Review & Queue.

The workspace must remain compact and must not expose evidence-ready candidate reports as selectable Generate contracts.
