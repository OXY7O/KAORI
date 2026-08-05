# Reports domain

Reports orchestrates report configuration, selected-cluster validation, source collection, artifact generation, storage, scheduling, delivery, and generated-report lifecycle.

## Subdomains

- `overview/`: reporting coverage and readiness.
- `generate/`: request use cases and contract validation.
- `generated/`: generated report listing and generic artifact actions.
- `report_templates/`: system and custom template management.
- `export/`: shared contracts, collectors, document/profile models, and renderers.
- `schedules/`: schedule definitions and execution controls.
- `storage/`: artifact storage status and operations.

## Canonical contract

`app/reports/catalog.py` is the single source of truth.

- Analytics: PDF or CSV; PDF is the default.
- Inventory: XLSX or CSV; XLSX is the default.
- Every report and schedule requires one selected Kubernetes cluster.
- Cross-cluster and default-cluster fallback behavior is prohibited.
- Generic artifact routes and lifecycle fields are format-neutral.

See `docs/reports/kaori-reporting-standard-v1.md` for the complete mandatory standard.

## Rules

Routes call subdomain services. Renderers do not read HTTP request state and do not query external systems. Collection occurs before rendering through the canonical selected-cluster payload path. System templates are catalog-derived; custom templates may only store sections and output formats allowed by their report type.

Long-running generation belongs in Celery. Storage and cleanup must reuse the cross-domain retention/archive foundation rather than implement report-only retention logic.

## KAORI Violet presentation standard

All report workspaces use the KAORI Violet Infrastructure design system: solid violet hero surfaces, tokenized card/background/border/text colors, compact rectangular status and metadata labels, violet focus/action states, and semantic colors only for operational state. This applies to Overview, Generate, Generated Reports and detail, Templates, Schedules, and Storage.

Artifact presentation is also standardized:

- Analytics PDF uses the shared Analytics publication component and stylesheet.
- Inventory XLSX uses the reusable three-sheet workbook contract.
- Analytics and Inventory CSV use one canonical CSV standard and shared source models.

## Renderer architecture

The artifact registry in `app/reports/export/artifacts.py` resolves exactly one renderer from the validated format.

- `app/reports/export/html_pdf/`: Analytics document model, presentation normalization, chart SVGs, and canonical WeasyPrint engine.
- `app/reports/export/xlsx/`: Inventory workbook profiles, style primitives, and workbook builder.
- `app/reports/export/csv/`: canonical CSV standard and family dispatcher.
- `app/reports/export/inventory_common.py`: shared Inventory collection context and row normalization used by XLSX and CSV.
- `app/reports/export/payloads/`: selected-cluster source collectors.
- `app/reports/storage/naming.py`: selected-cluster object-key and extension rules.

Rendering failures are logged with technical evidence and returned to users as sanitized operational feedback. KAORI does not switch to another report type, cluster, format, or renderer after validation.

## Worker runtime contract

`app/reports/jobs/queue.py` owns the Reports queue name. Both artifact generation and schedule dispatch resolve `REPORTS_CELERY_QUEUE` through this module before creating a canonical `JobExecution`. The Dev Container and production Compose definitions each run `reports-worker` with hostname `reports@%h` and the same queue environment variable.

`app/common/celery_queue_health.py` owns the shared, cached Celery topology inspection used by Reports, Retention, and the Activity Deck. Report pages must never render a static worker-ready state. Worker liveness is presentation evidence; business tasks remain owned by Celery workers and never execute inside HTTP requests.
