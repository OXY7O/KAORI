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

## Guarded Capsule G4 canonical Released finalizer source — #1230

`capsule_release_finalizer.py` and the existing Release wizard now expose
a separately confirmed G4 route only when the committed G3 execution
claims exact complete provider handoff. The UI claim is informational;
the service **must** independently pass every guard before writing
canonical governance. The finalizer does **not PATCH/DELETE/create**
Kubernetes objects.

Under locked, adopted, Ready Tenant/Namespace generations it verifies:
independently approved exact Release plan; current successor X.509
identity and Kubernetes scoped SAR; zero canonical dependencies; original
SHA-bound complete inventory; installed PostgreSQL write-once
START/terminal ledger role/trigger/WAL requirements; canonical 2-event
append-only chain with exact actor/plan/worklist/readback; and exactly
one fully verified G3 execution outcome. Then it uses fresh typed
Kubernetes GET across the original Capsule CR, every Namespace, every
ResourceQuota/LimitRange/RoleBinding, plus full GlobalResourceQuota
LIST/read-back. Only exact successor-owned metadata-only transfers are
accepted; original spec/policy, UID, foreign ownership and preservation
digests are revalidated. A terminal proof row lacking authenticated
resource-specific consent or controller origin fails closed.

Only upon complete proof does one guarded DB transaction set Tenant
`lifecycle_status=Released` and each governed Namespace
`provisioning_status=Released`, record generation-specific immutable
lineage/audit and preserve original provider objects. Capacity accounting
uses KAORI's existing `capacity_allocation_state` terminal-lifecycle
filters: both Released Tenant and Released Namespace stop reserving
logical headroom **as a consequence of the same DB commit**. No manual
budget subtraction, historical profile deletion or double release occurs.
Predecessor IDs and resource profile history remain intact.

**Source is installed but G4 is not PASS.** Current #1229 only has
G1/dry-run, disabled START and disabled one-object provider PATCH
primitive; there is no true G3 execution receipt satisfying these
requirements. Consequently a synthetic `verified=true` flag, an
incomplete AuditEvent, an uninstalled/mutable ledger or a partial outcome
cannot yield a legitimate Capsule Released row. Tests and live UAT are
still separately held.

## Capsule Released successor handback source — #1231 (G5, pending G2–G4)

`capsule_successor_handback.py` provides a real, explicitly confirmed
Platform Admin handback route and Violet/HTMX Released-Tenant workspace
form. It remains unavailable for ordinary Ready Tenants: it requires an
already canonical `Released` Capsule generation and complete counted G4
`release_mode=managed_handoff` and `provider_handoff_verified=true`
evidence. This source is **not** a bypass around the unfinished G2/G3
executor or #1230 finalizer.

The handler requires the original approved Release plan, current authenticated
Kubernetes X.509 identity and scoped get/patch SAR, exact CR/Namespace
UID/resourceVersion, all transferred ResourceQuota/LimitRange/RoleBinding
targets and provider/foreign resources explicitly preserved. It verifies
the CR and every preserved related object before any metadata mutation,
commits a single durable **in-progress** AuditEvent before the first provider
write, then for every successor marker removal performs JSON Patch
`test` on UID/resourceVersion/full labels,
`dryRun=All`, preservation validation, fresh GET, one conditional live
PATCH and a fresh authoritative GET. Related controls go before Namespace;
the Capsule CR/spec, foreign quota/RBAC/workloads, ownerReferences, and
external labels are never patched. After all targets the source rereads
the CR and preserved resources; any drift fails closed.

An incomplete/unknown provider outcome aborts further PATCH and produces a
recovery-required receipt; an existing handback START prevents automatic
retry (including after process interruption). Only complete verified
provider scope and locked existing `Released` Namespace generations may
write `handback_governance` evidence with precise current CR RV and each
Namespace's own RV. The released predecessor stays Released and immutable;
Re-Adopt still requires a **new** Discovery and distinct explicit Adoption
authorization. The normal GET reads committed handback evidence only.

Source-only implementation and regression tests are authored but **not
runtime validated**. Actual ability to initiate this route depends on a
valid previous G2/G3 handoff, G4 finalizer, installed infrastructure,
CI/CD/security gates, separately authorized UAT and human acceptance.
It must not be represented as a complete working Release→Re-Adopt result
until those operations have been executed and verified.

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

## Capsule CR versus Namespace handback identity — source correction

`_released_predecessor_evidence` now selects the historical **cluster-scoped
Capsule Tenant CR handback resourceVersion** directly, instead of wrongly
resolving it through the Native Tenant's per-Namespace version map. Native
Tenant identity remains Namespace-scoped, and its existing
`provider_resource_versions[namespace]` verification is unchanged.
Released Namespace generation verification continues to use the separately
stored Namespace-row handback `resource_version`; no UID-only fallback or
handback guard relaxation is permitted. Focused positive lineage regressions
are authored but **not run**. This fixes one G5 source correlation bug, not
Capsule successor handback implementation or UAT admission: G5 remains blocked
by the unfinished G2/G3 executor and G4 finalizer.

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
