# Platform Operations — Data Lifecycle

This package owns the KAORI **Data Lifecycle** operator workspace at `/platform-operations/data-lifecycle/`.

Ownership is intentionally split:

- `app/platform_operations/data_lifecycle/` owns HTTP routes, mutation orchestration, operator feedback, and workspace presentation.
- `app/platform_operations/data_lifecycle/retention/` remains the shared archive-first lifecycle engine, policy persistence layer, domain adapters, scheduling tasks, locking, verification, and cleanup safety boundary.
- `app/platform_operations/jobs/` remains the canonical execution ledger. Data Lifecycle may enqueue a canonical `JobExecution`, but it does not implement a second job registry.

The former `/settings/data-lifecycle/` route is compatibility-only and redirects to this workspace. Settings no longer owns lifecycle policy UI or mutation logic.

## End-to-end nine-domain DevContainer UAT

The review holding qualification guide
[`docs/operations/data-lifecycle-nine-domain-devcontainer-uat.md`](../../../docs/operations/data-lifecycle-nine-domain-devcontainer-uat.md)
covers **all nine** registered domains, persisted policy and Preview,
canonical JobExecution, verified archive artifacts, bounded source cleanup
only where admitted, cold-object expiry, storage recovery, RBAC,
cross-domain references and KAORI Violet browser/HTMX validation.
Each scenario starts NOT RUN until executable synthetic runtime and human
acceptance evidence exists. The dedicated AuditEvent guide remains
source-specific; Notification Delivery's pending source-safety backlog
remains separate. Archive Only acceptance must not be extrapolated to
destructive cleanup or historical individual-record lookup.

## Retention Policies nine-domain UI conformance (#2961)

The operator accepted **Retention Policies UI across all nine registered
domains on 2026-10-24**. This is a shared-page visual/navigation acceptance,
not the full PostgreSQL/Celery/Archive Storage, RBAC or cleanup lifecycle
admission. The exact pending execution cases remain in the nine-domain
DevContainer UAT guide under #2907.

All policies share the same Hero/workspace shell, 4:8 navigation grid,
metrics, Lifecycle Coverage, Storage Boundary, policy controls,
Preview/manual archive actions, feedback and loading states. The
**Execution Boundary** footer has a single title-adjacent Violet
`ⓘ Guide` using the existing shared Info Tip component, rather than
the old field-level circle-help. The Jobs & Executions link is
permission-gated and independently actionable.

Coverage layout is data-driven: **one** card uses full width, **two**
cards share two columns, **three** cards use three columns at XL and
**four** cards form a 2 × 2 grid. Shared geometry and Violet tokens are
retained; source-specific policy sections reflect real capabilities,
not alternative design systems. Notification Delivery and AuditEvent
remain manual-only with no scheduler/cleanup controls. Archive Only
cannot imply searchable per-record history or release authority.

