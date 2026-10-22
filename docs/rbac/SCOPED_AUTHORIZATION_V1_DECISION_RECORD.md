# Scoped Authorization v1 — decision and migration review record

**Status: ACCEPTED DESIGN BASELINE — implementation NOT admitted.**
Human acceptance of D1–D5 is recorded in #724 on 2026-10-23 (authority
comment https://github.com/OXY7O/KAORI/issues/724#issuecomment-6352000999).
The Role→Permission prerequisite, allow-only default-deny scoped layer,
User-first principal, no implicit inheritance, audited sensitive admission,
and RBAC-preserving migration are now **accepted architecture**. Detailed
storage/permission keys, grant administration and approval integration,
IdP group evidence, read-audit transaction/retention, cache/revision mechanism,
and cutover/rollback implementation must be reviewed under bounded issues.
No evaluator, migration, scoped grant, Vault Secret Registry route or UAT
acceptance is implied by this document.

**Authority:** #638 security, #724 scoped authorization, #641 identity and
break-glass; #714 Secrets & PKI, #2597 RBAC, #2688 implementation blocker,
#2678 unpublished Secret Registry; current final-locked Access v1
(`docs/architecture/ACCESS_OWNERSHIP.md`,
`docs/design/KAORI_ACCESS_LOCK_V1.md`), current RBAC/Authentication/Activity
Audit authorities. Decision children: #2712 lifecycle, #2713 principals, #2714
scope hierarchy, #2715 audit, #2716 migration. The #724 accepted decision comment is the governing authority for D1–D5;
this record preserves design details and the implementation gates.

## 1. Current implementation facts (verified in review source)

- `User.has_permission(key)`: local database `is_super_admin` returns true
  for a **global permission**; other users require an assigned **active**
  normalized Role containing the key. Missing/inactive role denies. No
  legacy slug fallback and no current resource-policy enforcement.
- `permission_required` and `any_permission_required` are HTTP guards
  based on the above **global** permission check. A template/nav hide cannot
  replace a server-side resource filter.
- Permission source of truth is the code-owned
  `app/definitions/catalogs/access/rbac/access.yaml`; protected default
  role seeding and custom roles remain canonical. `flask seed-rbac` does
  not derive per-resource grants, nor backfill `role_id` from legacy slugs.
- KAORI User has one `role_id`; an IdP can assign
  `IdentityProvider.default_role_id` and links an external identity through
  `ExternalIdentityLink`. No first-class approved external-group scope
  evaluator exists.
- Activity Audit presentation is owned by `app/access/activity_audit`.
  Shared committed operational evidence belongs to
  `app/platform_operations/notifications`; hot `AuditEvent` sources have
  separate access/retention boundaries, per Access final lock.
- An internal `app/secrets_pki/scoped_registry.py` exists **unpublished**;
  its synthetic `ScopedRegistryDecision` is NOT a persisted grant or
  permission evaluator. There is no authorized Secret Registry/Detail route.

**Documentation reconciliation:** historical RBAC architecture/flow/security
text described a legacy role-slug fallback and seeding behavior which the
current normalized `User` and `seed_default_rbac` code do not provide.
The accompanying docs-only correction describes this observed behavior; it
does **not** introduce a new authorization policy.

## 2. Agreed direction — already accepted in #724

1. **Permission = WHAT**, **Scope Policy = WHICH resource**; effective
   permission is an independent prerequisite.
2. Default deny for resource-scoped operations. Initial bias: **allow-only**.
   Do not encode object IDs into permission keys, create domain-local ABAC or
   infer grants from ownership/Team membership.
3. Canonical KAORI User and approved external-group binding are the intended
   human subject families. Service Accounts wait for #641. External IdP owns
   group membership; KAORI owns its admitted authorization decisions.
4. Server-side consistent filtering **before** rows/counts/search/exports,
   HTMX, worker/job and API outputs; cross-domain correlation intersects
   owning-domain permissions and resource grants.
5. Privileged authorization, action approval/step-up and provider execution
   are distinct. Tenant-to-Kubernetes provider RBAC remains independent.
6. Existing effective global access is not silently revoked or elevated
   by migration. Break-glass follows #641, never an invented scoped bypass.

## 3. Accepted D1 — policy identity and lifecycle (#2712)

**Candidate identity:** immutable opaque policy UUID, monotonic revision,
unique permission key, subject selector, exact resource selector, grant
effect = allow (v1), scope schema version, issuer/approver actor IDs,
effective_at / expires_at UTC, change reason and sanitized provenance.

**Candidate state progression:**

```text
draft → active → suspended → active (explicit re-admission)
               → revoked (terminal)
active → expired (time-bound, terminal)
draft → withdrawn (terminal)
```

