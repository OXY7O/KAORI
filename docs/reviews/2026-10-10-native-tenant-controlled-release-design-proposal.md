# Native Tenant KAORI-controlled Release / Re-adopt — design proposal

**Status:** ARCHITECTURE CORRECTED/ACCEPTED (2026-10-10): existing KAORI X.509 kubeconfig for provider execution; independent KAORI Platform Admin governance consent and Kubernetes SelfSubjectReview/SelfSubjectAccessReview for resource authority. Earlier external TokenReview successor proposal is **SUPERSEDED**. **Runtime/security UAT and Full Admission HOLD**.
**Accepted approach:** a privileged KAORI Platform Admin explicitly confirms Release after an independent reviewer, while the existing provider kubeconfig executes metadata-only handoff with fresh provider permission checks. Ordinary JumpServer/pipeline users do not administer cluster governance.
**Source authority:** #991 (under #982), #690 / #114 identity governance, #996 external identity observation, existing Native handoff #1009, current `docs/architecture/kubernetes-tenant-domain.md`, and `docs/reviews/2026-10-09-tenant-adopt-release-acceptance-matrix.md`.
**Workstreams:** #1047 trust/identity (this proposal) → #1048 provider executor → #1049 Released/re-adopt finalization. **Capsule stays out of scope.**

## Problem and invariant

A manually created Kubernetes Namespace and ResourceQuota may be adopted into KAORI. Native Adoption may then make controlled changes to provider allocation/ownership metadata. Existing KAORI two-actor approval commits only `acknowledged_pending_provider_handoff`, the Native dry-run uses `dryRun=All`, and the Native provider read-back explicitly records `external_successor_verified=false` and `release_authorized=false`. Existing `release_adopted_tenant_committed` deliberately allows only observation-only generations and fails closed when KAORI-mutated provider controls or allocations remain. Do not relabel that blocked situation as Released.

The desired outcome is a complete, non-destructive lifecycle:

```text
Native objects exist -> explicit Adopt -> KAORI managed allocation
 -> Review Release (committed inventory + blockers)
 -> Prepare Handoff (requester A, one active plan)
 -> Independent review (eligible B, one winning decision)
 -> Verified successor consent (trusted provider/IdP identity, separate authority)
 -> KAORI Execute Handoff (explicit mutation confirmation)
 -> verified Namespace/ResourceQuota/LimitRange read-back + cleanup evidence
 -> KAORI atomic governance Released (provider objects retained)
 -> fresh Discovery/Adoption -> next generation + immutable Released lineage
```

The **one primary operator action after approvals** should be **Execute Handoff & Release**. Backend sub-stages remain separately auditable and may stop in a safe recoverable state, never claim a single atomic Kubernetes+database transaction.

## Minimal human operations without lowering authority

- The requester enters successor identity and change reference once and prepares the already existing plan. Free-text `successor_owner=platform-team` is an **identifier proposal**, not verified Kubernetes/IdP identity and not permission to execute.
- The independent reviewer uses the existing Work Inbox and `Acknowledge as Independent Reviewer`; the backend enforces a distinct actor and first-valid-approval semantics.
- Successor consent is an **authenticated, explicit attestation by a party genuinely authorized to accept ownership** for the exact plan/objects, not a third generic KAORI administrator approval. Reuse the existing SSO/IdP/provider trust boundary where admitted; resolve the external principal/group mapping against authoritative credentials/claims, not against KAORI display names alone.
- **Fast path:** when the independently eligible reviewer also has *separately verified successor identity/authority*, the reviewer may explicitly consent to successor responsibility in the same guided transaction, with **two separately recorded evidence facts and checks** (internal review versus successor attestation). One click may carry both only if that combination is approved under #690 and authorization/SoD checks. Never infer external acceptance from `tenant.manage`, `integrations.manage`, a RoleBinding, an IdP login alone, or the reviewer identity.
- Otherwise the verified successor receives one acceptance task in the existing Work Inbox and attests once. No Kubernetes CLI or handwritten label changes are required from any party.
- If there is **no trusted mapping** to a provider-recognized principal, display **Successor Identity Not Verified** and stop. Do not invent a trust source, accept a typed team name as proof, or bypass the gate for a Super Admin.
- The current **External Reference Unverified** ticket is optional supporting correlation only, not a replacement for the actual successor attestation.

## Trust and acceptance contract to admit before implementation

