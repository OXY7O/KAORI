# Jobs & Executions

`app/platform_operations/jobs` is KAORI's canonical orchestration domain for background work. It owns job registration, scheduling policy, admission, `JobExecution` lifecycle, configuration UI, and worker/queue visibility. It does not own domain business logic.

## Canonical Flow

```text
Manual action / generic scheduler
→ registered JobDefinition
→ domain permission and scope resolution
→ canonical JobExecution create-or-attach
→ Celery queue
→ domain executor
→ progress, result, and terminal lifecycle
```

Every supported manual or scheduled operation must create or attach to a canonical `JobExecution`. Routes and scheduler code must never call a Celery domain task directly.

## Structure

- `registry.py` exposes the static job catalog.
- `definitions/` adapts registered jobs to their owning domains.
- `policies/` owns generic interval policy persistence and validation. Cron support requires an explicit scheduler extension before any definition may select it.
- `scheduler.py` claims due `JobPolicy` rows with database locks.
- `dispatcher.py` provides canonical dispatch and create-or-attach behavior.
- `routes.py` owns `/jobs/executions` and `/jobs/configuration`.
- `presentation.py` builds execution registry and queue views.
- `configuration.py` builds the job catalog and selected definition workspace.

## Ownership Boundary

The job domain may import a public domain dispatcher, but domain execution remains in its owner:

- Kubernetes inventory collection: `app.inventory` / `app.kubernetes.cluster`
- report generation: `app.reports`
- analytics materialization: `app.analytics`
- lifecycle archive: `app.platform_operations.data_lifecycle.retention`

Do not move collectors, report builders, analytics processors, or retention adapters into `app.platform_operations.jobs`.

## Registered Jobs

The Job Configuration catalog is a **two-row navigation list**:
each entry shows its icon, job name and current status on the first row,
with interval, queue and Active/Idle state on the second. The domain and
description are not repeated in the scroll list; selected-job details
remain authoritative. Search retains the full `JobDefinition.description`
and domain/queue terms, while HTMX selection, URL history, independent
scroll, and pinned boundary Guide footer are unchanged. The dynamic visible/total
job count belongs to the search header, not the navigation footer. Jobs and Data
Lifecycle reuse the same one-line Execution Boundary label, adjacent Guide
(prefers opening above), and permission-gated Jobs & Executions navigation
with its full accessible destination label. Neither footer scrolls horizontally;
the full canonical boundary remains in the Guide.

Report Schedule Dispatch lists committed notification destinations as compact,
status-labelled rows with bounded keyboard-scrollable overflow. Guarded
Object Storage / Registry empty-inventory recovery uses the shared Violet
section-header surface while preserving visible warning context and the
full canonical safety Guide. These changes are presentation-only; recovery
authorization, the CONFIRM EMPTY challenge and the two-read fail-closed
boundary remain in their owning domain.

The first registered definition is `kubernetes.inventory.sync`:

- queue: `inventory`
- scope: `kubernetes_fleet:all`
- schedule: enabled by default every 60 minutes
- manual execution: supported
- domain execution permission: `clusters.sync`
- deduplication group: `kubernetes-inventory:global`

Additional jobs must be added through a new definition rather than a parallel scheduler or settings page.


Object Storage inventory is registered as `object_storage.inventory.sync`:

- queue: `inventory`
- scope: `object-storage-inventory:global`
- schedule: enabled by default every 60 minutes
- manual execution: supported
- domain execution permission: `storage.sync`
- manual authorization: `jobs.execute` + `storage.sync`
- deduplication group: `object-storage-inventory:global`

The Object Storage executor remains owned by `app.storage.object_storage.inventory`. It resolves the provider through the integration registry and may pass a domain progress callback to `inventory.sync`; `app.platform_operations.jobs` owns orchestration and lifecycle only.


Artifact Registry uses independent registered jobs rather than one monolithic Harbor synchronization:

