# Activity Audit — Cross-Domain Evidence Source Review (2026-10-11)

**Status:** Review proposal; authority decision and browser/security acceptance pending.
**Issue:** #1208. Security audit authority: #640 / #638. Tenant provider correlation authority: #122.
**Reviewed baseline:** `kaori/review/staging-uat@6aaa0c5f7c52a3d3626fbc3e370758ded2c45e48`.

## Existing Source-of-Truth Boundaries

| Source | Concrete producer/example | Authority and actor | Activity Audit visibility | Retention / access |
| --- | --- | --- | --- | --- |
| `notifications` | `record_operational_activity()`, `create_notification()`, Authentication Audit | Normalized KAORI operation; committed `actor_snapshot_json`, `category_key`, distinct recipient `user_id` | **Direct**, including `deck_visible=false` rows | Hot `Notification`; older records through archive-first `operational_activity`; Activity Audit requires `activity_audit.view` |
| `audit_events` | `app/common/admin_audit.py` for User/Role changes; `app/kubernetes/tenant/audit.py` for Tenant sync dispatch/terminal; Native handoff approvals/executor; scheduled-job administrative events | Administrative action/target with `actor_user_id`, target type/id and action; not a full immutable actor snapshot | **Not automatically queried** by the Activity Register; producer-dependent Notification counterpart must be separately verified | Independent source; no `audit_events` archive domain was found in the inspected Data Lifecycle domain catalog. Verify its retention/authorization before surfacing |
| `tenant_audit_evidence` | `ingest_kubernetes_audit_events_committed()` in `app/kubernetes/tenant/audit_correlation_service.py` | Kubernetes API log remains external authority; KAORI commits bounded normalized principal/tenant/resource/verb/outcome/provenance, idempotency key, matched/ambiguous/unmanaged classification | **Already bridged** by `_project_activity()`: same transaction writes one audit-only `Notification` with `tenant_audit_evidence_id`; duplicates are rejected by tenant evidence idempotency. Do not introduce a second bridge | Independent `tenant_audit_evidence` archive domain; source timestamp `event_at` and ingest `observed_at` differ |
| `job_executions` | Jobs & Executions with `public_id`, requester, queue, status and terminal/result evidence | Worker/job execution lifecycle authority; not itself a human administrative audit fact | **Not automatically queried** by Activity Register; explicit terminal Notification or `AuditEvent` may be emitted by some workflows | Own job-execution archive domain; read path `jobs.view` is separate from `activity_audit.view` |
| Intelligence notification delivery | `app/intelligence/automation_control/notifications.py` dispatches `NotificationEvent` to provider-neutral delivery services | Delivery is not automatically KAORI audit persistence | **Coverage unproven** from event-catalog categorization alone; inspect committed producer/decision audit record before declaring an audited action | Preserve decision/approval authority and notification-channel ownership |
| Integrations / Registry / Harbor and Reports | Individual feature producer paths; shared `record_operational_activity()` used for some feature mutations | External provider remains authoritative for actual provider objects; KAORI may commit governance, binding and execution evidence | **Only those actions persisted as Notification** appear; catalog categories do not generate missing rows | Preserve producer-specific retention/permission boundaries and avoid mirroring raw provider logs |

## Verified Existing Contracts

1. `app/access/activity_audit/service.py` delegates register/query/detail to `app/platform_operations/notifications/queries.py`, which selects `Notification` only.
2. `app/access/activity_audit/routes.py` requires `activity_audit.view`. The register is administrative/system-wide **within the Notification store**, not a grant to read arbitrary Tenant raw/JobExecution details.
3. `app/platform_operations/notifications/event_catalog.py` classifies only records that are actually written. An event-category match cannot prove producer audit coverage.
4. Tenant's `_project_activity()` already commits a correlated audit-only Notification with a stable `tenant_audit_evidence_id` and separate source event metadata. Existing duplicate protection is source-side in `TenantAuditEvidence`.
5. `AuditEvent` is an administrative audit source, while `JobExecution` is task execution authority. Treating them as interchangeable events or copying their payloads into `notifications` would change their meaning, RBAC and retention contracts.
6. Existing `operational_activity`, `job_execution` and `tenant_audit_evidence` archive domains are independent. Reconstructing historical correlation across hot and archive must be explicit, not a live-provider lookup.

## Decision Needed Before Implementation

**Recommended approach:** preserve Activity Audit as the current Notification-backed administrative register; add **source-linked correlation/read models over committed KAORI evidence** only after an authority decision. Prioritize known business-event-to-job/audit links and count missing coverage explicitly. Do not implement a universal raw-table SQL union and do not duplicate Tenant's existing idempotent bridge.

An approved contract must specify:
- **Event identity:** source model, source primary/public identifier, event key, recorded vs source-occurrence time, provenance, normalized outcome, correlation refs (`job_public_id`, tenant ID, target ID, request/decision ID as available), and de-duplication rule.
- **Actor authority:** immutable snapshot if persisted, external Kubernetes principal if provider-observed, `actor_user_id` where only a mutable FK exists; never retrofit missing roles/identities as facts.
- **Authorization:** source-specific detail permissions; `activity_audit.view` alone must not bypass `jobs.view`, Tenant or security evidence restrictions.
- **Retention:** do not claim hot-or-archive continuity for a source with no approved retention domain; no implicit cross-domain purge or copy of raw payloads.
- **Coverage:** producer action matrix, explicit audit expectation, real observed record/contract evidence, replay/idempotency, security redaction; mark unsupported/unverified pathways honestly.

## Safe Workstream Breakdown (after decision)

- **A — Producer/source inventory**: enumerate mutation/approval/terminal event emitters with source, permission, state, correlation key, archival policy and evidence of actual persistence. Output a gap table; never assume `NotificationEvent` implies local Activity Audit.
- **B — Correlation contract**: decide canonical source-linked committed projection and idempotent row identity; reuse the Tenant bridge and already-committed JobExecution links. No raw Kubernetes/provider clone.
- **C — Read-only cross-domain UI**: if approved, extend the existing Access Activity Audit with source-detail links and explicit scope/capability messaging using shared KAORI tables/HTMX, behind reviewed permissions. Do not silently show data from unauthorized domains.
- **D — Retention/integrity/security admission**: verify archive restore semantics for every source, sanitizer #1207, no actor misattribution, search filters, DAST/security gates and human UAT.

## Explicit Non-goals

No new audit event source in this review, no multi-store migration, no new category taxonomy, no provider live query, no shadow JobExecution table, no second Tenant-Kubernetes bridge, no backfill, no bypass of the current Final Lock.

## Acceptance and Traceability

- The source map above is a **static source review**, not tested end-to-end coverage.
- Outstanding decision and producer-by-producer inventory must be reviewed before implementing B/C/D.
- This proposal may be merged to `kaori/review/staging-uat` for local feedback; CI/CD, Developer Check, Full Admission, staging/UAT and main remain **HOLD**.
