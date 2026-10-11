# Capsule Tenant Release & Re-Adopt — Minimum Secure Acceptance Baseline

**Decision:** Scope frozen for #991 / #1227–#1231 on 2026-10-11. This is a
**source-only acceptance contract**, NOT authorization to execute CI/CD, SQL
migration, Kubernetes API operations, provider handoff, Release or Re-Adopt.
Current integration target: `kaori/review/staging-uat`.

## End states (non-negotiable)

- **Provider-preserving Release:** an externally adopted, Ready Capsule
  Tenant moves to canonical `Released` **only after** independently accepted,
  fully verified handoff. Capsule Tenant CR, Namespace, workloads, Capsule
  spec (including quota, limits, rules), GlobalResourceQuota, provider/foreign
  ownership, RBAC and Kubernetes object identities are preserved. KAORI stops
  actively governing the released generation and releases only its own logical
  reservations **after** the canonical Released commit. Release is NOT
  Decommission, deletion, provider quota cloning or a database-only flag.
- **Explicit Re-Adopt:** fresh Discovery of the **same approved physical
  Capsule Tenant and Namespace identities** after verified Release, fresh
  provider authority and handback/lineage checks, new independent
  operator-approved Adoption, **new Tenant/Namespace governance generations**
  and immutable links to the Released predecessor. Historical Released rows
  stay terminal. Never auto-reconcile/re-attach, silently reparent, or create
  two live KAORI governance generations for one provider resource.

## Fixed binary gates (GO only when every required gate is PASS)

| Gate | Owner issue | Required PASS evidence | FAIL / blocked condition |
| --- | --- | --- | --- |
| **G0 — Eligible and dependency-free** | #991 / #1227 | Exactly one Ready, adopted Capsule Tenant; authoritative Capsule v1beta2 Tenant CR, bounded canonical entire spec, scoped Namespace/quotas/limits/RBAC/GlobalResourceQuota; source UID/RV and SHA fingerprint; zero active Access Grants/credentials/memberships, controlled allocations, integrations/exposure and other canonical Release dependencies | Managed/foreign identity ambiguous, unsupported quota/RBAC, active dependency, drift or incomplete LIST |
| **G1 — Human authority and successor** | #1228 | Current plan SHA/fingerprint, independent reviewer and explicit accepted Platform Admin successor; fresh registered X.509/TLS identity with exact SSR/SAR scope, actor separation, anti-replay consent and evidence of authority for each proposed KAORI-owned transfer | Claims based only on labels, managedFields, caller MAC or uncommitted IdP data; missing/stale/foreign consent |
| **G2 — Safe exact-scope provider handoff** | #1229 | Full per-object preservation/transfer decisions; KAORI-owned metadata-only conditional patch where strictly necessary; **server dryRun=All** then separately confirmed execution with fresh UID/RV/spec and foreign ownership guards; provider-owned resources and spec untouched | Any unapproved spec/quota/limits/subjects/roleRef/finalizer/owner change; UID/RV mismatch; unknown controller origin; no authorized dry-run |
| **G3 — Irreversible audit and definitive read-back** | #1229 | Installed and verified write-once attempt/batch/consent protection; START committed before first provider mutation; exact per-resource read-back of UID/RV, identity, spec, preserved resources, metadata and RBAC; no pending/partial/ambiguous outcome | Missing durable evidence, changed provider source, timeout/unknown outcome, residual KAORI control or automatic retry; manual recovery required |
| **G4 — Atomic Released finalizer** | #1230 | Fresh G0–G3 evidence and dependency zero-state rechecked under lock; single governed transaction commits Tenant+Namespace `Released`, capacity/accounting release, immutable lineage/audit; stop KAORI reconciliation and hide released generations from active governance | DB-only Released flag, existing partial evidence, provider drift, double capacity subtraction, recreation or destructive cleanup |
| **G5 — Safe fresh Re-Adopt** | #991 / #1230 / #1231 | Released predecessor and provider identity cross-checked; current Capsule/Namespace UID and RV read from fresh Discovery, exact original handoff or verified correction lineage, separate human Adoption authorization; new generation and back-link, no active duplicate | Missing/replayed handback, foreign owner, changed UID, stale RV, unresolved metadata residue, reused generation, automatic adoption |
| **G6 — Security/UAT acceptance** | #1231 | Authorized tests/CI/CD + controlled-cluster UAT for Release→Discovery→Re-Adopt, lost commit, partial PATCH/recovery, concurrent operations, bad X.509/SAR/TLS, reused/replaced UID/RV, changing Capsule spec, mixed ownership, idempotence and preserved workloads; explicit human sign-off | Any required negative test fails or is unrun, unknown provider aftermath, missing QA/evidence, unapproved promotion |

