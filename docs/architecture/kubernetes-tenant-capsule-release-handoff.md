# Capsule Release — guarded handoff and recovery source boundary (#1229)

Status: **DevContainer source-review slice; provider execution NOT admitted**.
Parent #991; prerequisite source #1227 and #1228. Neither merge nor committed
successor acceptance source is actual X.509 consent or provider authorization.
Target integration: `kaori/review/staging-uat` only. No developer check,
pytest, Ruff, pyright, CI/CD, DAST, live API UAT, promotion or deployment until
a separate explicit instruction.

## Authoritative inventory and transfer model

Capsule Tenant `capsule.clastix.io/v1beta2` is **cluster scoped** and continues
to own Tenant spec, quota, limitRange, owner, RBAC and future namespace policy.
The approved SHA-bound Release plan carries exact Tenant CR UID/resourceVersion
and full canonical spec digest plus each governed Namespace UID/resourceVersion.
It is not permission to PATCH Capsule Tenant spec or replay Native handoff.

The review-only `capsule_handoff_contract.py` implements:

- Pure bounded scope validation: exactly one approved Capsule Tenant CR, between
  one and thirty Namespace records, unique kind/name, exact UID/RV, authority,
  ownership classification and canonical Capsule spec SHA-256.
- A no-write Capsule CR preservation assertion: exact CR identity, exact
  spec SHA, no unreviewed KAORI CR markers. A source-marked CR with an
  unverified KAORI owner is **blocked** rather than stripped or re-labeled.
- A Namespace-only conditional JSON Patch plan: `test` UID, resourceVersion
  and complete original labels; `remove` only the known KAORI label keys;
  `add` the independently verified successor `app.kubernetes.io/managed-by`
  value. Capsule membership labels and all foreign labels, annotations, spec,
  quota, ownerReferences, finalizers and workloads remain untouched.
- Fail-closed foreign/mixed ownership, unknown `kaori.io/*` control markers,
  ambiguous Capsule membership, unsupported scope kinds, invalid owner values,
  missing identity and provider drift. A Namespace without a trusted Capsule
  membership label is not eligible for metadata transfer.

`capsule_handoff_dry_run.py` has **no route or background execution**. An
explicit caller can supply provider clients to preview the Namespace-only
conditional patch with Kubernetes `dryRun=All`; it then re-reads the live
Namespace and Capsule CR to compare identity, spec and retained state. Its
receipt is always `preview_observed_coverage_incomplete`, with
`dry_run_complete=false` and `provider_handoff_verified=false`. Even with
the supplementary read-only inventory described below, this is **not** an
admitted end-to-end provider handoff dry-run. No caller may interpret the
helper result as sufficient handoff proof.

`capsule_handoff_recovery.py` classifies exact Namespace baseline/read-back
into `pending_provider_transfer`, `provider_markers_transferred` or
fail-closed drift/partial ambiguity; its bounded aggregate reports
`provider_handoff_not_started`, `partial_handoff_recovery_required` or
`provider_markers_transferred_consent_unverified`. All recovery results have
`auto_retry_authorized=false`, `resume_authorized=false`,
`provider_handoff_verified=false`, `release_authorized=false`.

## Read-only related resource inventory — follow-up source slice

The existing committed Capsule preflight now calls
`capsule_handoff_related_inventory.observe_capsule_related_inventory` only
after it has correlated its exact governed Namespace records. For each
Namespace, the observer reads complete **bounded** Kubernetes lists:

- `ResourceQuota` and `LimitRange` from the Core API;
- `RoleBinding` from Kubernetes RBAC API;
- Each authoritative LIST resourceVersion, bounded count and every object's
  UID/resourceVersion, origin class, SHA-256 policy digest and SHA-256 retained
  metadata digest; never raw RBAC subjects, quota specs or authentication data.

Records are classified as `capsule_provider`, `foreign_preserved`,
`kaori_correlated`, `ambiguous_kaori` or `unattributed`.
Unknown and conflicting ownerReferences, foreign controller claims, unknown
KAORI markers, residual KAORI quota/limit controls or Access Grant RoleBindings,
incomplete LIST/pagination, duplicated scope, malformed spec and unbounded
inventory create **blocking evidence**, not silent adoption.

The committed result is placed in `capsule_related_inventory` for Capsule
only (Native evidence remains unchanged). The deterministic SHA-256 of scoped
objects **and LIST revisions** is bound into the existing Capsule Tenant
handoff component as `capsule_related_resources_sha256`; its existing
`handoff_fingerprint` now detects drift without changing route or database
schema. An incomplete read never emits a trusted resource digest.

