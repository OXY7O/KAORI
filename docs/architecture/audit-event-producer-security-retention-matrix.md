# AuditEvent Producer Security and Retention Admission Matrix

**Authority:** #2891 (security child of #2889); source-ownership #1208/#1219;
approved Data Lifecycle archive-only implementation #2890. Status:
**partial verified producer sample / security decision pending**, not an
inventory-complete or legal-retention approval.

## Boundary

The global `audit_events` table is **not** synonymous with Access →
Activity Audit → Administrative Source Evidence. The Access register displays
selected Automatic Jobs and Tenant Inventory Sync actions after their own
`jobs.view` / `tenant.manage` checks. The Data Lifecycle `audit_event`
domain is deliberately wider and must not grant a general archive-reader
permission based on permission to view either register. The unrelated
`operational_activity`, `job_execution` and `tenant_audit_evidence`
domains retain their own source/evidence/retention authority.

## Producer inventory — directly inspected code (not exhaustive)

| Verified write path | AuditEvent action/target | Principal/source semantics | Current read boundary | Risks and unresolved authority |
| --- | --- | --- | --- | --- |
| `app/common/admin_audit.py::record_admin_event` | Access administration actions; user/role targets | Optional `User` FK; no immutable role/auth-source snapshot | Access owner-specific permissions; NOT the jobs/tenant register | User/role changes, access grants and admin governance may require longer legal/security holds |
| `app/platform_operations/jobs/audit.py::record_automatic_job_event` | Scheduled `automatic_job_*`; `job_execution` | System-run actor NULL for scheduled job; job public ID may outlive hot execution row | `jobs.view` for scoped register; not a general audit export entitlement | Execution metadata can contain queue/config identifiers; expired hot jobs do not prove archive lookup |
| `app/kubernetes/tenant/audit.py::record_tenant_sync_dispatch_audit` | `kubernetes_tenant_inventory_sync_dispatch_*`; job or tenant inventory | Requesting actor FK; source metadata may include IDs/result payload | `tenant.manage` for Tenant Sync scoped register | Tenancy/scope and cluster identity, role revocation and source-specific retention |
| `app/kubernetes/tenant/audit.py::record_tenant_sync_terminal_audit` | `kubernetes_tenant_inventory_sync_*`; job execution | Actor nullable FK, terminal-job source; metadata includes result summary | `tenant.manage` for scoped register | Partial-result payload may contain private asset/user names; no immutable actor snapshot |
| `app/kubernetes/governance/tls_certificates/audit.py::record_tls_sync_dispatch_audit` | `governance_tls_secret_sync_dispatch_*`; job or TLS inventory | Requesting actor FK; source may reference cluster/certificate metadata | Governance/TLS source permission **needs owner confirmation**; not admitted under either Access source tab | Cluster/certificate IDs and security operations need stricter visibility |

Other AuditEvent producers and ad-hoc writes **have not been exhaustively
enumerated**. They remain **unclassified**. A codebase-wide producer and
source-permission audit, owner sign-off and update to this matrix are
prerequisites to broader export, hot deletion or archive record reading.

## Field-level security and evidentiary completeness

| Field | Archive-only state (#2890) | Decision before cleanup/export (#2891/#2892) |
| --- | --- | --- |
| `id`, `created_at` | Included as record identity and UTC event time | Verify durable uniqueness and provenance/index mapping |
| `actor_user_id` | Nullable FK included; **never** immutable actor snapshot | How to preserve context after user deletion or role/identity changes |
| `target_type`, `target_id`, `action` | Bounded, sanitized text | Determine per-producer sensitivity and allowed read scope |
| `summary` | Bounded, sanitized best-effort text | **May still contain private free text**, not guaranteed anonymous; require security review |
| `metadata_json` | Omitted entirely | Producer-specific schema, safe fields and legal evidence completeness |
| `ip_address`, `user_agent` | Omitted entirely | Privacy/security retention and lawful-access requirements |
| Source-linked job/resource | Hot-only source link when authorized | Verified record-level archive index/lookup cannot be inferred from bundle presence |
| Retention/hold decision | Fallback proposal **365d hot / 3650d archive**, paused | Actual legal/contractual retention, investigations/holds, min/max/purge authority **not decided** |

`redact_operational_text` conservatively removes common credential-shaped
patterns but cannot prove that arbitrary prose, target IDs or source
references are not sensitive. Do not label the minimal archive as
complete/exhaustive original evidence, fully anonymized or safe for broad
bundle distribution.

## Effective access contract (current vs desired)

- **Current interim gate:** only an authenticated Local Database Super
  Admin can enumerate, preview, save policy or manually run `audit_event`
  archive-only. These operations still require the canonical Data Lifecycle
  RBAC permission.
- **Current DENY:** all archive data/manifest download even with
  `platform_operations.export_data_lifecycle`, all automatic scheduling,
  all hot cleanup, all archive-object purge, all per-record archive search.
- **Future requirement:** source-specific permission must be checked on
  **every** archived record before drill-down/export; a bundle containing
  mixed source types cannot be downloadable under a single unrelated
  permission. Default deny on unclassified/unknown producer, missing owner,
  inactive source, revoked role or absent verified record index.
- The Archive History page displays **bundles**, not a guarantee that a
  particular AuditEvent or JobExecution exists in that archive. This is
  separate from job archive lookup #1416.

## Approval checklist and dependencies

1. Enumerate **all** AuditEvent constructors/writers, source/action
   taxonomy, authoritative producer teams and current permissions. Resolve
   ambiguous/unknown patterns and privileged service identities.
2. Perform source-owner privacy/security classification for every field,
   especially free-form summaries, target keys, metadata, actor FK and
   legal holds. Determine archival content sufficiency and deletion rules.
3. Propose per-source hot/archive retention and expiry/hold handling.
   No uniform 365/3650 mandate until a human governance decision.
4. Determine an authorized read model for mixed-source archive records and
   how revocation is respected; only then consider export permission.
5. Prove positive/negative authorization for Local/LDAP, Super Admin,
   jobs-only, tenant-only, TLS governance, source-disabled and unknown
   producer. Test nested secrets in summaries/metadata, corrupted bundle,
   archive expiry and restored/deleted principals.
6. Pass real PostgreSQL, checksum/manifest, permission, failure-injection
   and high-volume tests, followed by explicit human acceptance.
7. Only after #2891 acceptance can #2892 propose indexable cold
   record lookup and verified hot compaction. Keep `cleanup_supported=False`
   and the global export/purge blocks until that later admission.

## UAT while source security is pending

A **Disabled** policy is expected. Preview is allowed to the authorized
Local Database Super Admin. For **approved synthetic UAT evidence only**,
enable and save `archive_only` to run a manual archive and disable after
testing. Policy enablement does not authorize scheduler, export, cleanup,
or archive-object purge. Do not use real patient, customer, credential,
personal IP or production security audit data for this interim UAT.

Evidence required for issue acceptance: exact Git SHA, database/source
fingerprint, role/user classification, owner sign-offs, authoritative
retention decision, privacy review, checked UAT cases and reviewer.
Official Developer Check / Full Admission / staging / production HOLD.