Only approved **active** policy revisions whose effective time is current
can grant access. Unknown status/expiry, deleted resource, future-dated
approval, inactive subject or invalid reference denies. Never silently
reactivate revoked or expired policy. Content changes create a *new revision*
with reason and optimistic version check, not mutable grant history.
Revocation/suspension should take effect on the **next authorization
decision**; avoid a session-stored permit or unchecked cache.

**Accepted:** sensitive grant creation and activation require separate
maker-checker approval, while authorized revocation must be immediately
effective and durably audited. **Implementation detail pending:** which
canonical administrative permission keys and approval service implement this,
explicit scheduled expiry/reinstatement mechanics, #641 break-glass action
requirements and revision-safe cache invalidation. Approval/
execution boundaries under #641 remain independent.

## 4. Accepted D2 — principal and external groups (#2713)

**Accepted initial enforcement:** authenticated, active, non-deleted
`User.id`, with active normalized assigned Role and actual permission.
Do not use username, email, display name, Team ID, Vault AppRole identity
or unvalidated request subject as a grant key.

**Approved-direction but staged external-group family:** external provider
identity and immutable group object identifier; normalize against the
issuer/provider binding, with explicit membership provenance, freshness,
revocation, role prerequisites and identity-link reconciliation. Unknown,
stale, missing or conflicting membership must not grant. Avoid JIT role
mapping as an implicit per-resource grant.

**Deferred:** service account subject/admission under #641; group activation
until authoritative group evidence is contractually defined; worker tasks
must convey a qualified originating actor or separately governed system
identity instead of fabricating an authenticated User.

**Not decided:** acceptable IdP claim/group synchronization freshness,
group ID naming/issuer authority, cached membership lifetime and provider
outage behavior beyond fail-closed resource admission.

## 5. Accepted D3 — resource scope and inheritance (#2714)

**Stage 1 scope registry:** exact `integration_instance` identity using
canonical `IntegrationInstance.id`, not a Vault label/endpoint, namespace
string, Secret path or permission-key suffix. Provider identity is a
qualified attribute, never a separate product-wide authorization model.

**Accepted inheritance for v1:** **none**.

For high-sensitivity KV v2 record, Secret detail, path-sensitive search,
graph or export: a bare instance-level permit is **not** an implicit grant
for every namespace/mount. Require a specifically admitted exact nested
resource context, represented conceptually by the complete
`(instance_id, provider_namespace, mount)` tuple. Precise selector
persistence/normalization and whether one policy may cover several explicit
tuples need acceptance; no wildcard, regex or automatic `*` grant.

General provider configuration continues under existing
`integrations.manage`, but does not authorize sensitive Secret metadata.
A valid Vault ACL permits upstream API access, **not** KAORI viewer access.
Current anonymous, capability-wide *safe aggregate* pages stay governed
by existing RBAC until individually reviewed under the migration plan.

Cross-domain joins require **both** domain permission and source-appropriate
scope before counts, rows, details or downstream enrichment are computed.
No unauthorized source existence, path, name, count or guessed identifier
should be returned by a resource-specific denial.

**Not decided:** registry inheritance matrix outside Secrets & PKI (Service,
Tenant, Asset, Cluster), namespace/mount selector storage, UI for explicit
grants, treatment of HA node/Enterprise Vault namespaces and child scope
revocation. All must be tested rather than derived from navigation hierarchy.

## 6. Accepted D4 — authorization decision and audit (#2715)

Reuse KAORI Access Activity Audit ownership and the existing shared committed
notification/evidence boundary; domain operational evidence and AuditEvent
source reads retain their own access controls. Do not create a Vault-local
authorization log or expose full global decision context to ordinary viewers.

**Proposed sanitized decision envelope (not a DB schema):**

| Field | Meaning |
| --- | --- |
| `decision_id`, `occurred_at`, `request_id` | Correlation, UTC time, trace |
| `actor_kind`, `actor_ref`, `delegation_ref` | Human/qualified system origin |
| `permission_key`, `role_ref` | Existing permission prerequisite |
| `scope_type`, `resource_ref` | Canonical *authorized* opaque target |
| `policy_ref`, `policy_revision` | Effective grant provenance if qualified |
| `result`, `reason_code` | Allowed / denied / unavailable; sanitized |
| `operation_family`, `job_execution_ref` | HTTP, HTMX, worker or API correlation |

No Secret names/paths/versions/contents, provider URLs, credentials, raw
query selectors, external-group claims or raw body/errors. Keep audit
permission and data retention separate from domain read permission.

