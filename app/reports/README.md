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

- Analytics: PDF, XLSX, or CSV; PDF is the default.
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
- Analytics XLSX uses a category-owned executive workbook contract for drill-down, filtering, trends, and evidence review.
- Inventory XLSX uses the reusable executive inventory workbook contract.
- Analytics and Inventory CSV use one canonical CSV standard and shared source models.

## Renderer architecture

The artifact registry in `app/reports/export/artifacts.py` resolves exactly one renderer from the validated format.

- `app/reports/export/html_pdf/`: Analytics document model, presentation normalization, chart SVGs, and canonical WeasyPrint engine.
- `app/reports/export/xlsx/`: global XLSX presentation primitives plus separate Inventory and Analytics workbook families.
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
3. Reporting landscape and governance: two independent, vertically stacked cards. **Report Coverage & Artifact Estate** owns infrastructure-domain publication coverage, retained artifact footprint/mix and output-contract boundaries; **Contracts & Automation** owns published contract families, schedules and templates. Each card has its own shared `section_intro` title and short description above the card, with the existing card title retained for concrete workspace identity.

The shared `components/section_intro.html` macro owns the two outer section headings; neither page-local heading styling nor a competing reporting metric/contract source should be introduced. Planned Secrets & PKI copy stays definition-owned in `app/definitions/catalogs/reports/coverage.yaml` and must keep the distinction between planned/non-executable reports and admitted published contracts.

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


## Scheduled execution and delivery intent

A ReportSchedule occurrence is claimed under a database row lock before artifact generation is admitted. Failed unadmitted scheduled dispatch is eligible for bounded retry, while Run Now does not move the automatic cadence.

Each ReportScheduleRun captures selected Notification Channel identities on admission. The report worker uses this immutable selection after generation, including when the current schedule was edited or deleted. Shared Notification Channels still enforce send-time eligibility and event idempotency. Delivery outcomes remain separate from artifact generation success.

## Schedule registry read model

Schedule Registry applies search, status, cadence, published report type, infrastructure asset and channel filters in SQL before the canonical five-row pagination. Aggregate schedule counts use database counts, while dependency filter choices use compact identity-only queries. Run Schedule selection is capped to recent definitions with an explicit currently selected fallback; historical run text search remains available for older definitions.

The Schedule form initially loads only the selected Kubernetes cluster's current committed namespaces; switching clusters uses the permission-scoped `/reports/schedules/namespaces` endpoint and verifies the returned cluster identity before exposing choices. A failed namespace request does not claim that an empty inventory is authoritative. These bounded read paths do not query external providers or change the Generate contract.

## Notification delivery

Scheduled Reports use Integrations → Notification Channels. Schedules store selected channel IDs only; provider credentials and transport behavior remain owned by the shared notification integration. Legacy report-specific Telegram environment credentials are not supported.

### Reports Overview conservative runtime posture (#1530)

The Overview Hero posture comes from the same Reports queue-worker evidence and shared storage readiness consumed by Runtime Health. Storage unavailable takes precedence over queue unavailable/unknown, followed by historical failed requests. A missing worker/queue observation must never produce a Ready Hero; previously generated artifacts remain separately readable through their existing guarded routes. No new provider probe or report worker execution is owned by the Overview route.

### Reports Overview permission-aware navigation (#1531)

Overview is readable by `reports.view`, but links to Generate, Templates, Schedules, and Storage are displayed only for users with the corresponding existing target-route permissions. The Hero falls back to the readable Generated Reports registry when the user cannot access the relevant action. Server-side decorators remain authoritative; navigation never grants permissions. Legacy/partial operation payloads with no permission key are rendered without actionable links.

### Reports Overview bounded storage read path (#1532)

The landing page reads selected-backend shared storage readiness and never walks the local artifact file tree. Local readiness uses inexpensive path existence/writability checks; filesystem count/size scanning remains an opt-in diagnostic operation in the authorized Storage workspace. S3 readiness remains worker/Redis authoritative under the existing monitor and fallback guardrails. No provider mutation or new state cache is introduced.

### Reports Overview metric cohorts (#1533)

Requests This Month counts Report records whose created_at belongs to the half-open current **UTC calendar-month** interval [month start, next month start). Completion Rate is deliberately **all-time**, calculated from Ready + Archived as successful resolved requests over Ready + Archived + Failed; requested/generating records are not in this denominator. Empty resolved cohorts display unavailable (—), not a fabricated 100% or 0% success. UI copy names the distinct temporal cohorts; neither metric is a current-provider health signal.

### Generate invalid report type admission (#1541)

Generate distinguishes a UI catalog fallback from the submitted report type. Unknown, blank, and removed report type values are rejected during POST validation before scope queries or Report creation, even when the view normalizer can display a safe default report card. The canonical Reports catalog remains the only source of valid report types.

### Generate strict submitted sections and period (#1542)

GET navigation may display canonical default sections and period. On POST, analytics section selection must remain exactly the operator's requested values until server-side validation; missing/invalid sections are rejected, never silently rewritten to defaults. Inventory sections remain contract-locked and tampering fails closed. Analytics snapshot and Inventory time ranges are invalid, not silently converted. This boundary is enforced before Report/JobExecution persistence; the wizard remains advisory.