**Remaining hard stop:** Kubernetes namespaced lists do not prove
cluster-scoped GlobalResourceQuota variants, the exact Capsule CR-to-generated
RoleBinding lineage, or the complete independent successor acceptance/execution
contract. When actual Capsule handoff is required, preflight explicitly
retains a non-allowlisted blocker until those controls are proven. The
legacy observation-only Release path is not granted a new executor.
The preview remains `dry_run_complete=false`. No provider write is introduced.

## Cluster-scoped quota and Capsule RBAC intent lineage — follow-up

`capsule_handoff_authority_inventory.py` adds **read-only, bounded**
observation for `globalresourcequotas.capsule.clastix.io` using the served
`v1beta2` API (with a `v1beta1` fallback only after 404). The observer binds
the full cluster LIST resourceVersion, each CR UID/resourceVersion, SHA-256
canonical spec and metadata, and source API version. It never clones or
updates quota. Missing CRD, partial/paginated/oversized LISTs, malformed
specs or unsupported tenant selector expressions fail closed. Foreign quota
objects are fingerprinted without claiming their management.

Capsule Tenant `spec.rules[].permissions.bindings` now has a **candidate**
lineage comparison against effective KAORI-correlated RoleBindings. The
comparison accepts only explicit Namespace-name selectors, unique bounded
scopes, exact ClusterRole reference and canonical subject identity. Its
committed receipt contains opaque SHA digests and counts, **not** subject
names, authentication material or raw role policies.
`additionalRoleBindings` with KAORI grant markers cannot be admitted as
an unbounded successor handoff. Mismatched effective RoleBindings, residual
KAORI access grants, unknown selectors and duplicated claims block.
Matching content is only `contract_correlated`; it does **not** prove
which controller created a RoleBinding or that the successor accepted it.

Both complete observations are committed under the existing Capsule
`capsule_related_inventory` evidence and SHA-bound into the same Capsule
handoff fingerprint via `capsule_shared_quota_sha256` and
`capsule_rbac_lineage_sha256`. The prior namespaced inventory digest remains
unchanged, and Native/legacy observation-only Release paths remain separate.
The existing non-allowlisted Release blocker remains until full provider
authority/transition evidence is available.

No route, provider write, persisted dry-run admission, executor,
Release transition or automatic recovery is enabled by this source slice.
Neither successful intent matching nor an unchanged fingerprint is consent.
Additional cluster-scoped Capsule GlobalTenantResource/resource-pool variants
remain subject to explicit version/capability admission rather than
being silently interpreted as a global quota.

## Required before completing #1229

1. Build on the SHA-bound Namespace and cluster-scoped
   GlobalResourceQuota observations: prove the actual Capsule controller
   origin of generated RoleBindings, authorize any other served shared-quota
   variants explicitly, complete exact KAORI allocation/access transfer
   worklist and corresponding authoritative post-transfer read-back.
   Never relabel provider-owned objects. Residual KAORI-owned ResourceQuota,
   LimitRange or RoleBinding remains blocked until its exact metadata-only
   transfer is separately admitted.
2. Bind a committed dry-run receipt to the *current* independently approved
   plan SHA, provider fingerprint, live zero-dependency preflight, exact actor,
   accepted successor and fresh registered X.509 SelfSubjectReview/SAR with
   validated Kubernetes TLS. Revalidate immediately before each potential
   provider operation.
3. Add a separately confirmed guarded **live executor**, not available on
   ordinary GET, with an append-only `started` AuditEvent before any PATCH,
   per-object conditional mutation, definitive provider read-back, and
   `partial_handoff_recovery_required` on timeout/conflict/crash. Do not
   retry unknown outcomes automatically; require a new explicit human recovery
   decision and proof of exact original scope.
4. Expose intentional operator review/confirmation UI only after implementation
   and security review; use existing CSRF, HTMX, RBAC and Violet patterns. Do
   not overload Native executor, Native finalizer, or Release Step 4.
5. Author provider API mock regressions and UAT matrix for changed/reused RV,
   UID replacement, missing permissions/TLS/X.509, partial patch, retained
   quota/LimitRange/foreign RoleBindings/owners, full spec drift, concurrent
   reconciliation, restart and stale consent. Execute them only after the
   gate hold is explicitly lifted.

## Current operating boundary

`kaori-demo` is **NOT Released**. Three release handoff blockers remain
operational; no Capsule provider handoff or independent human acceptance has
been executed by this source change. #1230 verified finalizer and #1231
controlled provider UAT remain blocked. Source inspection is not gate PASS.

No new backend endpoint, database migration, Kubernetes mutation, provider
execution, Released lifecycle state or automatic retry is introduced here.
