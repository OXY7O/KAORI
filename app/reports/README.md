# Reports domain

Reports orchestrates report configuration, generation, rendering, storage,
scheduling, and generated-report lifecycle.

## Subdomains

- `overview/`: reporting coverage and readiness.
- `generate/`: generation use cases and input validation.
- `generated/`: generated report listing and actions.
- `report_templates/`: base and custom template management.
- `export/`: renderer and report sections.
- `schedules/`: schedule definitions and execution controls.
- `storage/`: report storage status and operations.

## Rules

Routes call subdomain services; PDF section code must not query HTTP request state.
Base templates remain protected and custom templates derive from a known base.
Long-running generation belongs in Celery. Storage and cleanup must reuse the
cross-domain retention/archive foundation rather than implement report-only
retention logic.
