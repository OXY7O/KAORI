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

## KAORI Violet presentation standard

All report workspaces use the KAORI Violet Infrastructure design system: solid violet hero surfaces, tokenized card/background/border/text colors, compact rectangular status and metadata labels, violet focus/action states, and semantic colors only for operational state. This applies to Overview, Generate, Generated Reports and detail, Templates, Schedules, and Storage. Presentation changes must not alter report generation, lifecycle, scheduling, retention, or storage behavior.

## PDF renderer architecture

KAORI uses one canonical PDF engine: Jinja HTML, dedicated print CSS, and WeasyPrint. The existing Report Template System remains the source of truth for report type, section order, scope, schedule, storage, and retention.

The renderer reuses prepared real-data payload collectors and never performs HTTP or Prometheus queries from Jinja templates. Selected sections are rendered in the exact order stored by the current system or custom template. Rendering failures are logged with technical evidence and returned to users as sanitized operational feedback; KAORI does not switch to a second PDF engine.

PDF-specific source lives under:

- `app/reports/export/html_pdf/`: document model, payload normalization, chart SVGs, and the canonical WeasyPrint engine.
- `app/reports/export/formatting.py`: renderer-neutral filename and period formatting.
- `app/templates/reports/pdf/`: Jinja PDF document template.
- `app/static/reports/pdf/`: dedicated print CSS tokens and layout.