A trusted successor attestation receipt must be tied to:
1. Exact committed Tenant/cluster/provider/generation and current handoff `plan_sha256`.
2. Canonical successor identity (issuer, immutable subject/group/organization identity, audience, verifiable authentication provenance, timestamp), and explicit acceptance of responsibility; KAORI session role alone is insufficient.
3. Explicit authorized scope (Namespace plus ResourceQuota/LimitRange object list) and the immutable provider UID/inventory fingerprint; no wildcard or unreviewed resource.
4. At decision/execution time: active identity, non-revoked/unaltered role or external trust, allowed scope and current provider preflight read-back. Revalidate time-limited approval; do not silently reuse a 15-minute plan/approval after expiry.
5. Separation of requester A from reviewer B; successor identity/authority is an **additional verified attribute**, not a substitute for first-valid independent approval.
6. Committed, non-secret evidence traceability and audit actor attribution; failure, cancellation, supersession, race and replay protections. Avoid storing tokens/credentials in AuditEvents.

**Unresolved admission detail:** existing KAORI application login/SSO and Kubernetes authentication are separate domains per #690. #1047 must select and document an **existing or approved trust mapping** (for example a Kubernetes-recognized IdP subject or an admitted provider identity assertion) before the successor attestation can be called verified. A Kubernetes label, SubjectAccessReview alone, or operator-submitted external ticket is never proof of intent/consent. The mapping cannot be guessed from `platform-team`.

## KAORI-controlled Native execution and compensation boundaries (#1048)

The existing Native dry-run patch builder already selects KAORI-correlated Namespace, ResourceQuota and LimitRange metadata with UID/RV and label tests and preserves spec, foreign labels, annotations and immutable metadata. It **only previews** removal of KAORI markers. A future admitted executor must:

- Complete all preceding gates, run fresh complete dry-run, acquire the correct mutation authority and reconfirm provider identity/UID/RV before *each* bounded live Kubernetes JSON Patch. Use the provider client; no parallel custom executor and no unattended mutations on Registry GET.
- Use a deterministic **successor ownership representation** agreed with the identity authority. The existing read-back expects `app.kubernetes.io/managed-by=<verified-successor>`, not a missing manager label, so the live patch and the read-back must agree exactly. No broad deletion of external/foreign markers.
- Preserve Namespace/ResourceQuota/LimitRange names, UIDs, spec/allocations, annotations, ownerReferences, finalizers, foreign labels and workload. Do not create, delete, or replace provider resources.
- Record immutable per-object before/after UID/RV, patch intent, operation ID, actor, provider read-back and failure class. Kubernetes plus DB do **not** form a distributed transaction.
- If only one of two resources transfers, state is **Partial Handoff — Recovery Required**. Do not mark Released, free KAORI capacity, drop governance or blindly revert provider labels. A bounded resumable/reconcile path must check the authoritative current state and exact plan before continuing. If provider mutation succeeds but DB commit fails, record recoverability and require authoritative re-observation rather than assuming failure means no mutation.

## Final Release and Re-adoption boundaries (#1049)

After all resources are transferred, trusted successor attestation is current, provider read-back passes and KAORI-owned grants/credentials/active dependencies have been safely resolved under existing access authority, the canonical Release service may commit `Released`. No special second release model. Mark the retired Tenant/Namespace generation historical, remove only KAORI logical active allocation, stop KAORI reconciliation, preserve immutable audit/provider lineage, and do not delete the Namespace or quota.

Discovery must subsequently offer **explicit Re-adopt** only after fresh provider UID/RV, released-lineage checks and evidence that the successor relinquishes or authorizes the new governance claim. Do not let an external successor-owned Namespace become automatically adoptable by merely removing its label; do not silently reuse an old Tenant generation.

## Failure modes, validation and operational UX

| Situation | Expected behavior |
| --- | --- |
| Different approver attempts to replace pending handoff plan | Block under existing plan lock; review the current plan |
| Successor has only a KAORI role, free-text team or unverified external reference | Block execution; show missing trusted identity mapping |
| Successor authenticated but did not explicitly accept responsibility | Block execution; provider identity verification is not consent |
| Approved plan / identity / provider fingerprint is stale or changed | Refresh/re-review with governed plan renewal; never silently reuse |
| One Kubernetes object PATCH succeeds and the next fails | Partial Handoff; keep governance blocked; resume/reconcile from authoritative provider |
| Provider mutated but database commit fails | Recovery Required; reread source of truth before retry, no false Released |
| Provider specs, UID, foreign labels or RBAC altered unexpectedly | Block and require authoritative investigation; no Released |
| Full transfer proof exists but KAORI grants/allocations remain active | Block finalizer; execute governed cleanup/read-back first |
| Re-adopt attempted while externally owned or with changed UID | Block until explicit handback/preflight/lineage verification |