**Accepted required event priority:** persist every sensitive policy create/activate/update/
revoke, grant approval and sensitive mutation/admission; ensure resource-scope denies
remain observable and correlated without enabling high-volume sensitive
log replay. Hot audit row budget and archival policy must reuse approved
Data Lifecycle controls. Audit sink unavailability must **never turn deny
into allow**. **Accepted:** sensitive scoped reads and provider mutation/admission requiring
committed audit fail closed if audit persistence fails. Existing non-sensitive
reads keep their prior audit contract pending separate cutover. Sampling and
retention specifics must never waive mandatory sensitive-read evidence.

## 7. Accepted D5 — RBAC-preserving migration (#2716)

| Phase | Proposed activity | Mandatory gate |
| --- | --- | --- |
| 0. Baseline | Enumerate current active users/roles/IdP defaults, Super Admin, permission dependencies, route+HTMX/job/report contracts and effective access | Sanitized approved baseline, no runtime change |
| 1. Design/shadow | Assess *hypothetical* scope decisions independently of real responses; no source data or policy grants leaked to callers | Explicit labeled simulation, no enforcement |
| 2. Grant review | Derive only **exact** approved target grants with named accountable owner; record access deltas and exceptions; do not bulk-allow all Vault | Signed/accepted grant list, no unexplained elevation or revocation |
| 3. Bounded cutover | Convert only separately approved route/service/workflow paths to permission + scope; retain old global-only endpoints unchanged until each cutover | Functional negative/security tests, parity matrix, cache/revocation proof, staging UAT |
| 4. Acceptance | Validate source-specific access/denial for real roles, workers, JIT, API, browser and reports before retiring compatibility | Exact SHA Developer Check, Full Admission, UAT + human acceptance |

**Crucial separation:**

- **Existing routes:** do not automatically swap global RBAC for default
  deny; route-by-route design and explicit preservation of previously
  effective authorized access must precede enforcement.
- **New sensitive routes:** default deny on day one until both permitted
  action and exact approved resource scope exist. No implicit grandfather
  policy derived from a global `secrets_pki.view`, `integrations.manage`,
  Admin role or Super Admin.
- **Rollback:** restore *only* the previously approved global-only
  endpoints where safe, retaining their original effective permissions.
  New per-Secret routes must remain denied/disabled if scoped policy is
  unavailable; never roll back to unscoped data disclosure.
- **No automatic migration:** neither `flask seed-rbac` nor legacy role
  fixtures should fabricate broad resource policy rows. Migration must be
  reviewed and operator-controlled with row-level grant evidence.

**Required parity matrix** before cutover: active Viewer/Operator/Editor/
Admin/Auditor, active custom roles, inactive role, missing role, local
Super Admin, external JIT mapped roles, deleted/disabled users; old/new
permission and source-scope coverage, explicit effective grants, denied
counts, backend worker/HTMX links and cross-domain joins. Differences are
reviewed as FAIL/rework, not tolerated silently.

## 8. Authorization sequence — proposed shared contract

```text
Authenticate human / qualified system origin
  → active admitted identity and session / worker context
  → existing Role → Permission prerequisite
  → resource-scope registry selects exact target identity
  → active, effective, versioned approved allow policy
  → exact resource + optional nested-scope match (NO implicit inheritance)
  → authorized query restricted BEFORE COUNT / PAGE / GRAPH / EXPORT
  → independently applicable approval / step-up if mutating
  → permitted domain operation
  → sanitized committed decision/audit evidence
```

Invalid role, unknown policy, revoked/grant mismatch, stale source, absent
scope, failed authoritative group membership or unknown resource must
**deny**. A same-name or same-path Vault Secret on another instance never
matches by inference. Enforce consistency across HTTP, HTMX, background
jobs and future APIs, and test a policy revocation between read and
execution with fresh admission.

## 9. Architecture acceptance and bounded implementation gates

- [x] #2712 lifecycle, maker-checker sensitive grant and immediate audited revocation **principles accepted** under #724.
- [x] #2713 User-first principal, external-group staged admission and no implicit Team/service-account grant **accepted**.
- [x] #2714 exact IntegrationInstance and explicit nested scope/no inheritance **accepted**.
- [x] #2715 sanitized Access-owned audit and sensitive fail-closed persistence requirement **accepted**.
- [x] #2716 preserve-access baseline, shadow, explicit grants, guarded cutover and fail-safe rollback **accepted**.
- [x] #724 acceptance recorded by accountable human; #641 break-glass remains separate and never grants implicit scope.
- [ ] Bounded implementation issues have reviewed field/schema/API/index/permission/revision and grant-administration contracts; #724 is not a bulk implementation issue.
- [ ] Audit persistence transaction/failure mode, external-group freshness, and migration baseline technical designs reviewed before enabling associated execution.
- [ ] Exact-SHA Developer Check, security negative tests, Full Admission, real PostgreSQL/Vault/IdP UAT and human acceptance are recorded for runtime work.
- [ ] New sensitive Secret Registry, Detail, search, export, report and graph routes remain unpublished until authoritative evaluator, audited grants and scoped filtering have been admitted.