Remaining **operational** gates: source review and retention admission
for AuditEvent (#2891/#2892), durable Notification Delivery identity,
aggregate and channel dependency continuity plus compaction
(#2868/#2869/#2870), and actual recorded runtime/Visual QA evidence
for DL-E2E-01–20 (#2907). UI acceptance does not close these issues or
authorize official deployment gates.

## Archive Storage evidence-first UI composition (#2977)

The Archive Storage workspace uses the shared KAORI header, four KPI
cards and semantic status labels. **Reachable** means only that the web
container can reach the configured S3 endpoint; **Ready** may indicate a
writable local directory. Neither proves verified data/manifest
checksums. The status label and Storage Interpretation use an
informational, non-success tone until a profile-matching archive has
verified evidence. Only authoritative `last_verified_at` plus a
verified/ready profile can show the success evidence tone. Inaccessible
or incomplete targets display warning. The UI must not imply that a
healthy worker or an accepted TCP connection is archive verification.

Archive Target Contract and Execution Contract use balanced 6:6
responsive columns. The execution details share compact 2-column
cards at `sm` and wider; all provider/location/endpoint/bucket/queue,
dispatcher/retry/purge-limit/worker-isolation fields remain accessible.
The archive-first flow is still four steps, but cleanup is explicitly
**conditional on source-specific admission** (particularly Notification
Delivery #2868–#2870 and AuditEvent #2891/#2892). This change is
presentation-only and does not alter lifecycle/storage provider behavior.

## Workspace contract

The page contains three controlled, server-owned workspaces. Only the active workspace is built on a request, so Archive History queries and Archive Storage probes do not run while an operator is editing Retention Policies:

1. **Retention Policies** — per-domain retention, archive, schedule, and cleanup intent.
2. **Archive History** — verified archive artifacts and cleanup evidence. Canonical worker runtime remains under Jobs & Executions.
3. **Archive Storage** — shared target posture, verification evidence, worker dependency, and archive-first safety boundary.

Only registered archive adapters are displayed. Retention Policies remain preview-first and manual execution is fail-closed when the persisted policy is missing, while a policy is paused, or while another lifecycle execution for that domain is active. Archive History preserves filters, pagination, and Rows context when an operator re-verifies evidence. Archive Storage reports the newest verified evidence that matches the currently configured storage profile across all managed domains, rather than inheriting the selected policy domain. Future domains are not advertised as placeholders before their adapter and safety contract exist. The policy workspace also exposes **Lifecycle Coverage** so operators can see which product surfaces share each source model: Activity Audit and persistent Notification Center rows share `operational_activity`, while Kubernetes, MinIO Object Storage, Metrics Source, and Alertmanager Recent Runtime Observations share `runtime_observation`. Reusable Analytics and Forecast materializations are governed by the `analytics_snapshot` adapter with explicit stale-serve protection. Generated report metadata and retained PDF/XLSX/CSV artifacts are governed by the `generated_report` adapter with active-generation protection and binary checksum verification. Closed Alert Operations evidence is governed by `alert_incident` with a searchable retained case index; normalized Tenant/Kubernetes audit correlation is governed by `tenant_audit_evidence` without copying raw provider audit logs. The current registered adapter catalog contains nine domains (including paused Notification Delivery and AuditEvent archive-only extensions); the v1.3 Final Lock is the earlier four-domain admission record. The Generated Reports policy is seeded paused and must be explicitly enabled after archive-storage readiness and Preview are reviewed.

## Retention Policies domain navigation (#2915)

The approved 4:8 desktop **Master–Detail** workspace keeps its server-owned
policy panel. The nine-domain left navigation is now a compact Data Domains
selector with persistent search/header, source status labels, hot/archive
summaries and a scrollable **list only** on `xl` screens. The `xl` grid
stretches its two 4:8 columns to equal height. The right-hand policy remains
the naturally sized master for the grid row; the left sidebar uses an
inset, absolutely positioned flex shell to **avoid contributing its nine
domain rows to intrinsic row height**. The middle list fills the available
height and scrolls internally, with a small desktop minimum height for
short policy forms. This does not introduce a fixed-height right panel,
independent page scrollbar or extra placeholder cards. Header/search and
the compact Execution Boundary footer stay outside the scrolling list.

The selected row is locally aligned inside the list on initial rendering
and browser Back/Forward, without programmatically scrolling the document.
On smaller screens, the navigator reverts to natural height and a
disclosure reveals the full domain list, with ordinary
href links retained for no-JavaScript navigation. Selecting a domain keeps
the existing URL-pushing HTMX detail swap, active Violet selection, and
read-only RBAC. A no-match search produces an accessible empty state.
Execution Boundary remains a fixed section **outside the scrolling list**,
with detailed ownership text in the existing KAORI Info Tip and permission-
scoped link to canonical Jobs & Executions.

No policy execution, retention setting, archive evidence, storage, API,
permission or domain ownership semantics changed. Keyboard, mobile,
light/dark, HTMX and visual QA still require DevContainer human UAT.

## Alert Incidents Policy visual composition (#2923)

The shared policy workspace keeps the canonical KAORI table block shell,
but uses the **subtle outline without its table shadow** to avoid a
visually doubled perimeter when stacked with the Data Lifecycle frame.
Lifecycle Coverage item cards use the existing subtle outline/surface
tokens. For the four `alert_incident` sources, a responsive two-column
grid at `sm` and above produces an even **2 × 2** composition; on mobile,
cards stack vertically. Other domain coverage layouts are unchanged.

Failure Recovery text remains a concise statement of the existing
single transient retry and subsequent manual intervention; Execution
Worker only appends an availability claim when committed queue readiness
reports `queue_ready=True`. This is presentation-only and does not
change Celery retries, cleanup, policy, or archive semantics. Review
light/dark, focus, responsive, varied-domain layouts, and status-aware
wording in DevContainer before human Visual QA acceptance.

## Policy action feedback and Alert Incidents guide (#2929)

The Alert Incidents Policy title uses the canonical **title-level KAORI
Info Tip Guide** (keyboard, pointer and touch) for source scope, closed-case
admission and archive/cleanup boundaries. The Incident Timeline summary and
Failure Recovery operator sentence were adjusted without modifying
retention behavior.

All four Retention Policies controls retain their owning permissions and
routes: **Preview** is read-only; **Save Policy** persists the supplied
policy; **Archive Only** and **Archive & Cleanup** request a canonical
maintenance `JobExecution`, not an inline archive job. Archive & Cleanup
remains disallowed on non-destructive evidence domains. All state-changing
buttons use explicit submit types, CSRF-protected forms and HTMX in-flight
submission disabling. Read-only Preview GET and archive POST return a
full workspace on non-HTMX navigation, rather than an orphaned fragment.

Feedback uses the existing `record_operational_activity` /
`operation_feedback_oob` / `operational_toast` pipeline:
- **Policy save success:** foreground success toast + Activity Audit, no
  routine Notification Deck entry.
- **Manual job queued:** foreground info toast + Activity Audit; the
  canonical job appears in **Notification Deck → Active Work** and
  **Jobs & Executions**, never as a duplicate queued Notification row.
- **Rejected/failed save, dispatch or verification:** warning/error toast,
  persistent **Notification Deck** entry where actionable, and Activity
  Audit attempt evidence when persistence succeeds.
- **Read-only Preview:** inline selected-boundary result, no artificial
  success toast and no job/Notification row.
- **Archive verification:** direct toast and Activity Audit for the
  foreground response; verified status is source-owned Archive History.

This is a presentation and feedback-delivery boundary only. Storage,
retention thresholds, schedule admission, cleanup and retry semantics
are unchanged. Browser/worker/Deck runtime UAT remains required.

## Analytics Snapshots Policy UAT (#2935)

Analytics Snapshots reuse the shared Retention Policies master-detail
workspace, authenticated Save Policy/Preview/manual Archive Only/Archive &
Cleanup routes, canonical maintenance `JobExecution` and Data Lifecycle
Archive History/Archive Storage. **Serve Window Protection** describes a
necessary two-part eligibility condition: pending or still-serveable
materializations remain hot; stale grace and hot retention must both have
elapsed before archive eligibility. The underlying v1.3 frozen-cutoff
calculation remains authoritative (do not reinterpret the shorter UI
sentence as independent authority for cleanup).

Existing shared operational feedback remains unchanged: policy save success
is a foreground success toast plus Activity Audit, read-only Preview is
inline with no notification, accepted manual archive dispatch is an info
toast and canonical Active Work job without a duplicate queued Deck row,
and actionable warning/error conditions appear in toast and Notification
Deck with audit attempt evidence. A no-eligible-record preview is not
automatically a failure.

Synthetic unit contracts check pending/current/stale-serveable exclusions,
expiration/retention cutoff, and **rechecking each row before cleanup**
so refreshed materializations are not deleted. Complete runtime UAT on
approved disposable PostgreSQL, worker and archive storage, including
checksum, notification surface and human acceptance, is tracked under #2907
and #2935. No schedule, source Analytics, or provider logic changed.

## Administrative Audit Events manual Archive Only readiness (#2939)

Administrative Audit Events remains **paused by default** under the
source-owner/privacy/retention security matrix #2891, not because the
button or data-domain adapter is unimplemented. Read-only Preview is
available to an authenticated **active Local Database Super Admin** with
Data Lifecycle view permission. For *approved disposable synthetic UAT*
only, that user may check **Policy enabled → Save Policy**, then run
**Archive Only** manually using a separately saved, unscheduled policy.
The source and worker recheck authority; a policy toggle does not
immediately dispatch a job or retroactively authorize source export.

UI now distinguishes paused policy from **Manual Archive Only enabled**
on the committed state. Disabled Archive Only is an intentional guard
until enable/save; while a canonical lifecycle JobExecution is active,
duplicate runs stay blocked. After UAT the operator must disable/save
the policy again. A successful save creates a foreground toast and
Activity Audit; accepted queueing shows info toast and canonical Active
Work/Jobs & Executions rather than a duplicate notification row.
Warning/error outcomes remain Deck-visible under the existing
`DECK_ON_FAILURE` policy. Preview remains silent/read-only.

**Never** auto-enable or reconfigure production audit retention. AuditEvent
source census/privacy/legal retention decision #2891 is incomplete, so
automatic scheduling, hot cleanup, archive download, per-record lookup,
and archive object purge remain denied until separate authority #2892.
Archive Only provides only a minimal, bounded redacted projection, not
a complete source-level audit export.

## Administrative Audit Events policy layout (#2943)

The operator panel uses the shared KAORI policy components and one compact status row for paused, enabled or active manual archiving. The schedule controls are not shown for this manual-only domain. Source access, retention and archival permissions remain governed by #2891, and compaction plus historical lookup remain blocked by #2892. The default policy is unchanged. No test-environment wording is shown to operators.

The status row deliberately has no redundant Guide: it shows committed state and the next action. Source-owned retention and archive restrictions remain accessible through the canonical title-adjacent KAORI Guide on the Administrative Audit Events Policy header. Do not add contextual popovers to the status row.

## Notification Delivery and Runtime Observations visual composition (#2959)

Notification Delivery's manual Archive Only operator panel uses **one**
semantic, responsive inline notice instead of a three-line advisory card.
It distinguishes the active **Archive Only** posture in KAORI Violet,
hot-source deduplication/retry/channel/lifetime evidence in regular muted
text and **Cleanup blocked** in the existing warning text token. The
inline notice naturally wraps on narrow screens and does not introduce a
second status card, custom toast or hover control. Delivery policy controls
now correctly show **Execution Mode: Manual Archive Only** and omit the
nonfunctional schedule hour/minute configuration, as already enforced by
the shared policy service and worker.

Runtime Observations uses the existing coverage card component but lays
out its four provider categories as **2 × 2** at `sm` and wider, a single
column on narrow mobile. Kubernetes, Metrics Source, Alertmanager and
Object Storage · MinIO remain distinct, provider-owned data sources.
Cards use existing Violet icons, subtle borders, even heights and shorter
source descriptions. Other domain coverage grids are not changed.

**Admission boundary:** Notification Delivery archive-only is already
implemented, but hot cleanup and archive-object purge are not admitted:
#2868 durable identity is not yet operationally cut over, #2869 aggregates
and channel dependency ownership remain open, and #2870 verified compaction
depends on both. Keep the hot journal authoritative and archived bundles
artifact-level; source contracts and browser UAT cannot authorize purge.
Operator testing must separately verify Policy/Preview/Archive Only,
committed JobExecution, archive checksum, canonical toast/Deck behavior
and negative scheduling/cleanup routes. Official promotion remains HOLD.

## RBAC

- `platform_operations.view_data_lifecycle`
- `platform_operations.manage_data_lifecycle`
- `platform_operations.export_data_lifecycle`

The ownership-cutover migration renames the former `settings.*_data_lifecycle` permission rows in place, preserving role assignments and custom-role access.


## Execution semantics

Retention days define eligibility only. Automatic execution requires an enabled persisted policy, its schedule to be enabled, and the global `DATA_LIFECYCLE_SCHEDULER_ENABLED` dispatcher gate to be on. Celery Beat checks due lifecycle policies every 15 minutes and dispatches due domains through the canonical `maintenance` execution path. The UI exposes the dispatcher gate explicitly and suppresses a misleading next-run timestamp while it is disabled. Transient connectivity failures retry once automatically; exhausted or non-retryable failures keep cleanup blocked and require operator review/manual retry. A later scheduled window can dispatch a new run. Production already deploys a dedicated `maintenance-worker`, so a separate retention worker is unnecessary while `RETENTION_CELERY_QUEUE=maintenance`.


## Engine-level execution admission (#2906)

All registered adapters require an **explicit persisted enabled policy** at
execution time, including direct CLI and Celery worker paths; UI Preview is
still non-mutating. The `audit_event` and `notification_delivery` domains
remain manual Archive Only, unscheduled, without hot cleanup or cold-archive
purge. Delivery remains coupled to source-owned deduplication and historical
outcome dependencies (#2847/#2850); AuditEvent remains under producer/RBAC
security gate (#2891). No consumer may infer a per-record historical reader
or authorize object deletion from the presence of a verified bundle.

## Archive purge safety

Expired cold archives are purged in a bounded batch (`ARCHIVE_PURGE_BATCH_SIZE`, default 250). If object deletion only partially succeeds, the registry row becomes `purge_failed`; the UI no longer advertises the archive as downloadable, the canonical lifecycle JobExecution is marked partially succeeded, and a later lifecycle run may retry the idempotent deletion.

### Storage ownership

Lifecycle domains do not configure independent archive buckets. Hot source storage remains domain-owned (for example, Runtime Observations live in PostgreSQL table `integration_runtime_observations`), while every domain writes verified cold evidence to the shared **Archive Storage** profile. Runtime Observations archive structured provider-neutral evidence as JSONL.GZ + manifest JSON and do not carry supplemental binary artifacts. Generated Reports are the exception at the payload level: their PDF/XLSX/CSV files are copied as supplemental evidence into the same shared archive target. The Retention Policies workspace exposes this boundary without probing the backend; readiness and verification stay demand-loaded in **Archive Storage**.

## Notification Delivery archive boundary (#2848)

The registered `notification_delivery` domain uses the existing Retention
Policies and Archive History workspaces for operator-driven **archive-only**
verification. It is paused by default and excludes scheduled/cleanup
mutations. Unlike the Notification Center's `operational_activity` lifecycle,
this domain concerns outbound provider delivery attempts. Its hot journal,
deduplication and channel dependencies remain committed in PostgreSQL; no
claim of reduced database footprint is made before #2850.

## Administrative AuditEvent archive boundary (#2890)

The separate `audit_event` domain exposes the `audit_events` source through
existing Retention Policies, Preview and Archive History but is paused,
manual and Archive Only by default. Unlike `operational_activity` (persisted
`notifications`), this source includes multiple administrative producer
families; Access Administrative Source Evidence displays only allowlisted
hot `AuditEvent` subsets.

Until source-specific governance #2891 is admitted, the domain, its policy,
preview, counts and archive history are visible **only to authorized Local
Database Super Admin** operators, and even they cannot export the archive
data or manifest. User-interface restrictions are also enforced by the
mutation service, archive download helper and route, scheduling guards and
no-purge service. Archival is minimal/redacted and never deletes hot audit
rows. Archive-object purge is prohibited pending legal hold/retention
review. The fallback 365/3650-day proposal is **not** a legally approved
retention obligation and cannot activate an unattended job. Verified hot
cleanup and per-record archive lookup are separate #2892 workstreams.