- `artifact_registry.inventory.sync` — Projects, Repositories, Artifacts, and Tags; default 60 minutes.
- `artifact_registry.security.sync` — incremental vulnerability/signature/SBOM evidence; default 60 minutes.
- `artifact_registry.governance.sync` — retention/immutability/webhook/replication evidence; default 360 minutes.
- `artifact_registry.runtime_correlation.materialize` — DB-only Registry ↔ current Kubernetes inventory materialization; default 60 minutes.
- `artifact_registry.analytics.materialize` — committed analytics materialization on `analytics-batch`.

The first four jobs currently use the existing `inventory` queue and remain independently deduplicated.
Global **Sync All Inventory** dispatches `artifact_registry.inventory.sync` only. Heavy security evidence must
not extend the inventory correctness path; Harbor vulnerability detail is refreshed only for new/changed scan evidence.

## Shared Kubernetes Schedule Policy UI

The approved **Kubernetes Inventory Sync** policy is the presentation baseline
for scheduled Jobs. The canonical Jinja macro file
`app/templates/platform_operations/jobs/configuration/_schedule_policy.html`
owns the Violet policy header/status, accessible scheduled switch, bounded
interval input and validation, optional scheduler timeline and Save Policy
footer. Normal scheduled domains import the same macros. Vault KV v2, public issuer
and stored certificate schedules also use this component without relaxing
mount approval, public-only evidence, source limits or the RBAC boundary.
Analytics and Forecast use the same switch and interval primitives while
retaining freshness, stale fallback and precomputed time-range controls.
Vault Alert Source uses the shared manual-only header, without an automatic
scheduler switch. Domain-specific recovery, report-delivery choices,
provider eligibility and policy values remain in their owning templates/services.

This is **presentation reuse**, not a new scheduler or policy authority.
CSRF, per-job configure permission, disabled fields, canonical JobPolicy,
HTMX target and persisted scheduling decisions retain existing ownership.
Manual-only tasks must not be given a misleading scheduler switch.

## Compact Job Configuration Evidence

Jobs → Configuration uses the existing `_job_overview.html` and
`_execution_activity.html` to keep long safety summaries readable.
For Vault/PKI and selected Object Storage Analytics jobs, the visible
one-line synopsis is **presentation-only**; the existing canonical
`JobDefinition.description`, `safety_summary`, result evidence,
and provider-owned policy remain unchanged. A single canonical KAORI Info Tip **Guide beside the selected job title**
exposes the complete safety context to keyboard, touch and pointer users,
including approved mounts, metadata-only collection, HMAC custody,
PKI coverage limitations and committed snapshot/fail-closed behavior.
The compact summary footer remains readable without a second Guide button.
Current Execution process/detail and Registry Analytics safety can use
single-line responsive previews, but original committed values remain in
the HTML and complete safety details remain in the title Guide.
The application must never infer eligibility or success from abbreviated copy.

Vault policy forms now reuse consistent Violet icon/toggle/interval cards,
operator helper text and a scheduler note beside Save Policy. Registry Security
and Governance policy footers use the same read-only scheduler explanation.
These are presentation-only changes: existing CSRF fields, permissions,
schedule-enabled controls and interval constraints remain authoritative.
Analytics refresh and stale-grace inputs likewise preserve their canonical semantics.

## Job Configuration UI Reuse and Evidence Density

The Job Configuration sidebar follows the approved Data Lifecycle footer
pattern: `Execution Boundary`, a canonical Info Tip Guide, a current
catalog result count and a permission-gated `Open Jobs & Executions` link.
Catalog filtering, HTMX selection, history and independent list scroll remain
local to the sidebar; runtime state and attempts are authoritative in Jobs.

Guarded Empty Inventory reconciliation (Object Storage and Artifact Registry)
keeps the Guide adjacent to its title while displaying the original independent
verification requirement and two-read fail-closed safety. The `CONFIRM EMPTY`
phrase, target selector, CSRF, permission checks and provider-owned discovery
logic must never be bypassed for a presentation-only update.

Execution scope values may be truncated visually, but the complete committed
label is retained in the accessible HTML title. GitHub Repository Sync presents
a short synopsis while retaining the original admission and incomplete-scan
safety evidence in the canonical selected-job title Guide.

Report Schedule Dispatcher delivery channels use a bounded, responsive,
scrollable grid over the existing committed channel collection. Header count
and empty state come from the same collection, and no live provider request
or delivery mutation is performed by rendering it.

