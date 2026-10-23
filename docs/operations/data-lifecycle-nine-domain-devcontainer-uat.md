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

- Desktop at and above `xl`: 4:8 master/detail, search and registered count
  remain visible, only the domain list scrolls up to
  `min(65dvh, 36rem)`, and the Execution Boundary footer stays outside
  the inner scroll; the right policy panel is not height-locked.
- Select first/middle/last domain by pointer, keyboard Tab/Enter and in
  scrolled state: active Violet highlight, `aria-current`, status, URL
  `?tab=policies&domain=...`, and right-hand policy agree; no stale
  selection after browser Back or Save Policy full HTMX refresh.
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
| `alert_incident` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `tenant_audit_evidence` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `notification_delivery` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| `audit_event` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

The audit-only contracts of `notification_delivery` / `audit_event`
mean that rejected destructive operations are expected **PASS** on
negative tests. Mark actual hot cleanup/cold purge as **NOT ADMITTED**,
not a runtime failure in the accepted Archive Only scope.

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