This accepted architecture is **not** a currently active authorization system,
permission change, provider credential, database migration or UAT PASS. Existing
global RBAC remains in force until the approved per-route cutover.

## 10. Initial policy storage candidate — #2723 review-only

The first implementation slice adds `access_scope_policies` and
`access_scope_policy_revisions` under the existing canonical Access models
and Alembic chain. The schema records exact User, permission, IntegrationInstance
and optionally a namespace/mount child tuple, UTC validity, policy identity,
revision, approval actor and lifecycle. SQL CHECK constraints reject impossible
levels, wildcard mounts, nonpositive revisions, invalid intervals, and
an active row lacking a distinct approver. **It seeds zero grants.**

This remains *persistence only*: the current revision pointer and append-only
revision semantics require the governed #2724 service; SQL CHECK constraints
alone do not establish full approval, audit, freshness or grant eligibility.
No evaluator, worker/HTTP route, Secret Registry or provider identity read is
turned on. The grant administration, mandatory durable audit, revision/cache
invalidation and user access migration require #2724–#2726 and exact-SHA
PostgreSQL/DevContainer security/UAT evidence. Repository source merge is not
migration execution.

## 11. Governed grant lifecycle backend candidate — #2724

The Access-owned `app/access/scoped_grants.py` supports **service-only**
request → independent approval → immediate versioned revocation. The service
reuses active KAORI User/Role permissions, checks the canonical IntegrationInstance
and approved Vault KV v2 namespace/mount, requires an existing `secrets_pki.view`
permission for the principal, and uses **both** existing `roles.manage`
and `users.manage` for its provisional administrative guard. Neither
`integrations.manage`, ownership nor `is_super_admin` alone qualifies.

Mutations call the existing `stage_operational_activity` evidence writer
and commit the revision pointer and sanitized notification in **one database
transaction**. Failure to stage/write mandatory audit rolls back the policy
transition, instead of using ordinary nonblocking Activity Audit notification
delivery. The audit stores opaque policy identity/revision and canonical
IntegrationInstance ID, not Vault Secret values, mount/path or credentials.

This is **not yet exposed through any UI, public API or worker**. The caller
must prove the authenticated initiating actor at its future boundary; a
service method parameter is not itself session authorization. The D1 admin
permission pair is a bounded existing-taxonomy candidate pending Access
review, not a public grant-management delegation contract. This service
does **not** evaluate Secret reads, authorize Vault access, activate external
IdP groups or replace #641 break-glass. Exact-SHA unit/integration tests,
database role privileges, review of committed audit atomicity, safe
notifications and real PostgreSQL/DevContainer UAT are still mandatory.

## 12. Non-enforcing RBAC parity and route admission evidence (#2726)

The Access-owned `compare_scope_parity` reports only whether an actual
active user's legacy global permission and exact-scoped read would agree.
It does not change the current HTTP/HTMX/worker response or grant policy,
and `summarize_scope_parity` never emits user identity or Vault source
identity. An unavailable scope evaluator is **not** accepted as parity.

| Boundary | Current enforcement | Proposed cutover |
| --- | --- | --- |
| Existing Secrets & PKI dashboard | Existing global `secrets_pki.view` | Preserve unchanged until separate route review |
| Existing safe capability Inventory aggregates | Existing source-owned/global permission contract | Preserve unchanged; do not silently add resource deny |
| Existing Vault provider Integrations registry | Existing `integrations.view` / `integrations.manage` | Provider operation and Scope Policy remain independent |
| New Vault per-Secret Registry/Detail/search | **Unpublished** | Only exact current User+Role+child-scope admission with committed sensitive audit |
| New sensitive report, export, graph, job | **Unpublished** | Independent domain and source-scope intersection + audit |

Review the *actual active* protected/custom roles, IdP/JIT mapping,
disabled/deleted user, local Super Admin, revoked/future policy, incomplete
Vault collection, cross-source counts, and independent endpoint denial in
PostgreSQL before considering any flip. No bulk grant backfill and no
environment toggle to bypass the evaluator are added in this phase.

**Cutover status: NOT ADMITTED** (source-only review). Final approval requires
Developer Check, full admission, exact SHA UAT including revocation lock
and audit failure, visual QA, and explicit human acceptance. Rollback for
new Secret route = disable the route; never restore an unscoped query.