### Generate bounded namespace choices (#1543)

Reports Generate bootstraps current committed namespace choices for only the selected Kubernetes cluster. On cluster switch, its existing wizard requests an authorized lightweight `GET /reports/generate/namespaces?cluster_id=...` list with `reports.generate` permission, then renders options only when response cluster identity still matches selection. Object Storage and Registry report types do not query Kubernetes namespace inventory on page load; registered asset option lists remain available for the existing in-wizard contract switcher. The server independently validates namespace membership within the selected cluster before report persistence. No live provider request or custom cache architecture is introduced.

### Reports job integration ownership (#1544)

Canonical Report JobExecution `integration_type` and `integration_instance_id` come from the report's selected asset type: Kubernetes cluster → `kubernetes`, Object Storage system → `object_storage`, Registry IntegrationInstance → `registry` plus its numeric instance ID. Unknown future scope types must not be mislabeled as Kubernetes. The existing Report scope key, queue identity, idempotent resource group and renderer remain unchanged. Historical completed job evidence is not rewritten during this remediation.

### Generate report naming boundary (#1545)

Operator report names are optional, trimmed, and bounded at 255 Unicode code points before report persistence to match `Report.name`'s existing VARCHAR(255) contract. Over-limit names render actionable validation feedback. The wizard input uses the corresponding HTML maxlength as convenience only; server-side checks remain authoritative. No schema migration is necessary.

### Generated Reports concurrent archive admission (#1557)

Archive (single/bulk) and worker generation serialize against the Report row with the existing database transaction/row-lock contract. Archive rejects any report with an active canonical JobExecution for `report:<id>` even when its retained artifact makes the report lifecycle still `ready`. Bulk archive is atomic: any missing, ineligible, or active request rejects the entire selection with actionable counts. The worker rechecks archived lifecycle under a row lock after storage preflight and before committing `generating`, and failure cleanup never overwrites an archived record. The Registry reads one batched active-job query per page, not per row. Historical committed artifact and job evidence remain owned by the existing Reports/Platform Operations boundaries.

### Generated Reports artifact evidence honesty (#1556)

List pages remain metadata-first and must never treat a reachable backend plus retained storage URI as proof an individual artifact exists. Unprobed retained URIs are surfaced as **Artifact Referenced / Reference Not Verified**. The list may offer a protected download handoff when the reference is reachable; the download route and detail separately perform authoritative per-object probing, with unavailable/missing feedback. No per-row HEAD and no provider-live dependency is introduced into normal registry polling.

### Generated Reports Registry scope identity (#1555)

Registry's generic scope filter includes active IntegrationInstance Registry options through `get_active_registry_options()`, alongside Kubernetes and Object Storage. Each persisted report's immutable scope label snapshot remains authoritative for historical presentation even when an integration is unavailable; absent snapshots use a safe Registry Integration ID fallback without per-row provider or IntegrationInstance lookups. Registry rows/detail display `Artifact Registry` / `Integration Scope`, not Kubernetes/namespace metadata. Scope filters remain server-side committed SQL.

### Report Templates POST type/status admission (#1561)

Custom Template create and update preserve the submitted report type and lifecycle status until catalog validation. Unknown/missing type or status is rejected before database mutation and cannot be normalized into a different Analytics contract or draft template. UI form defaults remain distinct from submitted values; only the canonical Reports catalog determines supported types.

### Report Templates submitted section evidence (#1562)

Custom Template POST preserves Analytics section keys, including empty/invalid selections, until server validation rejects them. Inventory sections must exactly match the definition's fixed workbook contract. Initial GET defaults and operator-driven Reset Sections are presentation only; no unsupported or duplicate section can be committed under the current catalog. Generate admission remains separately authoritative.

### Historical custom Templates without catalog compatibility aliases (#1566)

The registry must remain readable if a persisted custom template references a removed report type, unsupported format, invalid sections or lifecycle status. Such records are presented with Needs Review evidence; Generate and Duplicate are guarded until corrected using current catalog types through the existing Edit workspace. Historical record identity, source snapshot and ownership are never silently rewritten or removed on registry read.

### Report Templates validation recovery (#1565)

Invalid custom-template create/edit submissions render the same existing native modal with submitted values and an accessible server-owned validation summary (`422`). No unbounded session or cross-user flash store is introduced; the safe registry query/pagination return boundary remains intact. Valid mutations still perform canonical feedback and redirect to the edited template. The externally owned form JavaScript under merged #394/#435 remains unchanged.

### Report Templates generation permission (#1564)

The Templates management workspace owns draft/active lifecycle and system/custom duplication. A Template manager may open Generate only if they independently have `reports.generate`; draft templates remain unavailable regardless of RBAC. The Generate route remains authoritative for admission and scope validation.

### Report Templates bounded registry query (#1563)