Recommended modal UX reuses Violet and existing Release Governance, Work Inbox and toast patterns. It should show exactly which gate is missing, a single primary action when eligible, detailed provider evidence in existing modal panels, non-destructive confirmation, partial failure/retry guidance, and committed progress without live provider polling on normal Registry reads. Default 5-row paging, light/dark, responsive and accessible keyboard/focus remain standard.

## Current safe DevContainer readiness projection (#1047)

The Tenant Management native dialog now presents five committed-evidence
checkpoints for adopted Native resources requiring provider handoff:
Release review, independent approval, verified successor acceptance,
KAORI provider transfer, and final Released / Re-adopt. The read model
`app/kubernetes/tenant/native_release_readiness.py` does not query Kubernetes,
issue external requests, mutate objects or confer any admission authority.
It checks committed plan/approval fingerprints, current 15-minute evidence
and Native dry-run status. External Reference Unverified and observed provider
markers **never** fulfill the trusted consent gate. The current #1047
identity-mapping contract remains UNAPPROVED, so the live executor, finalizer
and automatic Re-adopt checkpoints remain explicitly incomplete.

For the observation-only Release path, the existing native dialog offers
its ordinary Release action only if the latest Release preflight has no
blockers. Previously the control could be shown while all known provider
mutation blockers made the POST fail. This is a UI affordance correction,
not a Relaxed admission: the `release_preflight.py` backend remains the
only authority and continues failing closed.

**Do not claim the full lifecycle can yet pass UAT.** The gap is not a
missing click: #1047 must first admit a trusted Kubernetes/IdP successor
principal mapping; #1048 must execute and prove provider transfer; #1049
must then commit provider-preserving Released and validate new-generation
Adoption, including capacity and provider dependency cleanup. Current
DevContainer can exercise Adoption, pending/acknowledged approval,
dry-run and the blocked gate projection without provider mutation.

## Admission and handoff checkpoints

- **This proposal only:** documentation and issue decomposition; no feature flag, live patch, application permission, migration, Release bypass or provider mutation.
- **#1047:** review identity mapping, trusted successor acceptance receipt and SoD/fast-path proposal; obtain explicit security/architecture human acceptance first.
- **#1048:** implement admitted Native executor with existing checks/adapter, negative tests and mock/nonproduction Kubernetes mutation evidence; local-DevContainer review initially.
- **#1049:** implement guarded canonical Release/re-adopt changes, capacity/audit lineage and provider UAT; acceptance before `kaori/staging`.
- Developer Check, Full Admission, CI/CD, staging-server UAT, main promotion and release remain **HOLD** pending explicit authorization. Passing static contracts alone is not UAT.

**Decision requested of maintainer:** accept KAORI as the controlled Native provider executor and choose an *approved verifiable successor principal mapping* (with the one-click combined consent fast path only when the same independent reviewer is itself verified as the successor). Do **not** admit or turn on a live transfer based on this draft alone.


## SUPERSEDED historical candidate: #1047 Kubernetes TokenReview identity (removed)

The issue-linked review implementation `native_successor_identity.py` evaluates an
alternative to guessing KAORI SSO → Kubernetes identity mapping. For a Native
cluster, an explicit provider authentication token is checked against the
**same connected Kubernetes API server** using its TokenReview endpoint. The
API server, not a KAORI role or free-text handoff reference, asserts the
authenticated username, stable principal UID, and group membership. The
existing `successor_owner` value is interpreted **only for this candidate**
as an exact non-system Kubernetes group and a valid provider label value.
Unsupported group names, service accounts, missing UID, wrong cluster,
stale/changed plan digest, and unauthenticated tokens fail closed.

**This is an identity observation, not successor consent**: the review-only
helper neither accepts the responsibility attestation nor creates an AuditEvent,
stores tokens, adds an HTTP credential form, changes Kubernetes, or enables
Release. Its outcome explicitly sets `identity_mapping_admitted=false`,
`consent_verified=false`, and `release_authorized=false`. No KAORI
application account is considered equivalent to the authenticated Kubernetes
principal. No existing read-back or independent KAORI approval is promoted to
consent.

**Security decisions still required before adoption:** human review must
accept the exact group/owner mapping, safe proof-of-possession and transport of
short-lived provider credentials, TokenReview RBAC/audience/expiry semantics,
consent intent and separation-of-duties attribution, revocation/freshness checks
at each live mutation, fail-closed recovery and credential non-retention. In
particular TokenReview provides point-in-time authentication; it does **not**
prove independent acceptance, guarantee a future identity remains active, or
on its own authorize `#1048` patches. The current provider executor and
`#1049` finalizer remain explicitly blocked. No staging, production or live
provider mutation follows from this candidate.

