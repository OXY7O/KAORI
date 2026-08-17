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
- Every report and schedule requires one canonical infrastructure asset scope. Kubernetes reports use one selected cluster with optional namespace; Object Storage reports use one registered Object Storage system.
- Cross-cluster and default-cluster fallback behavior is prohibited.
- Generic artifact routes and lifecycle fields are format-neutral.

See `docs/reports/kaori-reporting-standard-v1.md` for the complete mandatory standard.

## Rules

Routes call subdomain services. Renderers do not read HTTP request state and do not query external systems. Collection occurs before rendering through the canonical selected-cluster payload path. System templates are catalog-derived; custom templates may only store sections and output formats allowed by their report type.

Long-running generation belongs in Celery. Storage and cleanup must reuse the cross-domain retention/archive foundation rather than implement report-only retention logic.

## KAORI Violet presentation standard

All report workspaces use the KAORI Violet Infrastructure design system: solid violet hero surfaces, tokenized card/background/border/text colors, compact rectangular status and metadata labels, violet focus/action states, and semantic colors only for operational state. This applies to Overview, Generate, Generated Reports and detail, Templates, Schedules, and Storage.

Artifact presentation is also standardized:

- Analytics PDF uses the shared Analytics publication component/style system with domain-specific publication templates where required.
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

## Reports Overview presentation contract

Reports Overview is the operational landing workspace for the Reports domain. It is full-width and does not use a secondary right sidebar. The hierarchy is fixed to:

1. Reporting Posture: the canonical KAORI hero owns page identity, infrastructure scope, artifact readiness, and two compact operational metrics.
2. Reporting Operational Posture: Reports worker/queue readiness, active schedules, artifact storage health, current generation demand, and resolved completion quality.
3. Report Coverage & Artifact Estate: publication coverage by infrastructure domain, retained artifact footprint/mix, output-contract boundaries, and reusable automation.

Generic helper callouts are avoided on the Overview. Operational interpretation uses `Operational Reading`, while export guidance is expressed as an `Output Contract` boundary. Planned Server/VM and HCI coverage is definition-owned in `app/definitions/catalogs/reports/coverage.yaml`; the Overview service must not embed future report catalogs as Python literals.

The Overview deliberately does not repeat the Generated Reports artifact registry. Artifact browsing, row-level status, file size, and report-detail actions remain owned by `Reports -> Generated Reports`.

Overview must not expose storage credentials, storage paths, retention configuration, cron definitions, or other configuration-level detail. Those remain owned by their dedicated Reports workspaces.

## Shared report-storage readiness and degraded mode

Report artifact storage readiness is one canonical, cross-process state shared by Overview, Generate, Generated Reports, Schedules, and Storage. Web processes must not maintain independent long-lived truth for S3/MinIO connectivity.

The readiness lifecycle is:

1. Celery Beat dispatches `app.reports.storage.tasks.refresh_report_storage_readiness_task` on the maintenance queue every `REPORT_STORAGE_HEALTH_INTERVAL_MINUTES` (default: 1 minute).
2. The periodic task performs a lightweight connectivity/readiness probe (`head_bucket` for S3-compatible storage) and publishes a sanitized state to Redis.
3. Shared readiness includes `checked_at`, source, age/staleness metadata, backend state, and read/write availability. The Redis key is configuration-fingerprinted so stale state from a previous endpoint/bucket/credential configuration cannot be reused after configuration changes.
4. Manual **Verify Storage** remains the strong validation path: an explicit CSRF-protected POST connects, writes a temporary verification object, confirms it exists, deletes it, then publishes the resulting shared state immediately. GET requests never execute this write path.
5. Artifact read/write failures publish an immediate unavailable state so all Reports pages converge on degraded mode without waiting for the next periodic probe.
6. If Redis/shared state is unavailable or stale, request-time probing remains the fail-safe fallback; the short process cache is only a request-load optimization, not the canonical multi-process state.

Default monitor settings:

- `REPORT_STORAGE_HEALTH_MONITOR_ENABLED=true`
- `REPORT_STORAGE_HEALTH_INTERVAL_MINUTES=1`
- `REPORT_STORAGE_HEALTH_STALE_SECONDS=120`
- `REPORT_STORAGE_HEALTH_STATE_TTL_SECONDS=600`
- `REPORT_STORAGE_HEALTH_CELERY_QUEUE=maintenance`

S3/MinIO unavailability degrades artifact capabilities; it does **not** make the complete Reports domain unavailable:

- **Overview:** remains available and shows a degraded storage incident with last-check evidence and Storage actions.
- **Generate:** remains readable, but new report creation is disabled in the UI and rejected server-side before a `Report` record is created when artifact storage cannot accept writes.
- **Generated Reports / detail:** database registry and metadata remain available. Download availability is evaluated per artifact/backend, so historical local artifacts are not disabled merely because the active S3 backend is unavailable.
- **Templates:** remain available because template/catalog management does not require artifact storage.
- **Schedules:** definitions and history remain available. **Run Now** and due artifact execution are paused/fail-closed before creating a report artifact request while storage is unavailable.
- **Storage:** remains available for active-backend diagnostics, metadata-first artifact-reference coverage, retained-reference integrity, and strong manual verification. Generated Report retention eligibility, archive storage, cleanup execution, scheduling, and archive history remain exclusively owned by Platform Operations → Data Lifecycle.

Raw S3 exceptions, access keys, secret keys, tokens, and credential values are never written into the shared readiness payload or rendered in Reports UI. Technical exceptions remain server-side evidence.


## Notification delivery

Scheduled Reports use Integrations → Notification Channels. Schedules store selected channel IDs only; provider credentials and transport behavior remain owned by the shared notification integration. Legacy report-specific Telegram environment credentials are not supported.
