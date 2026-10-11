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


## Producer-Level Source Inventory — 2026-10-11 Follow-up (#1218)

**Source revision:** review baseline `e9e650b557bb365a028253f4150a0a04bb7bcb37`. This table is a **source-contract inventory**, not proof that every runtime mutation emitted a committed event. `VISIBLE` means the specific call path writes a local `Notification` that the Activity Audit query can read (subject to transaction success, permissions and retention); it does not establish complete feature coverage. `SEPARATE` means a distinct persisted store; `DELIVERY-ONLY` means outbound-channel delivery and local `NotificationDelivery` evidence, not Activity Audit inclusion.

| Feature / operation | Producer and committed authority | Activity Audit coverage | Actor/correlation and retention boundary | Follow-up |
| --- | --- | --- | --- | --- |
| Authentication sign-in, rejected sign-in, sign-out | `app/access/authentication/audit.py` directly constructs `Notification`; authenticated vs unauthenticated actor snapshots are distinguished | **VISIBLE** in hot Notification register | `actor_snapshot_json`, target-account `user_id` on failed login is **not** actor identity; `ip_address`, auth source, reason code; operational_activity archive | Keep existing boundary; check synthetic failure and sign-out in UAT |
| User management | `app/access/users/notifications.py::user_management_feedback` → `record_operational_activity`; `app/common/admin_audit.py::record_admin_event` is a separate administrative `AuditEvent` producer | **VISIBLE when feedback is invoked; ALSO separate administrative AuditEvent** | Actor from User at notification commit; separate administrative record uses actor FK. Correlate before calling events duplicates | #1219 if cross-store drill-down approved |
| Roles/RBAC | `app/access/rbac/notifications.py::role_access_feedback` → shared Notification writer; admin audit may also be committed | **VISIBLE for feedback; separate source exists** | Snapshot actor on Notification; role ID/slug in safe metadata; AuditEvent target/actor handling differs | #1219 |
| Identity Providers | `app/access/identity_providers/notifications.py::identity_provider_feedback` → shared Notification writer | **VISIBLE for invoked feedback** | `provider_id`, `provider_key`, actor; secret material must remain external | UAT producer sampling |
| Integration Registry lifecycle | `app/integrations/routes.py` calls `record_operational_activity` for multiple mutation and failure paths | **VISIBLE for those calls; not a guarantee for every provider mutation** | Integration instance/provider refs and Actor Notification snapshot, operational_activity archive | Verify additional provider paths |
| Harbor Registry instance actions | `app/integrations/registry/providers/harbor/application/routes.py` calls `record_operational_activity` for registration/validation actions | **VISIBLE for invoked feedback** | Provider-owned Harbor state remains authoritative; local evidence is about governed KAORI action | Sample each mutation/validation terminal route |
| Data Lifecycle policy/execution request | `app/platform_operations/data_lifecycle/service.py` emits shared Notification activity | **VISIBLE for explicit policy/update/queue outcomes** | Domain/mode and job refs when known; archive rules belong to each underlying data domain | Review terminal archive task evidence separately |
| Manual Jobs dispatch | `app/platform_operations/jobs/routes.py` invokes `record_operational_activity` for accepted/blocked/failed dispatch | **VISIBLE for dispatch feedback only** | `job_public_id`, queue and manual requester when available; **terminal status belongs to JobExecution** | #1219 for source links |
| Automatic/scheduled Job dispatch or terminal | `app/platform_operations/jobs/audit.py::record_automatic_job_event`, `app/platform_operations/jobs/service.py::_append_automatic_terminal_audit` persist `AuditEvent`; JobExecution remains task authority | **SEPARATE: not automatically queried by Activity Audit** | `actor_user_id=None` for automatic; job `public_id` stable link; JobExecution archive independent, AuditEvent retention must be reviewed | #1219, do not fabricate a human actor |
| Tenant inventory sync (authored) | `app/kubernetes/tenant/audit.py` dispatch/terminal uses `AuditEvent` with `job_public_id` | **SEPARATE unless a specific matching Notification is also persisted** | Owner/user FK differs from immutable Notification actor snapshot; explicit job ID and sync status | #1219 |
| Native Tenant handoff plan/approval/execute | `app/kubernetes/tenant/release_handoff_approval.py` and `native_handoff_executor.py` commit privileged `AuditEvent` evidence | **SEPARATE; do not silently mark Activity Audit complete** | Requested-by vs independent approver and authorization provenance are distinct, high-sensitivity; no implied `activity_audit.view` permission to raw details | #1219, gated security decision |
| Kubernetes Tenant provider API observations | `app/kubernetes/tenant/audit_correlation_service.py::ingest_kubernetes_audit_events_committed` commits `TenantAuditEvidence` and `_project_activity()` audit-only `Notification` in same successful ingestion transaction | **VISIBLE through existing idempotent bridge** | Provider principal/source event and `event_at` vs `observed_at`; `tenant_audit_evidence_id`; Tenant evidence archive independent | **NO second bridge** (#122) |
| Automation Control decision outbound alert | `app/intelligence/automation_control/notifications.py::dispatch_decision_notification` builds `NotificationEvent` for external delivery | **DELIVERY-ONLY from this call site; any separate committed audit must be proven independently** | `IntelligenceDecision.public_id` and approval/decision state are authoritative; `event_key` is delivery idempotency, not Notification actor | #1220 |
| Alert Intelligence outbound | `app/intelligence/alert_intelligence/notifications.py` builds `NotificationEvent` and calls `dispatch_notification_event` | **DELIVERY-ONLY from this call site** | Alert/incident state is domain-owned; sending provider channel message does not imply persisted Activity Audit | #1220 |
| Report notification delivery | `app/reports/notifications.py::deliver_generated_report` builds outbound `report.generated` `NotificationEvent` | **DELIVERY-ONLY from this call site** | Report artifact/job remains authoritative; channel `event_key=report.generated:<report.id>` identifies delivery, not actor's audited generation action | #1220 |
| External channel delivery worker | `app/integrations/delivery/notification_channels/service.py::dispatch_notification_event` commits `NotificationDelivery`, attempts provider send and retries under channel/event_key | **SEPARATE delivery ledger; not an Activity Audit writer** | Recipient/channel ID, provider message ID, delivery status, attempt count. Never issue one Activity Audit record per channel/retry without explicit business-event contract | #1220 |

### Status and Architecture Decision

- **Confirmed source-backed paths:** Authentication, invoked Access/Integration/Harbor/Data Lifecycle/manual Job feedback and existing provider-audit Tenant bridge. Every outcome still needs runtime sampling before PASS.
- **Confirmed missing automatic fan-in:** `AuditEvent`-only automatic Job/Tenant governance records and outbound-only `NotificationDelivery` are not automatically part of the Notification-backed Activity Audit query. This does **not** prove those business operations lack domain audit evidence.
- **Unverified producers:** remaining Kubernetes governance, Ansible/orchestration, asset/registry synchronization, Analytics/Intelligence decision persistence, miscellaneous Reporting, and any route not explicitly inventoried above. Do **not** infer coverage from event-category YAML or the presence of an outbound notification.
- **Canonical separation:** written KAORI administrative action ≠ provider-observed API action ≠ JobExecution terminal ≠ delivery attempt. Correlation references point to authoritative stores; copying payloads or guessing actors breaks governance.
- **Decision requested under #1208:** approve scoped source-linked navigation/projection with permission checks (preferred), or explicitly choose another authority model. Until that approval, #1219 and #1220 remain blocked design workstreams and no new Notification writes are authorized.

### Focused DevContainer Acceptance Plan (not yet executed)

1. Capture one synthetic auth success/failure/logout, User/RBAC/IdP mutation, Integration lifecycle outcome, Harbor registration/validation, manual Jobs dispatch and Data Lifecycle policy action; verify Notification `event_type`, actor snapshot, target, category, correlation and Activity Audit query.
2. Exercise automatic Job and Native Tenant approval; verify `AuditEvent` and JobExecution identities and **do not expect** Notification-backed Activity Audit entry unless an existing explicit producer also runs.
3. Ingest one normalized Kubernetes Tenant event twice; expect one `TenantAuditEvidence` and one existing audit-only Notification, with stable `tenant_audit_evidence_id` and correct provider-observed actor classification.
4. Dispatch one report/automation alert to two channels and retry a failed send: validate `NotificationDelivery` dedup and distinguish delivery attempts from committed business-action audit records.
5. Inspect hot/retained archive boundaries separately, source-specific RBAC and safe redaction (including #1207). Never test with real credential values. Security, CI/CD, Developer Check, Full Admission, staging/UAT and human acceptance remain **HOLD**.


### Additional Reviewed Producers — Same Authority (#1218)

These checks extend the inventory above and resolve the earlier **unverified** flag for the specific call sites below. They do not prove coverage for every route in the associated feature.

| Feature / operation | Verified source and authority | Activity Audit interpretation | Required review |
| --- | --- | --- | --- |
| Kubernetes ConfigMap mutations | `app/kubernetes/operations/configmaps/routes.py::_feedback` calls `record_operational_activity` | **VISIBLE for this feedback path**; Kubernetes remains provider authority for actual ConfigMap object | Dry-run versus mutation and secret-safe change summaries |
| Kubernetes Secret create/update/delete | `app/kubernetes/operations/secrets/crud_routes.py` uses `app/kubernetes/operations/secrets/route_support.py` feedback helper → `record_operational_activity` | **VISIBLE for feedback path**, not a copy of plaintext Secret values | DAST/security check proving secret data never persisted; #1207 direct-write scope |
| Cluster lifecycle | `app/kubernetes/cluster/lifecycle_web.py` calls `record_operational_activity` | **VISIBLE for the explicit lifecycle web callbacks** | Check success, rejected and queued actions individually |
| Alertmanager registration/validation | `app/integrations/observability/alert_source/providers/alertmanager/application/notifications.py` invokes shared Notification-backed operational activity | **VISIBLE when helper used** | Provider runtime remains independent, avoid interpreting configuration as live readiness |
| MinIO Object Storage provider | `app/integrations/storage/object_storage/providers/minio/application/routes.py` has explicit `record_operational_activity` paths | **VISIBLE on these interaction paths** | Follow per-instance lifecycle and report terminal jobs separately |
| Reporting templates | `app/reports/report_templates/routes.py::_record_template_feedback` writes operational activity | **VISIBLE for create/update/delete/duplicate feedback paths** | Report template mutation != report generation/delivery |
| Reporting schedules | `app/reports/schedules/routes.py::_record_schedule_feedback` writes operational activity | **VISIBLE for schedule create/update/toggle/delete/run feedback paths** | Schedule configuration != job execution terminal or outbound delivery |
| Artifact Registry governance | `app/artifact_registry/routes.py` invokes `record_operational_activity` | **VISIBLE for those governed actions** | Provider registry/image remains authoritative; verify sync/terminal separately |
| Automation Control governance | `app/intelligence/automation_control/service.py::upsert_deployment_policy` persists an `AuditEvent`; `app/intelligence/automation_control/routes.py` also invokes `record_operational_activity` for scoped feedback and queues outbound decision alerts | **MIXED**: some UI feedback is Notification-backed, policy AuditEvent is separate, channel delivery is `NotificationDelivery` | Must correlate by real decision/action and actor; no synthetic audit for channel retries; #1219/#1220 |
| TLS governance sync dispatch | `app/kubernetes/governance/tls_certificates/audit.py::record_tls_sync_dispatch_audit` persists `AuditEvent` | **SEPARATE**, not automatically in the Notification Activity register | Governed sync/JobExecution correlation and permission/retention review #1219 |

**Additional security boundary:** `app/access/authentication/audit.py` and `app/kubernetes/tenant/audit_correlation_service.py::_project_activity()` directly construct `Notification`, bypassing the shared writer introduced in #1207. Both currently construct deliberately bounded evidence, but **the shared writer's persistence sanitization cannot be assumed to cover these direct-write paths**. This requires direct producer review under open #1207 before any claim of universal stored-evidence redaction. The read-side Activity Audit sanitizer remains relevant for those records.

**Remaining unverified scope:** deeper analytics/forecast terminal operations, remaining Kubernetes resources, resolver delivery execution, reports artifact generation details, storage fleet jobs, all background archive tasks, and failure/retry paths not listed in the matrix. A full feature-by-feature UAT matrix and architecture acceptance remain outstanding.

**Lifecycle note:** This inventory does not close #1208. #1218 is a scoped evidence contract; #1219 and #1220 require the explicit architecture/security decision before implementation.