## Guarded Empty-Inventory Recovery UI

Object Storage and Artifact Registry expose **manual-only**, permission-gated
reconciliation when a previously nonempty committed inventory appears empty.
Their Job Configuration sections use shared KAORI operational-card and Info Tip
Guide patterns: a prominent Guarded Recovery header, target selector, explicit
`CONFIRM EMPTY` phrase and visible fail-closed boundary. Provider-specific
safety details remain readable in the Guide. Compact operator copy must not
remove the independently verified removal prerequisite, last-good snapshot
protection, two complete discovery checks, binding to the authenticated actor,
selected target and current committed snapshot, or fail-closed behavior.

The Guide is read-only and does not authorize an operation. All confirmations,
CSRF, role/domain permissions, source verification and provider-owned discovery
remain enforced by existing routes and domain services.

## RBAC

- `jobs.view`: view executions, queues, and configuration catalog.
- `jobs.execute`: manually dispatch registered jobs.
- `jobs.configure`: update automatic job policies.
- `jobs.cancel`: request cancellation for eligible executions.

A definition may require an additional domain permission. Inventory Sync requires both `jobs.execute` and `clusters.sync` for manual execution.

## Scheduler

Celery Beat runs `app.platform_operations.jobs.tasks.dispatch_scheduled_jobs` every minute on the maintenance queue. The task claims due `job_policies` rows with `FOR UPDATE SKIP LOCKED`, advances the next due time, and dispatches through the registry. Policy changes do not require a Beat restart.

A pre-dispatch failure marks the claimed policy failed and makes it eligible for a **bounded five-minute retry**, but only if no concurrent policy edit replaced the original claim. This does not bypass the canonical active-job deduplication guard or the definition's source-owned freshness contract. When the job has already been dispatched, the automatic queued AuditEvent and JobPolicy outcome are persisted in one transaction. If evidence persistence fails, Jobs records a best-effort `evidence_failed`/ **Dispatch Evidence Incomplete** attention state without automatically dispatching a duplicate; operators should review the committed JobExecution before further action.

Cancellation and recovery use the same committed job state. If Celery cannot accept a revoke, KAORI retains a pending cancellation and its deduplication slot; reconciliation continues with other jobs and retries the pending cancellation later. A late worker progress callback cannot mutate terminal or cancel-requested JobExecution evidence.

## Analytics Definitions

The registry includes `analytics.materialize`, `analytics.forecast.materialize`, `object_storage.analytics.materialize`, and `object_storage.forecast.materialize`. These definitions use database-backed `JobPolicy`, canonical `JobExecution`, worker-specific queues, shared deduplication, and Activity Audit records for automatic runs. Kubernetes and Object Storage operational analytics use the `analytics-batch` queue, while both forecast definitions use the dedicated `forecasting` queue and retain separate domain artifacts and eligibility contracts. Scheduled jobs have no user subscriber and therefore do not produce notification-center items or toasts.

Analytics and Forecast policies are freshness-aware. A due policy check may complete with `current` and create no `JobExecution` when every configured snapshot is still reusable. This avoids periodic Metrics Source queries that do not improve the data served to users.

### TLS Certificate Sync

`governance.tls_certificates.sync` refreshes Kubernetes TLS Secret certificate inventory through the
existing inventory worker. It defaults to a six-hour database-backed interval, supports manual execution,
and uses the same canonical deduplication and terminal audit behavior as other registered jobs. The owning
domain permission is `tls_certificates.sync`. User-facing execution, Notification Deck, cancellation, and automatic-audit labels resolve from the registered definition name, so the acronym remains **TLS Certificate Sync** rather than being reconstructed as `Tls Certificate Sync`.

## Job Progress Contract

All asynchronous job progress uses one canonical `JobExecution` progress contract and one shared UI renderer.
Domain workers keep `progress_current` / `progress_total` for completed work-item counts, while the reserved
`payload_json._progress` namespace carries a smooth 0–100 percentage plus the current stage and target.
This avoids overloading resource counts just to make a progress bar move.

