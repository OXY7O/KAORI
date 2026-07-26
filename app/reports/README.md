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

KAORI keeps the existing Report Template System as the source of truth for report type, section order, scope, schedule, storage, and retention. PDF rendering is selected through `REPORT_PDF_RENDERER`:

- `weasyprint` (default): Jinja HTML + dedicated print CSS + WeasyPrint.
- `reportlab`: legacy renderer retained for controlled rollback.

When `REPORT_PDF_LEGACY_FALLBACK_ENABLED=true`, a WeasyPrint rendering failure is logged with technical evidence and the same report request is rendered through ReportLab. User-facing report errors remain sanitized.

The WeasyPrint renderer reuses the existing real-data payload collectors and never performs HTTP or Prometheus queries from Jinja templates. Selected sections are rendered in the exact order stored by the current system or custom template.

PDF-specific source lives under:

- `app/reports/export/html_pdf/`: document model, payload normalization, chart SVGs, and rendering engine.
- `app/templates/reports/pdf/`: Jinja PDF document template.
- `app/static/reports/pdf/`: dedicated print CSS tokens and layout.
- `app/reports/export/renderers/`: renderer selection and ReportLab fallback.