Historical review-only TokenReview helper and corresponding tests were retired following the Platform Admin X.509 decision. The current tests live in `test_native_successor_acceptance.py` and `test_native_successor_handback.py`.


## #1057 expired acknowledged-plan recovery (review branch)

The five Native Release checkpoints intentionally report **currently valid**
evidence. An independently acknowledged plan remains immutable audit history,
but its 15-minute freshness and the provider preflight may expire, so the
checkpoint count can return to 0/5 without removing the recorded decision.

An expired acknowledged plan now has one explicit, non-mutating operator action:
**Restart Expired Handoff Plan**, available only to its original requester,
with existing `tenant.manage` and `integrations.manage` permissions, CSRF,
and an explicit confirmation. The service verifies the original plan SHA,
independent actor, approved fingerprint, nonfuture timestamps and expiry. It
commits a *fresh* authoritative Native preflight, proves the exact same
Tenant/generation/provider UID/resourceVersion and handoff fingerprint,
checks zero unresolved dependencies, and uses the existing Tenant row lock to
block races. If a read-back has already been recorded for that plan, or
the provider inventory has changed (including partial ownership transfer),
restart is blocked until explicit recovery review.

On success the service creates a **new plan SHA** and records
`supersedes_plan_sha256` as nonsecret AuditEvent evidence. The old approval,
external reference and dry-run remain in history but are not valid for the
new plan, which must be independently acknowledged again. No Kubernetes
mutation, successor consent, Release or Re-adopt authority is gained by
restarting the plan. The readiness UI distinguishes `Recorded · Expired`
from `Pending` and labels the counter as *active* checkpoints. A historical
acknowledgement must never be displayed as an executable current approval.

**Operational consequence:** this fixes the stuck screenshot state and makes
it possible to repeat provider preflight/review safely, but it is *not* a
substitute for the missing accepted #1047 trusted successor attestation, the
#1048 live transfer executor, or the #1049 verified Released finalizer/
successor-authorized new-generation Re-adoption.


## Final accepted identity correction → review-branch implementation (2026-10-10)

The **current** approved contract supersedes the bearer-token branch described
earlier in this historical design proposal. The user confirmed that KAORI's
registered Kubernetes provider connection uses a Base64-embedded X.509 client
certificate; the actual Kubernetes API reports principal `kubernetes-admin`,
group `kubeadm:cluster-admins`. Platform Admins perform Native and separately
authorized Capsule infrastructure administration; ordinary users only receive
delegated access through JumpServer, pipeline or scoped Tenant RBAC.

Current implementation follows issues #1047 → #1048 → #1049. Authorized
KAORI Platform Admin permissions, explicit per-plan administrative consent
and independent human review form the governance decision. Kubernetes
SelfSubjectReview + scoped SelfSubjectAccessReview on the **existing**
TLS-verified kubeconfig prove the executing provider identity and effective
get/patch permissions. There is no successor credential field, no
bearer/TokenReview user/group mapping and no private-key upload. Governance
manager labels do not confer RBAC. Previously committed bearer consent
receipts cannot authorize a new provider handoff.

The Native executor retains metadata-only UID/RV JSON Patch, final server
dry-run and full provider read-back. The canonical Released finalizer uses
the new acceptance/execution receipts, and Re-adopt requires a fresh
explicit Platform Admin handback plus original UID/RV-bound lineage.
Neither lifecycle action deletes/re-sizes Kubernetes resources, grants
automatic user privileges or silently reactivates previous generation state.
Old workflow text above is retained for audit history, not current authority.

Current normative source-of-truth documents:
`docs/architecture/kubernetes-tenant-access-governance.md` and
`docs/architecture/kubernetes-tenant-domain.md`.

**Validation remains outstanding:** Kubernetes cluster-version
SelfSubjectReview support, X.509 principal/group and optional credential-id,
scoped SelfSubjectAccessReview, provider CAS/dry-run/post-write preservation,
cross-object crash/partial-recovery, Release read models and logical capacity,
fresh Discovery/Re-adopt lineage, existing regression gates, Violet
light/dark/mobile Visual QA and security-sensitive Human Acceptance.
Provider mutation has **NOT** been executed during this GitHub work.
CI/CD, Full Admission, staging and main promotion remain HOLD.