Workers should report progress at meaningful boundaries only: stage transitions, resource-group boundaries,
or coarse percentage changes. High-cardinality collectors must not commit one `JobExecution` update per
individual object. Object Storage therefore reports bucket-level progress with percentage throttling, while
Kubernetes reports resource-family stages inside each cluster. Terminal success always normalizes progress
to 100%.

The shared `components/progress_bar.html::job_progress` renderer is the only progress presentation for
Jobs & Executions, Job Configuration, Activity Center, report execution details, and other JobExecution-backed
surfaces. Domain-specific progress toasts may wrap the same low-level violet bar primitive, but must not
introduce a second visual or percentage contract.

## Execution Registry Detail Contract

The Registry **View Details** modal reads only a sanitized committed `JobExecution` snapshot via
`present_job_execution_detail()`. The existing shared Resource Detail controller owns the
modal header, summary, focus/close actions, scrolling and loading/error states; the fragment
must declare `data-kaori-detail-variant="job-execution"` so the controller projects those
sections rather than duplicating a second title and leaving the loading placeholder visible.

The outcome-first operator view prioritizes status, real progress, last worker stage and
conditional recorded error evidence. To avoid dense side-by-side label/value walls, the
primary content uses one quiet **resource sheet**: four owner/scope facts, three committed
lifecycle milestones, and a responsive sanitized result-evidence fact grid. Secondary scope
attributes, timestamps and technical identifiers remain available through the existing,
keyboard-accessible **View More / View Less** disclosure; they are not discarded.
An absent result summary is an explicit empty state, not an execution failure.
Raw job request payloads, deduplication keys and parameter fingerprints are never displayed.
Scheduler/queue/provider authorities remain unchanged by this presentation contract.

## Operations UI Performance Contract

Jobs & Executions is intentionally server-backed and demand-loaded. The page must not build hidden workspaces merely to support client-side tab switching.

- The parent **Executions** and **Job Configuration** workspaces use server-owned navigation; only the selected workspace is built on a request.
- Execution **Active Work**, **Registry**, and **Queues** are demand-loaded. Registry pagination never triggers Celery topology inspection, and queue inspection runs only when the Queues view is opened.
- **Queues** lists registered JobDefinition queue names together with committed JobExecution queue history. A registered queue appears even before its first job so unavailable/unverified workers are visible; zero history does not prove a healthy worker. Live topology is inspected only on the Queues view.
- Global execution counters come from one conditional aggregate query. Queue activity comes from one grouped aggregate query plus one short-lived shared Celery topology snapshot.
- Active Work polls every 15 seconds and carries the overview counters in the same response. Registry and Queues use one compact overview heartbeat every 30 seconds.
- Job Configuration has no idle polling; active execution status refreshes every 10 seconds.
- Browser-hidden tabs do not poll. Active Work therefore has one 15-second heartbeat instead of overlapping 15-second and 30-second refresh loops. While a selected job is active, a lightweight execution-only status poll runs every 10 seconds; domain eligibility/readiness is rebuilt once when the execution becomes terminal.
- Active Work OOB counter fragments are emitted only by HTMX fragment responses. The initial full-page render must never append those response helpers as visible inline content.
- Active Work, Registry, and Queues use the canonical KAORI empty-state component so healthy zero work, filtered no-results, and initial no-data conditions keep one visual grammar.
- Terminal JobExecution history remains bounded by **Platform Operations → Data Lifecycle**. The Jobs page is the hot operational registry, not a replacement archive browser.

## Vault Alert Source Observation (HV-12, #2802)

`secrets_pki.vault_alerts.observe` is a source-owned **manual-only**
registered job for approved Vault/Alertmanager evidence. It reuses canonical
Jobs & Executions admission, `inventory` Celery queue, current shared
Execution & Recent Activity UX and operator audit. `default_enabled=false`
and `schedule_supported=false` mean no persisted policy edit or Celery
Beat scheduler can activate automatic polling. Run Now requires `jobs.execute`
and `secrets_pki.sync`. Validation, worker-only stable HMAC custody and real
DevContainer UAT are prerequisites to declaring the job operational.

