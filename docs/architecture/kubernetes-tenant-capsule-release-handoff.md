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
`dry_run_complete=false` and `provider_handoff_verified=false`. It is not
an end-to-end admitted provider dry-run because the current approved preflight
inventory does **not** enumerate namespaced ResourceQuota/LimitRange, Capsule
distributed RoleBindings, their origin, or every KAORI-managed allocation
control. No caller may interpret the helper result as sufficient handoff proof.

`capsule_handoff_recovery.py` classifies exact Namespace baseline/read-back
into `pending_provider_transfer`, `provider_markers_transferred` or
fail-closed drift/partial ambiguity; its bounded aggregate reports
`provider_handoff_not_started`, `partial_handoff_recovery_required` or
`provider_markers_transferred_consent_unverified`. All recovery results have
`auto_retry_authorized=false`, `resume_authorized=false`,
`provider_handoff_verified=false`, `release_authorized=false`.

## Required before completing #1229

1. Extend the **existing** Capsule provider handoff inventory with verified
   bounded ownership origins for every affected ResourceQuota, LimitRange and
   distributed RoleBinding; classify unknown and foreign ownership without
   relabeling provider-owned objects. Include exact Capsule CR relationship and
   preserve complete unchanged provider policy/spec in authoritative read-back.
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
