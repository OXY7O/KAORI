# KAORI — Administrative AuditEvent Data Lifecycle DevContainer UAT

**Authority:** #2889 foundation, #2890 archive-only child; source ownership
#1208/#1219; review-only `kaori/review/staging-uat`. Official gates HOLD.

The operator has already accepted **Access → Activity Audit** functionality.
This UAT concerns the **new** `audit_event` policy/archive boundary, not
a redesign of either register.

## Exact candidate and checks

Record exact `git rev-parse HEAD`, Alembic revision, user/role,
test DB identifier, storage profile, worker readiness and redacted evidence
for every scenario. A remote branch commit is not automatically the local
tested commit.

```bash
git fetch origin
git switch kaori/review/staging-uat
git pull --ff-only origin kaori/review/staging-uat
git rev-parse HEAD
git status --short

python scripts/verify_access_final_lock.py
python scripts/verify_migration_graph.py
python -m ruff check app/platform_operations/data_lifecycle tests/contracts/platform_operations
python -m pytest -q \
  tests/contracts/platform_operations/test_data_lifecycle_audit_event_archive_contract.py \
  tests/contracts/platform_operations/test_data_lifecycle_notification_delivery_archive_contract.py \
  tests/contracts/platform_operations/test_data_lifecycle_mutation_domain_contract.py \
  tests/contracts/platform_operations/test_data_lifecycle_final_lock_contract.py \
  tests/contracts/access/test_activity_audit_refinement_contract.py
```

These are operator commands, **not executed by the GitHub-source authoring
session**. Do not run against production data or Storage. No Alembic
migration is introduced by this workstream.

## Browser and security UAT matrix

| ID | Scenario | Expected | Status |
| --- | --- | --- | --- |
| AE-LC-01 | Policies → `audit_event` GET | Ninth domain, source `audit_events`, paused policy, no GET-created policy row | NOT RUN |
| AE-LC-02 | Preview with synthetic old/new AuditEvents | Exact ID-bound and cutoff count; newer events excluded | NOT RUN |
| AE-LC-03 | Compare Access Activity Register vs Administrative tab | Different `notifications` / `audit_events` stores and scoped counts; no duplicate row join | NOT RUN |
| AE-LC-04 | Disable/enable with authorized disposable persisted policy | Paused blocks queue; explicit archive-only save; no default schedule | NOT RUN |
| AE-LC-05 | Invoke Archive Only on synthetic eligible rows with approved Archive Storage | Verified JSONL.GZ/manifest, retained PostgreSQL rows, immutable source event ID; no metadata, IP, UA or credential | NOT RUN |
| AE-LC-06 | Attempt Archive & Cleanup via direct request / worker / adapter | DENY before DB deletion; no cleanup job | NOT RUN |
| AE-LC-07 | Attempt scheduling, including manually configured domain | DENY; no unattended archive JobExecution | NOT RUN |
| AE-LC-08 | Local Super Admin with lifecycle export permission downloads AuditEvent Data/Manifest | HTTP 403; browser does not offer links pending per-source RBAC #2891 | NOT RUN |
| AE-LC-08a | Non-superadmin lifecycle viewer/manager opens Policies, Preview or Archive History | AuditEvent domain/counts hidden; direct selected-domain and mutation requests 403, without policy/job creation | NOT RUN |
| AE-LC-09 | Try purge of AuditEvent archive artifacts through worker/service/CLI | DENY; no object deletion even after archive-retention cutoff | NOT RUN |
| AE-LC-10 | Verify archive checksum, missing/corrupted object, partial storage | Integrity failure surfaced, no false downloaded/cleanup-complete evidence | NOT RUN |
| AE-LC-11 | Unauthorized jobs / tenant user in Administrative Evidence | Existing source tabs hidden/403, no cross-source record disclosure | NOT RUN |
| AE-LC-12 | Long source labels, permission states, narrow UI and light/dark | Existing shared Violet Data Lifecycle UX, 5-item pagination, focus, no broken HTMX state | NOT RUN |

Inspect actual rendered UI and storage only with **approved disposable
test evidence**. Do not inject actual private user data, secrets, session
tokens, production AuditEvent, Kubernetes audit logs, or personal IP data.
For no eligible rows, Archive Only must not create false evidence.

## AuditEvent producer governance checkpoint (#2891)

Review `docs/architecture/audit-event-producer-security-retention-matrix.md` before considering archive export or enabling deletion. The matrix names **confirmed examples**, not a complete codebase census or a legal-retention approval. It distinguishes source-scoped read permissions, actor FK limitations and currently omitted metadata, as well as unknown producers. Until all producers are classified and their source owners approve access, archive download and per-record archive search remain **DENIED** even for Super Admin. The default Disabled policy is intentional; see the preview-first UAT flow above.

## Safety and non-admission boundary

`audit_event` archives minimal sanitized summary fields only. The
original `audit_events.metadata_json`, IP/user-agent and actor's
effective role or authentication source are **not** represented in the
new cold evidence. Actor is only a nullable FK. Archive history tracks
verified **bundles**, not a searchable individual AuditEvent. The
candidate default 365 hot/3650 cold retention days is **not an approved
legal/security retention rule**, does not schedule deletion, and does
not activate hot cleanup. No archive bundle download or archive-object
purge is allowed until #2891 source-owner permission and retention
authority is accepted, followed by #2892 cleanup/index admission.
`job_execution` and `tenant_audit_evidence` remain independent domains.

Operator acceptance of the new archive-only behavior requires recorded
test output, exact SHA, source/role-negative screenshots, and explicit
feedback. Official Developer Check, Full Admission, staging/main,
deployment, release and tags remain HOLD pending separate instruction.