Only opaque, five-minute correlation snapshots are committed; the result
summary contains sanitized source counters. This job does **not** create,
recover, resolve, route or send AlertCases. See
`app/secrets_pki/TELEMETRY_BINDING.md` for exact source-identity,
redaction and replay restrictions.

### Source Control repository sync (SC-03 candidate)

`source_control.repository.sync` reuses the `inventory` worker and the standard database-backed `JobPolicy` / `JobExecution` lifecycle. The policy is disabled by default; manual execution is blocked pending #724 resource-scoped authorization. Only admitted GitHub App installations with Ready validation can be scanned. At most 25 installation IDs, never tokens, cross the queue boundary. Signed webhook delivery is retained in a separate committed inbox; its after-commit handoff links the canonical JobExecution without claiming the delivery completed. No webhook ingress endpoint is enabled by this increment.


The first registered definition is `kubernetes.inventory.sync`:

- queue: `inventory`
- scope: `kubernetes_fleet:all`
- schedule: enabled by default every 60 minutes
- manual execution: supported
- domain execution permission: `clusters.sync`
- deduplication group: `kubernetes-inventory:global`

Additional jobs must be added through a new definition rather than a parallel scheduler or settings page.


Object Storage inventory is registered as `object_storage.inventory.sync`:

- queue: `inventory`
- scope: `object-storage-inventory:global`
- schedule: enabled by default every 60 minutes
- manual execution: supported
- domain execution permission: `storage.sync`
- manual authorization: `jobs.execute` + `storage.sync`
- deduplication group: `object-storage-inventory:global`

The Object Storage executor remains owned by `app.storage.object_storage.inventory`. It resolves the provider through the integration registry and may pass a domain progress callback to `inventory.sync`; `app.platform_operations.jobs` owns orchestration and lifecycle only.


Artifact Registry uses independent registered jobs rather than one monolithic Harbor synchronization:

- `artifact_registry.inventory.sync` — Projects, Repositories, Artifacts, and Tags; default 60 minutes.
- `artifact_registry.security.sync` — incremental vulnerability/signature/SBOM evidence; default 60 minutes.
- `artifact_registry.governance.sync` — retention/immutability/webhook/replication evidence; default 360 minutes.
- `artifact_registry.runtime_correlation.materialize` — DB-only Registry ↔ current Kubernetes inventory materialization; default 60 minutes.
- `artifact_registry.analytics.materialize` — committed analytics materialization on `analytics-batch`.

The first four jobs currently use the existing `inventory` queue and remain independently deduplicated.
Global **Sync All Inventory** dispatches `artifact_registry.inventory.sync` only. Heavy security evidence must
not extend the inventory correctness path; Harbor vulnerability detail is refreshed only for new/changed scan evidence.

## RBAC

- `jobs.view`: view executions, queues, and configuration catalog.
- `jobs.execute`: manually dispatch registered jobs.
- `jobs.configure`: update automatic job policies.
- `jobs.cancel`: request cancellation for eligible executions.

A definition may require an additional domain permission. Inventory Sync requires both `jobs.execute` and `clusters.sync` for manual execution.

## Scheduler

Celery Beat runs `app.platform_operations.jobs.tasks.dispatch_scheduled_jobs` every minute on the maintenance queue. The task claims due `job_policies` rows with `FOR UPDATE SKIP LOCKED`, advances the next due time, and dispatches through the registry. Policy changes do not require a Beat restart.

A pre-dispatch failure marks the claimed policy failed and makes it eligible for a **bounded five-minute retry**, but only if no concurrent policy edit replaced the original claim. This does not bypass the canonical active-job deduplication guard or the definition's source-owned freshness contract. When the job has already been dispatched, the automatic queued AuditEvent and JobPolicy outcome are persisted in one transaction. If evidence persistence fails, Jobs records a best-effort `evidence_failed`/ **Dispatch Evidence Incomplete** attention state without automatically dispatching a duplicate; operators should review the committed JobExecution before further action.

Cancellation and recovery use the same committed job state. If Celery cannot accept a revoke, KAORI retains a pending cancellation and its deduplication slot; reconciliation continues with other jobs and retries the pending cancellation later. A late worker progress callback cannot mutate terminal or cancel-requested JobExecution evidence.