System templates remain definition-owned and first in the mixed registry. Custom template filtering, counting, and retrieval are database-side: shared KAORI pagination selects at most the current page size (default five) and a grouped type/status query supplies all-estate KPI counts without materializing the full custom estate. Search uses committed template metadata and catalog labels, not provider-live calls. No custom pagination abstraction is introduced.

### Storage unsupported backend fail-closed (#1593)

A blank backend defaults to local, but any nonempty unsupported REPORT_STORAGE_BACKEND remains unsupported. Its Storage workspace shows a degraded configuration and no new artifact may silently write to local. Historical stored URI access stays backend-specific.

### Storage handoff permission (#1599)

Reports Storage's Generated Reports link is visible only with destination `reports.view`; `reports.manage_storage` stays independent, and the destination RBAC remains authoritative.

### Process readiness fingerprint (#1597)

Process storage readiness cache keys use the canonical hashed configuration fingerprint from `storage/state.py`, including credential, S3 addressing and backend changes without exposing secrets. Stale cache identities can no longer be reused after a configuration change.

### Local footprint read performance (#1596)

Routine Reports Storage GETs only check local path availability and writability. The Local References card counts committed report metadata; physical filesystem footprint is not claimed or recursively re-enumerated from an HTTP request.

### Strong storage verification cleanup (#1598)

Strong worker verification uses a per-run random object key and records successful write, existence and confirmed deletion before marking the storage backend strongly verified. Cleanup is attempted even when provider probing fails; incomplete cleanup leaves storage write readiness degraded and must be reviewed in worker logs.

### Integrity Scan evidence contract (#1594)

Integrity results expose checked, available, missing, error and full reference population counts, with explicit partial/empty/unknown semantics. A 500-object scan is a bounded sample, never proof of full-estate integrity. The UI renders success only when every selected reference has actually been scanned without exceptions.

### Storage integrity scan worker ownership (#1595)

A bounded reference integrity scan is dispatched through canonical report-storage JobExecution and the existing maintenance worker queue. The HTTP route only creates/attaches a job; the worker owns per-artifact storage checks. The page reads committed job results with active/failed states and HTMX refresh, without live provider I/O from the browser. Strong write-confirm-delete verification remains separate.


### Cross-domain reporting evidence boundaries (2026-10-12, #1585)

- **Artifact Registry Analysis (#1605):** the Registry Operational Dashboard Fast Shell is only a navigation/readiness entry point. Report publication explicitly resolves existing scoped committed Overview, Capacity and Signals sections before normalizing the Analytics payload. If no inventory generation is committed, publication must report unavailable evidence rather than presenting default-zero inventory counts. PDF, XLSX and CSV consume the same Analytics collector; XLSX alert titles and summaries follow the canonical Alert Intelligence row fields.
- **Tenant Governance (#1607 and #1609):** report findings are selected by canonical cluster asset key; namespace-selected reports additionally constrain structured namespace or selected-Tenant identities. Capacity admission and audit events are filtered in SQL before the most-recent-250 source sample. The XLSX Governance worksheet retains at most 100 audit entries from that bounded payload; this is not a complete historical audit ledger. Keep source scope and explicit sampling provenance visible as methodology/evidence metadata.
- **Artifact Registry Inventory (#1612):** rows distinguish `entity_type` = project, repository, or artifact. Projects without repositories and repositories without artifacts remain visible with blank digest and artifact-only fields. Artifact counts continue to count real artifact rows only. Use the shared Inventory CSV/XLSX profile and never reuse the CSV control header `record_type` as a profile column.
- **Object Storage Analysis (#1613):** manual/scheduled report collectors pin exactly one committed Analytics snapshot for Overview, Performance and Alerts during a generation. They must not request provider metrics or enqueue materialization refresh as a side effect of artifact rendering. Snapshot expiry/missing data fails with explicit unavailable evidence; stale-but-usable evidence is flagged as stale with its own generated-at timestamp. The primary Analytics data cut-off comes from the committed Analytics generation, not current wall time or an unrelated inventory timestamp. Inventory and independent forecast cut-offs remain separately attributable.
- These boundaries are source requirements, not runtime UAT acceptance. Validate cross-format scope/value parity, negative states and real artifact fidelity in the controlled DevContainer before any staging promotion.


## Planned Secrets & PKI coverage (HV-15, #2694)

The definition-owned `secrets_pki` coverage domain lists six **Planned**
report candidates in `app/definitions/catalogs/reports/coverage.yaml`.
The Reports Overview uses the existing coverage projection; the Secrets & PKI
Operational Dashboard Reporting tab uses the same source-controlled candidates
only for actors with `reports.view`. This is **not** a report type in
`reports/catalog.yaml` and cannot be generated, scheduled, exported or
archived. Existing Reporting workers/renderers are unchanged.

No Vault path/name, Secret material, private key, AppRole SecretID, provider
token or unqualified per-source counts may appear in exports. Each future
executable report requires committed data, resource-scoped #724 authorization
enforced before counts and rows, report-specific collection/retention, Full
Admission, security checks and actual DevContainer/Vault UAT. Never treat
a planned candidate or a healthy Vault connection as a published report.