**Gates are conjunctive.** A source PR merged to review branch does not
satisfy any runtime PASS condition. #1227/#1228 source is integrated but
human/operator/runtime validation remains separate. Keep #1229 OPEN until
the executor can actually complete admitted dry-run, guarded operation,
partial recovery and definitive provider read-back. #1230 and #1231 stay
blocked by that evidence.

## Re-Adopt live resourceVersion caller wiring (P0 source corrected; runtime HOLD)

The Capsule-specific caller defect identified during baseline freeze has
been corrected in source: `_adopt_capsule` now supplies the *live*
Capsule Tenant CR `resourceVersion` to
`_released_predecessor_evidence`. For namespaced resources,
`_capsule_namespace_records` now completes its bounded, duplicate-free
UID/RV inventory scan, then verifies **every** Released Namespace
predecessor with that Namespace's own live `resource_version` **before
building any new-generation KAORI governance record**. This follows the
already-established Native live identity pattern while retaining the
strict `_require_re_adoption_handback_for_managed_release` guard.
It neither substitutes old database RV for current provider evidence nor
accepts UID-only handback. Missing/stale/foreign handback remains FAIL,
and manual verification of any later provider correction remains required.

Authored-only regressions cover Capsule Tenant and multiple Namespace
live RV forwarding, no early record allocation for a later invalid
Namespace, generation/linkage preservation, stale/missing managed
handback and positive exact handback. **These tests have not been
executed. G5 remains NOT PASS pending G2–G4, CI/CD, provider-authorized
UAT and human acceptance.** New generation allocation takeover must
also be reviewed separately: the Capsule adoption path can establish
KAORI-managed profiles and is not an implicit provider read-only
operation.

## Scope-freeze and execution rules

**Must keep:** independent human authorization; exact provider
fingerprints and current UID/RV; resource-by-resource owner authority;
provider-spec preservation; prior-commit fencing and manual partial
recovery; atomic Released+capacity accounting; verified
Released→Discovery→new-generation Re-Adopt; security/UAT gates.

**Not independent blockers by default:** creating additional
cryptographic envelope formats, duplicate AuditEvent frameworks, more
proof tables, a bespoke IdP/MFA or Vault/KMS integration **if** the
existing approved KAORI authentication/audit/immutable storage can meet
the same concrete evidence and threat-model requirements. Never
replace authenticated identity, integrity, durability or anti-replay
with self-declared `verified=true`, a hash or user-supplied key.

**Work order:** (A) audit existing source against G0–G6 and record
P0 FAILs, (B) close G2/G3 with the minimum reviewable executor/read-back
vertical slice, (C) close G4 finalizer, (D) fix and verify G5
Released→Discovery→Re-Adopt lineage, (E) separately authorize and run
G6 security/UAT. New supporting abstractions need an explicit
specific gate/negative case they solve, rather than indefinite
architecture expansion. Native provider Release stays independent.

**Standing operational HOLD:** No pytest, Ruff, Pyright, CI/CD,
Developer Check, Full Admission, DAST, browser/DevContainer runtime
QA, Alembic execution, SQL operational writes, Vault/IdP secret
reads, Kubernetes SSR/SAR/dryRun=All/PATCH/live UAT, Released
finalization, deployment or staging/main promotion until separately
authorized by the operator. Demo `kaori-demo` is NOT Released.