## Analytics Definitions

The registry includes `analytics.materialize`, `analytics.forecast.materialize`, `object_storage.analytics.materialize`, and `object_storage.forecast.materialize`. These definitions use database-backed `JobPolicy`, canonical `JobExecution`, worker-specific queues, shared deduplication, and Activity Audit records for automatic runs. Kubernetes and Object Storage operational analytics use the `analytics-batch` queue, while both forecast definitions use the dedicated `forecasting` queue and retain separate domain artifacts and eligibility contracts. Scheduled jobs have no user subscriber and therefore do not produce notification-center items or toasts.

Analytics and Forecast policies are freshness-aware. A due policy check may complete with `current` and create no `JobExecution` when every configured snapshot is still reusable. This avoids periodic Metrics Source queries that do not improve the data served to users.

### TLS Certificate Sync

`governance.tls_certificates.sync` refreshes Kubernetes TLS Secret certificate inventory through the
existing inventory worker. It defaults to a six-hour database-backed interval, supports manual execution,
and uses the same canonical deduplication and terminal audit behavior as other registered jobs. The owning
domain permission is `tls_certificates.sync`. User-facing execution, Notification Deck, cancellation, and automatic-audit labels resolve from the registered definition name, so the acronym remains **TLS Certificate Sync** rather than being reconstructed as `Tls Certificate Sync`.

## Job Progress Contract

All asynchronous job progress uses one canonical `JobExecution` progress contract and one shared UI renderer.
Domain workers keep `progress_current` / `progress_total` for completed work-item counts, while the reserved
`payload_json._progress` namespace carries a smooth 0–100 percentage plus the current stage and target.
This avoids overloading resource counts just to make a progress bar move.

Workers should report progress at meaningful boundaries only: stage transitions, resource-group boundaries,
or coarse percentage changes. High-cardinality collectors must not commit one `JobExecution` update per
individual object. Object Storage therefore reports bucket-level progress with percentage throttling, while
Kubernetes reports resource-family stages inside each cluster. Terminal success always normalizes progress
to 100%.

The shared `components/progress_bar.html::job_progress` renderer is the only progress presentation for
Jobs & Executions, Job Configuration, Activity Center, report execution details, and other JobExecution-backed
surfaces. Domain-specific progress toasts may wrap the same low-level violet bar primitive, but must not
introduce a second visual or percentage contract.

## Operations UI Performance Contract

Jobs & Executions is intentionally server-backed and demand-loaded. The page must not build hidden workspaces merely to support client-side tab switching.

- The parent **Executions** and **Job Configuration** workspaces use server-owned navigation; only the selected workspace is built on a request.
- Execution **Active Work**, **Registry**, and **Queues** are demand-loaded. Registry pagination never triggers Celery topology inspection, and queue inspection runs only when the Queues view is opened.
- **Queues** lists registered JobDefinition queue names together with committed JobExecution queue history. A registered queue appears even before its first job so unavailable/unverified workers are visible; zero history does not prove a healthy worker. Live topology is inspected only on the Queues view.
- Global execution counters come from one conditional aggregate query. Queue activity comes from one grouped aggregate query plus one short-lived shared Celery topology snapshot.
- Active Work polls every 15 seconds and carries the overview counters in the same response. Registry and Queues use one compact overview heartbeat every 30 seconds.
- Job Configuration has no idle polling; active execution status refreshes every 10 seconds.
- Browser-hidden tabs do not poll. Active Work therefore has one 15-second heartbeat instead of overlapping 15-second and 30-second refresh loops. While a selected job is active, a lightweight execution-only status poll runs every 10 seconds; domain eligibility/readiness is rebuilt once when the execution becomes terminal.
- Active Work OOB counter fragments are emitted only by HTMX fragment responses. The initial full-page render must never append those response helpers as visible inline content.
- Active Work, Registry, and Queues use the canonical KAORI empty-state component so healthy zero work, filtered no-results, and initial no-data conditions keep one visual grammar.
- Terminal JobExecution history remains bounded by **Platform Operations → Data Lifecycle**. The Jobs page is the hot operational registry, not a replacement archive browser.
