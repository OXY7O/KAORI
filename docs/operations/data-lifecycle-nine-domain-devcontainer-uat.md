# KAORI — Complete Data Lifecycle Nine-Domain DevContainer UAT

**Authority:** Platform Operations Data Lifecycle audit #1569; end-to-end qualification #2907;
cross-domain execution safety #2906; approved historical Data Lifecycle Final Lock v1–v1.3.
**Environment:** `kaori/review/staging-uat` review holding only. Official CI/CD admission,
`kaori/staging`, production, release and tags are **HOLD** until explicitly authorized.

This is the **single all-domain UAT checklist**, extending the focused AuditEvent
(`docs/operations/audit-event-data-lifecycle-devcontainer-uat.md`) and Notification
Delivery (#2847/#2850) security/retention gates. It does **not** claim that any
scenario has been executed, passed, or accepted. Previously accepted Access
Activity Audit / Notification Channels UI does not imply Data Lifecycle acceptance.

## 1. Current domain inventory and authority

The test roster must equal `DOMAIN_FACTORIES` at the **exact tested commit**.
The nine registered adapters have different data owners and admission rules.

| Domain | Authoritative hot source | Synthetic eligibility / verification target | Current special gate |
| --- | --- | --- | --- |
| `operational_activity` | `notifications` | Old persisted audit-only + inbox-visible rows; unread protection and actor snapshot, not transient toast | Normal admitted lifecycle subject to persisted policy and synthetic cleanup authorization |
| `job_execution` | `job_executions` | Terminal executions versus queued/running; result references remain source-owned | Bundle history is **not** per-job historical lookup; #1416 |
| `runtime_observation` | `integration_runtime_observations` | Old committed normalized runtime samples from multiple provider families | No live provider request; common provider-neutral retention |
| `analytics_snapshot` | `analytics_snapshots` | Old expired snapshot versus pending/still-serveable stale window | No cleanup while pending or still serveable |
| `generated_report` | `reports` + supplemental PDF/XLSX/CSV | Ready/Archived/failed terminal report with object checksum; active generation excluded | Seeded paused; binary archive verified first; do not mutate production report files |
| `alert_incident` | `alert_cases` with source-owned case evidence | Closed case versus active; case history/index preserved | No deletion of cross-domain `notification_deliveries` (#2850) |
| `tenant_audit_evidence` | `tenant_audit_evidence` | Committed normalized tenant audit correlation | Raw Kubernetes API audit logs remain provider-authoritative |
| `notification_delivery` | `notification_deliveries` | Old sent/skipped terminal rows versus queued/failed/retryable | **Manual Archive Only**, no hot cleanup, scheduled run or cold purge; #2847/#2850/#2868–#2870 |
| `audit_event` | `audit_events` | Old/new synthetic source audit rows and minimal redacted projection | **Local DB Super Admin, manual Archive Only**, no export, scheduling, cleanup or purge; #2889/#2891/#2892 |

Policy ages displayed from unpersisted defaults are proposals, not legally
approved deletion or archival schedules. `archive_only` means hot records
remain; it does **not** provide searchable per-record cold history or restore.

## 2. Environment fingerprint and safety authorization

Before testing, record the following in the UAT evidence ticket/worksheet:

| Evidence field | Operator observation |
| --- | --- |
| Git branch and exact `git rev-parse HEAD` | NOT RECORDED |
| `git status --short` | NOT RECORDED |
| Current Alembic revisions and migration graph | NOT RECORDED |
| PostgreSQL database name/host (redacted) and disposable approval | NOT RECORDED |
| Archive Storage profile/backend and disposable object prefix | NOT RECORDED |
| Maintenance queue/worker and Celery Beat posture | NOT RECORDED |
| Test account, auth source, effective source permissions | NOT RECORDED |
| Synthetic fixture identifier, row counts, source high-watermarks | NOT RECORDED |
| Independent security owner and human UAT reviewer | NOT RECORDED |

Stop before any policy mutation or archive if DB/storage are not positively
identified as **approved disposable UAT** or if real personal records, production
security events, credentials, or private provider data would be selected.
Use existing repository test fixtures/seed paths; do **not** modify production
timestamps or bypass retention cutoff to fabricate eligibility.
Do not enable global scheduling or purge flags for this UAT.
A user-visible policy toggle alone does not authorize cleanup.

### Source and regression commands

```bash
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git rev-parse HEAD
git status --short

python scripts/verify_data_lifecycle_final_lock.py
python scripts/verify_migration_graph.py
python -m ruff check app/platform_operations/data_lifecycle tests/contracts/platform_operations
python -m pytest -q tests/contracts/platform_operations/test_data_lifecycle_*.py
```

The last `pytest` glob should be expanded by the operator shell; if the
test runner cannot resolve imports, use the existing repository runner and
record its exact command. The broader `pyright`, `djlint`,
`prettier` and Visual QA gates apply where relevant and are not
silently replaced by these focused checks.

## 3. Common end-to-end workflow for **each** domain

Use the existing three workspaces, not a second lifecycle UI.

1. **Read / authorization:** Open **Platform Operations → Data Lifecycle →
   Retention Policies**, inspect the registered domain, coverage, source
   ownership and policy status. Verify nonauthorized role/tenant requests
   cannot see source-private domain data or bypass direct URLs. Browse
   Archive History separately; verify source-specific permissions.
2. **Preview:** With the policy paused or missing, request read-only Preview.
   Record selected-at UTC, cutoff UTC, maximum record ID, eligible count,
   protected count and estimated size. Record that the policy table and
   JobExecution count **did not change** from GET/Preview. Zero eligible
   rows are an expected outcome, not automatically a FAIL.
3. **Policy transaction:** Save a synthetic approved Archive Only policy.
   Confirm correct persisted settings and that sidebar/hero/HTMX summary
   update consistently. An invalid domain must return 400 and cannot
   default to Activity Audit. Missing/disabled policy must refuse execution.
4. **Manual archive:** Only for an authorized domain and disposable
   synthetic eligible rows, invoke **Archive Only** manually. Confirm one
   canonical maintenance JobExecution, selection boundary, immutable
   archive UUID, JSONL.GZ + manifest, source row count, SHA-256/size
   verification and Archive History status; re-read eligible hot rows and
   confirm no deletion. For reports, verify supplemental binary checksum.
5. **Integrity and failure:** In the disposable storage **only**, test
   missing/corrupted object and partial write, retry, and re-verification.
   A failed integrity check must revoke downloadability and never imply
   cleanup was completed. Re-verifying a recovered archive must preserve
   truthful cleanup-partial semantics.
6. **Safety negatives:** Confirm hot cleanup is rejected for both paused
   archive-only domains at UI, service, CLI, worker and adapter; scheduled
   bypass and cold purge are rejected. For other admitted domains, test
   cleanup only under independent disposable-data authorization, after
   verified bundle and source-specific state/hold checks; never infer
   destructive acceptance merely because source code has a cleanup method.
7. **History, storage and UI:** Verify source-owned archive history,
   Filters/Rows/pagination default 5, loading/error/empty states, immutable
   storage locator after profile changes, light/dark, mobile, keyboard,
   focus, toast and direct-route 403. A bundle listing is **not** an
   archived individual-record reader.
8. **Reset:** Re-disable manually enabled paused policies; compare
   expected synthetic record/object counts. Record exact tests, failures,
   blockers and human acceptance or rejection for each domain.

### Retention Policies domain navigator Visual QA (#2915)

After loading the current holding commit, exercise all **nine** domain rows
in Retention Policies alongside DL-E2E-11, without changing actual policy
or archive evidence:

- Desktop at and above `xl`: 4:8 master/detail **equal-height columns**
  under a variable right-hand policy height (compare Job Executions, Generated
  Reports and shorter domains). No large blank space below the left panel.
  Header, search and registered count stay at the top; only the domain list
  fills and scrolls through the remaining height, with Execution Boundary
  anchored at the bottom. The right policy panel is never height-locked and
  the left domain list must not determine the grid row's intrinsic height.
  For shorter policies, the sidebar retains a usable minimum height.
  Scrolling the list must not unexpectedly scroll the outer document.
- Select first/middle/last domain by pointer, keyboard Tab/Enter and in
  scrolled state: active Violet highlight, `aria-current`, status, URL
  `?tab=policies&domain=...`, and right-hand policy agree; no stale
  selection after browser Back or Save Policy full HTMX refresh.
  After browser Back/Forward, active row must be visible inside the domain
  list while page scroll position and filter behavior remain predictable.
- Search by visible label, source/description, and technical domain ID;
  confirm matches, zero-match empty state, no unauthorized source disclosure,
  and correct focus/scroll after clearing search.
- Under `xl`: Choose Domain disclosure opens and closes accessibly with
  `aria-expanded`; selecting a domain closes the picker, browser
  navigation works without JavaScript, and no nested mobile scroll traps.
- Light/dark, narrow width, long domain labels, wrapping status badges,
  readable Hot/Archive metadata, visible keyboard focus, accessible
  KAORI Info Tip, and Jobs & Executions link only for `jobs.view`.

Record actual viewport/browser, screenshot, selected domain, filtered
result and UAT PASS/FAIL against an **exact commit SHA**; source contracts
alone cannot count as Visual QA acceptance.

### Alert Incidents Policy coverage and visual rhythm (#2923)

On **Alert Incidents Policy**, verify the nested policy border is thin
and neutral/subtle rather than appearing as two adjacent Violet outlines.
Lifecycle Coverage must contain exactly four source-owned cards arranged
**2 × 2** on tablet/desktop (`sm`+): Closed Alert Cases, Incident
Timeline, Notification Delivery and Postmortem Evidence. On mobile,
preserve natural single-column stacking and legible text. Confirm no
excess empty third-column space; adjacent metrics and Storage Boundary
remain unchanged. Check light/dark and compare a domain with three
coverage sources to ensure its existing responsive grid is preserved.

Confirm Failure Recovery says "Cleanup stays blocked; transient failures
retry once, then need manual retry." and that an online ready maintenance
worker displays "Queue maintenance · Online and ready for lifecycle jobs."
When queue readiness is false or unknown, **do not** show the readiness
claim. Run this alongside DL-E2E-11 as a **visual-only** scenario; it
does not authorize cleanup or change existing retention/retry behavior.

### Alert Incidents operator actions, Info Tip and notification routing (#2929)

Run only with approved disposable synthetic PostgreSQL and Archive Storage
and a ready maintenance worker. Verify the exact tested holding SHA and
capture evidence of each action's HTTP/HTMX response, toast status,
Notification Deck visibility, Activity Audit event, canonical JobExecution
and archive evidence. Do not trigger real production cleanup.

| Action / case | Immediate feedback | Persistent evidence and behavior | UAT |
| --- | --- | --- | --- |
| Alert Incidents Policy Info Tip Guide | Accessible anchored Guide on pointer/keyboard/touch | Closed-only case scope, timeline/delivery/postmortem, archive verification, searchable index and journal ownership | NOT RUN |
| Preview | Read-only selected-boundary inline content; no success toast | No JobExecution or Notification row; full page on ordinary GET, partial on HTMX | NOT RUN |
| Save Policy success | Success operational toast | Updated policy + Activity Audit; no routine Notification Deck row | NOT RUN |
| Save Policy invalid/failure | Error toast | Failed attempt Activity Audit and actionable Deck error if persistence succeeds; no policy partial commit | NOT RUN |
| Archive Only accepted | Info operational toast immediately | One canonical maintenance JobExecution in Active Work; Activity Audit, no duplicate queued Deck Notification | NOT RUN |
| Archive & Cleanup accepted on authorized synthetic domain | Info operational toast immediately | Same canonical job; cleanup only after verified archive and admissible source state | NOT RUN |
| Paused policy / unsupported destructive mode / dispatch failure | Warning/error toast | Actionable Deck notification and Activity Audit; no unauthorized job or deletion | NOT RUN |
| Archive verification success/failure | Success/error toast | Committed verification result/attempt, failed integrity stays blocked; failure is Deck-visible | NOT RUN |
| Browser fallback and duplicate submit | Full workspace without HTMX; disabled submit during HTMX request | CSRF/RBAC preserved; no repeated queue mutation while one submission is pending | NOT RUN |

At page level, the Incident Timeline copy reads "Case lifecycle evidence
from initial detection through final closure." Failure Recovery reads
"Cleanup blocked; transient failures retry once, then need manual retry."
Toast, Notification Deck and Activity Audit are *distinct* delivery surfaces;
their presence must match this table rather than appearing all at once for
every successful action. Verify keyboard and light/dark behavior of the
shared KAORI Guide. Keep DL-E2E-03, -05, -07, -10, -11 and -14/-15
source-specific safety checks independent of this visual/feedback UAT.

### Analytics Snapshots Policy actions and serve-window UAT (#2935)

Retain the approved v1.3 Analytics materialization source and 30-day
default hot policy. Use **synthetic fixtures only** with known frozen UTC
boundaries and separately approved disposable Archive Storage/worker;
do not edit live snapshot timestamps. The shorter Serve Window Protection
description reads: "Pending and still-serveable snapshots stay hot.
Archiving requires both stale grace and hot retention to have elapsed."

| Case | Expected result | UAT |
| --- | --- | --- |
| Pending snapshot older than cutoff | Excluded from preview, archive and cleanup | NOT RUN |
| Current materialization / recently refreshed row | Protected, never cleanup-selected | NOT RUN |
| Expired but still in stale-grace window | Kept hot; no archive or cleanup | NOT RUN |
| Stale deadline exactly at frozen cutoff | Still protected by strict comparison | NOT RUN |
| Expired and outside stale grace + frozen hot cutoff | Eligible in Preview and Archive Only | NOT RUN |
| Concurrently refreshed between selection and cleanup | Rechecked against current row, not deleted; truthful partial cleanup evidence | NOT RUN |
| Save Policy (success / invalid) | Committed policy + success toast, or error toast and actionable Deck; Activity Audit evidence, no routine success Deck | NOT RUN |
| Preview (zero/eligible) | Read-only inline boundary; no created JobExecution or success notification | NOT RUN |
| Archive Only (enabled persisted policy) | Info toast + canonical maintenance JobExecution in Active Work, no duplicate queued Deck notification; verified archive artifact, source row retained | NOT RUN |
| Archive & Cleanup (approved synthetic only) | Info toast + canonical JobExecution; delete only after archive checksum and per-row recheck | NOT RUN |
| Disabled policy / failed dispatch / RBAC-negative | Correct blocked action, warning/error toast and Deck when actionable, no unauthorized artifact or delete | NOT RUN |
| Light/dark/mobile, HTMX/full-page fallback, multiple submits | Shared UI controls remain accessible, toast/OOB appears once, no duplicate job from in-flight submission | NOT RUN |

Focused source/unit tests:
`tests/contracts/platform_operations/test_data_lifecycle_v1_3_analytics_snapshot_contract.py`
and
`tests/contracts/platform_operations/test_data_lifecycle_analytics_snapshot_uat_contract.py`.
Also run the existing shared lifecycle action/feedback contract. Record
actual event statuses and Notification Deck visibility, not merely
toast HTML in a response. User acceptance of Alert Incidents is **not**
a pass for this Analytics UAT; keep Analytics cases NOT RUN until
DevContainer evidence and human review.

### Administrative Audit Events manual activation UAT (#2939)

**Paused by default is expected.** Source authorization remains limited
to active Local Database Super Admin; this temporary route is not a
general audit export entitlement. The shorter domain description is
"Source-owned administrative AuditEvent evidence; manual Archive Only."
The coverage note remains explicit about separate Activity Register,
Jobs, Tenant Audit Evidence, and pending retention/RBAC review.

| Case | Expected result | UAT |
| --- | --- | --- |
| Disabled/absent persisted policy | Preview remains read-only; Archive Only disabled, no jobs | NOT RUN |
| Authorized manual enable/save | Success toast + Activity Audit, no routine Deck; committed policy enabled/Archive Only/unscheduled; no job starts on Save | NOT RUN |
| Enabled state refresh | Manual Archive Only enabled message, Archive Only available, no scheduler/cleanup/export controls unlocked | NOT RUN |
| Manual Archive Only with synthetic eligible records | Info toast + canonical maintenance JobExecution; immutable verified archive/manifest, hot AuditEvent row preserved | NOT RUN |
| Scheduled spoof/LDAP/non-admin/inactive requester, cleanup/download/purge | Authorization fails closed before mutation, actionable warning/error Deck | NOT RUN |
| Disable/save after UAT | Success toast, disabled state restored; worker refuses new archive | NOT RUN |

Execute with disposable UAT source/storage and record exact holding
commit; the synthetic contract
`tests/contracts/platform_operations/test_data_lifecycle_audit_event_manual_uat_contract.py`
covers the toggles and safety boundaries but **does not** substitute for
actual PostgreSQL, Celery, Archive Storage, negative RBAC, or operator UAT.

## 4. Execution / failure-injection matrix

Every row starts **NOT RUN**; mark PASS only with exact SHA and inspected
runtime evidence. If a scenario is intentionally denied, PASS means
**correct rejection without side effect**, not feature admission.

| ID | Scope | Expected result | Status |
| --- | --- | --- | --- |
| DL-E2E-01 | All 9: registered domains and source coverage | Exact registry parity; no phantom/duplicate source union | NOT RUN |
| DL-E2E-02 | All 9: GET/Preview with missing/disabled policy | Preview read-only, no automatic policy insertion/job | NOT RUN |
| DL-E2E-03 | All 9: persisted policy and manual queue | Missing/disabled/invalid policy rejected before lock; proper HTMX state | NOT RUN |
| DL-E2E-04 | All 9: cutoff/high-watermark and concurrent new rows | Frozen bounds, deterministic id selection, no overshoot or double count | NOT RUN |
| DL-E2E-05 | All 9: Archive Only with synthetic eligible data | Canonical JobExecution, immutable compressed data/manifest with checksums, no hot deletion | NOT RUN |
| DL-E2E-06 | All 9: zero eligible rows | No false archive artifact, no fabricated evidence | NOT RUN |
| DL-E2E-07 | All 9: Verify and missing/corrupt/partial storage | Fail closed, revoke downloadability, preserve verification failure | NOT RUN |
| DL-E2E-08 | All 9: storage profile rotation and history | Registry reads original nonsecret storage locator, not current target | NOT RUN |
| DL-E2E-09 | All 9: concurrent requests/lock/retry/worker loss | No unsafe duplicate cleanup, bounded retry, truthful canonical JobExecution | NOT RUN |
| DL-E2E-10 | All 9: RBAC and direct URL negative | No unauthorized source exposure, action or archive download | NOT RUN |
| DL-E2E-11 | All 9: responsive UI/HTMX/a11y/history paging | Consistent Violet design, dark/light, 5-row default, focus/error/empty/loading | NOT RUN |
| DL-E2E-12 | Admitted cleanup-capable domains only | Compare-before-delete after verified archive; exact source ownership/holds | NOT RUN |
| DL-E2E-13 | Admitted cold-purge domains only | Expiry/time boundary, bounded delete, partial failure and retry | NOT RUN |
| DL-E2E-14 | `notification_delivery` | Scheduled, hot cleanup and cold purge **DENIED**; terminal-only source selection; dedup remains | NOT RUN |
| DL-E2E-15 | `audit_event` | Only active Local DB Super Admin can manually archive; source RBAC, export/cleanup/purge **DENIED** | NOT RUN |
| DL-E2E-16 | `job_execution` / `audit_event` | Hot record absence never fabricates permissioned archived-record existence | NOT RUN |
| DL-E2E-17 | `generated_report` | Active generations excluded; permitted binary supplement verified against original | NOT RUN |
| DL-E2E-18 | `analytics_snapshot` | Pending/serveable snapshots remain hot; stale window honored | NOT RUN |
| DL-E2E-19 | `alert_incident` / `notification_delivery` | Closed-case cleanup does not delete delivery journal or dedup evidence | NOT RUN |
| DL-E2E-20 | `tenant_audit_evidence` / `runtime_observation` | Committed normalized evidence, provider remains authoritative | NOT RUN |

## 5. Per-domain operator acceptance ledger

| Domain | Preview | Archive + checksum | Negative safety / RBAC | UI / human acceptance |
| --- | --- | --- | --- | --- |
| `operational_activity` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `job_execution` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `runtime_observation` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `analytics_snapshot` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `generated_report` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `alert_incident` | NOT RUN | NOT RUN | NOT RUN | ACCEPTED — operator review 2026-10-23 |
| `tenant_audit_evidence` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `notification_delivery` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `audit_event` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

The audit-only contracts of `notification_delivery` / `audit_event`
mean that rejected destructive operations are expected **PASS** on
negative tests. Mark actual hot cleanup/cold purge as **NOT ADMITTED**,
not a runtime failure in the accepted Archive Only scope.

The Alert Incidents UI/actions operator review was accepted on 2026-10-23
(#2923 and #2929 completed); the three separate runtime evidence columns
remain NOT RUN here because their underlying outputs were not provided in
this UAT register. Acceptance does not transfer to Analytics Snapshots.

## 6. Blockers and stop/go criteria

| Capability or unresolved dependency | Existing authority | Admission |
| --- | --- | --- |
| Full current-domain archive-only runtime qualification | #2907, #2906 | **PENDING runtime UAT** |
| Historical Data Lifecycle remediations DL-01..06 | #1569, #1571–#1576 | **Implemented in holding; runtime/human UAT pending** |
| JobExecution verified **per-record** cold lookup | #1416 | **NOT ADMITTED** |
| Notification Delivery durable identity/backfill, aggregates, and compaction | #2847/#2850/#2868/#2869/#2870 | **NOT ADMITTED** |
| AuditEvent producer classification, export retention authority, compaction/lookup | #2889/#2891/#2892 | **NOT ADMITTED** |
| Legal hold, source-owner retention/purge approval and restore evidence | Source-specific governance authorities | **NO blanket approval** |
| Official Developer Check, Full Admission and staging/main promotion | Existing KAORI release governance | **HOLD** |

**Stop** when any data origin/storage profile is uncertain, unexpected
hot deletion occurs, checksum cannot be verified, actor or source RBAC
is ambiguous, or a protected domain appears scheduled/purgeable.
Record FAIL with evidence and create a bounded remediation issue rather
than enabling production features to make the test pass.

**Go for human Archive Only UAT acceptance** only when all applicable
archive-only cases pass on the exact commit, object integrity and negative
side effects are demonstrated, and the reviewer records explicit approval.
This is **not** permission to activate hot compaction, broad archive
export, restore, cold purge, scheduler, or official release gates.

The operator must preserve raw test outputs/screenshots privately under
approved KAORI evidence storage; issue comments should contain
nonsecret summaries, exact SHA and links to governed evidence only.
