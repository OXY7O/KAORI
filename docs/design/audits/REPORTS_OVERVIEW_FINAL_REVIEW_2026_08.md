# Reports Overview — Final Review (2026-08)

## Decision

Reports Overview remains the operational landing workspace for the Reports domain. It is not an artifact registry, scheduler configuration page, template editor, or storage configuration page.

The final hierarchy is intentionally compact:

1. Canonical KAORI Hero — page identity, infrastructure scope, storage boundary, and artifact readiness.
2. Reporting Operational Posture — worker/queue readiness, active schedules, storage health, generation demand, completion quality, and a compact storage incident when degraded.
3. Artifact Estate & Report Capability — retained artifact footprint, output distribution, schedules/templates, and canonical report-family capability.

## Audit findings and changes

- The H1 `Reports` was ambiguous for a domain landing page. It is now `Reports Overview`.
- Hero descriptions across the Reports workspaces were too terse. They now carry one additional operational clause without becoming paragraph-length copy.
- The Overview used generic `Performance Tip` and `Format Tip` callouts. These are now explicit `Operational Reading` and `Output Contract` boundaries.
- Planned Server/VM and HCI report coverage was embedded as Python list literals in the Overview service. It is now source-controlled in `app/definitions/catalogs/reports/coverage.yaml` and consumed through the Reports catalog adapter.
- The existing two-block full-width layout is retained. Adding more page-level cards would duplicate Generated Reports, Schedules, Templates, or Storage ownership.
- Storage degradation remains non-blocking for the Overview. The page stays readable and routes operators to the Storage workspace while artifact mutation remains fail-closed elsewhere.

## Ownership boundary

- Reports Overview: readiness, estate, aggregate activity, and capability.
- Generate: request composition and report contract selection.
- Generated Reports: artifact registry, retained status, download/archive lifecycle.
- Templates: protected and custom reusable structures.
- Schedules: recurring report definitions and execution history.
- Storage: backend readiness, integrity, retention, and configuration.

## Definition boundary

Executable report types and output formats remain in `reports/catalog.yaml`. Planned/reserved future coverage belongs in `reports/coverage.yaml` so future product planning does not create executable report contracts accidentally.
