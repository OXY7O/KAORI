# Capsule Release — guarded handoff and recovery source boundary (#1229)

**Scope/acceptance freeze:** [Capsule Release & Re-Adopt — Minimum Secure Acceptance Baseline](kubernetes-tenant-capsule-release-readopt-gates.md) defines mandatory G0–G6 gates, exact Release/Re-Adopt exit criteria, and the outstanding Re-Adopt resourceVersion lineage defect. Follow that baseline before expanding proof machinery.

Status: **DevContainer source-review slice; provider execution NOT admitted**.
Parent #991; prerequisite source #1227 and #1228. Neither merge nor committed
successor acceptance source is actual X.509 consent or provider authorization.
Target integration: `kaori/review/staging-uat` only. No developer check,
pytest, Ruff, pyright, CI/CD, DAST, live API UAT, promotion or deployment until
a separate explicit instruction.

## Provider-declared Capsule `kaori.io/tenant` projection evidence — #1229

**Observed local read-only evidence (12 Oct 2026):** Capsule Tenant
`kaori-demo` declares
`spec.namespaceOptions.additionalMetadata.labels` =
`{cluster: kaori-local, kaori.io/tenant: kaori-demo,
pod-security.kubernetes.io/enforce: restricted}`, with
`managedMetadataOnly=false` and `quota=2`. The Namespace
`kaori-demo-dev` has the same `kaori.io/tenant` value and a matching
`capsule.clastix.io/tenant=kaori-demo` membership label. Its managedFields
reports `manager=kubectl-create` at initial creation; that record alone
cannot prove the historical actor or authorize KAORI ownership transfer.
However, the **current authoritative Capsule Tenant spec** is concrete
evidence that this particular label is a provider-declared Namespace
metadata projection.

The approved reconciliation is narrow: G0 and G2/G3 read-only
preservation may recognize **only the exact key `kaori.io/tenant`** when
the immutable Capsule Tenant spec observed for the same approved
CR UID/RV/spec SHA contains
`namespaceOptions.additionalMetadata.labels['kaori.io/tenant']` with
the precise Capsule Tenant name **and** the Namespace actually has the
same value, current Capsule membership correlation and unchanged UID/RV.
G0 then retains the independent
`external_or_unattributed/observe_only` classification. This is not the
canonical KAORI `kaori.io/tenant-id` ownership marker, is not handoff
consent, and **must not** be added to the removable KAORI transfer key
list. It is preserved by GET-only provider read-back in preview, offline
scope review and the guarded executor; spec changes fail CR hash
verification. No PATCH is sent to this Namespace.

Any other unverified `kaori.io/*` key, missing/mismatched Capsule spec
projection, changed Namespace label/UID/RV, inconsistent canonical KAORI
manager/tenant ID or conflicting owner remains **FAIL**. Authoritative
Capsule CR validation occurs before any Namespace no-op admission; a
locally supplied source label or managedFields author is insufficient.

The former #1227 G0 orphan-label blocker remains correct **when provider
spec correlation is missing**. Existing pending approval plans created
under prior G0 classification are not silently rewritten: prepare and
independently approve a fresh plan through governed workflow after the
current one expires/restarts. G1 review and Platform Admin consent do
not authorize provider mutation. A successful Namespace preservation
does not resolve separate Capsule RoleBinding controller provenance,
consent for related-resource PATCH, START ledger, or any other G2/G3
handoff constraint. Tests are authored, not executed under HOLD.

## G0/G2 marker-origin consistency: orphan `kaori.io/tenant` (#1227)

Local Capsule `kaori-demo` / Namespace `kaori-demo-dev` read-only
evidence shows `capsule.clastix.io/tenant=kaori-demo` and
`kaori.io/tenant=kaori-demo`, but **not** the current KAORI
`app.kubernetes.io/managed-by=kaori` plus
`kaori.io/tenant-id=<canonical database Tenant ID>` claim.
The unrelated `cluster`, `kubernetes.io/metadata.name`, and
`pod-security.kubernetes.io/enforce` labels do not establish KAORI
metadata handoff authority.

`kaori.io/tenant` is not among the documented provisioning and
recovery marker keys or the Capsule ownership-label keys. Its matching
*value* with the Capsule Tenant name is **not** controller-origin,
governance, or mutation consent evidence. The runtime G2 preview
properly refused the unknown `kaori.io/*` label; G0 previously marked
the same Namespace as `external_or_unattributed / observe_only`,
then let users prepare/approve a plan that could not pass preview.

G0 now marks any `kaori.io/*` label **without the independently
verifiable canonical KAORI manager/tenant-id pair** as
`marker_conflict / owner_review_required`, and records a clear
blocking reason at the earliest preflight. It preserves three distinct
cases: complete canonical KAORI pair → governed transfer candidate;
foreign/external manager without KAORI-scoped labels → read-only
preservation; unverified KAORI-scoped residue → **FAIL**. No new
allowlist, relabeling, resource deletion or replacement provider
authority was introduced.

Operator next must inspect **read-only** Capsule Tenant
`spec.namespaceOptions` (including additionalMetadata if present)
and Namespace managedFields or trusted apiserver audit/committed
provisioning history. ManagedFields alone is *not* authoritative
controller provenance. Only when the label's actual origin and
governance purpose are established may a separate reviewed,
issue-authorized reconciliation or strictly source-proven preservation
rule be considered. Do not remove `kaori.io/tenant` just to bypass G2.

Existing G1 reviewer and X.509 acceptance receipts do not confer
permission to mutate the provider. The changed G0 scope also means
the old prepared plan is not automatically renewed/approved. Tests
are source-authored but have **not** run under the standing HOLD.

## G1 accepted → G2 Capsule provider scope preview: observed Namespace boundary (#1229)

Local DevContainer: the independent second-operator review and exact
X.509 Capsule Platform Admin acceptance for 2 resources both succeeded.
The next `Preview Capsule Provider Scope` was rejected with
`Namespace handoff source ownership is ambiguous.`, **before any live
provider mutation**. The G1 recorded approval and non-mutating
successor consent do not prove provider transfer or resolve the separate
controller-generated RoleBinding origin warning.

The original Capsule Namespace preview required all observation-only
Namespaces to have **no** `app.kubernetes.io/managed-by` key; this
incorrectly rejected an otherwise unchanged Namespace owned by a
non-KAORI external manager. The surrounding scope preview also always
required one Namespace PATCH, even when the entire Namespace set was
observation-only and a governed **related** quota/limit candidate was
the legitimate server-side dry-run target.

The provider-preserving correction:
- Exact observed Namespace UID/resourceVersion, Capsule membership label
  correlation, source `managed_by` value, full label/spec/owner/finalizer
  invariants and second provider GET must still match the prepared plan.
- `observe_only/external_or_unattributed` may retain a verified non-KAORI
  `app.kubernetes.io/managed-by` marker. This is a **GET-only**
  preservation receipt, never a PATCH, implicit KAORI grant, or
  provider-owned label rewrite.
- An observed Namespace with `kaori.io/*` controls, claimed KAORI
  manager, unverified/changed source manager, or other ambiguous
  ownership remains **FAIL**, now with a more actionable explicit error.
  Do not manually strip such labels to make Release succeed.
- Namespace-only preview may contain zero Namespace dry-run PATCHes,
  but complete-scope preview must first read and validate every governed
  quota/limit/RoleBinding and require at least one real, exact
  KAORI-correlated metadata transfer candidate somewhere in the
  canonical worklist. Exact Namespace/related candidate counts must
  match observed server dry-run coverage. A zero-transfer observed-only
  scope does **not** produce an executable handoff preview, and G2/G3
  admission, START, authorization and Release remain separate.

If the same environment continues to show an unclassified KAORI control
label, obtain **read-only** Namespace label evidence and correlate it with
the existing committed KAORI controller/adoption history. This change
does not authorize relabeling or deletion of provider resources.
Regression source authored but NOT executed under the CI/CD/runtime HOLD.

## G1 live feedback — separate complete LIST evidence from stable object identity (#1228)

A `kaori-demo` independent reviewer correctly reached G1, but the exact
SHA-bound fresh preflight repeatedly rejected the prepared handoff plan
with **only two** changed categories: quota/limit/RBAC scope digest and
GlobalResourceQuota scope digest. The source cause is confirmed: each
collector SHA previously mixed object identity/policy with the
collection-wide Kubernetes **LIST resourceVersion**. This value may move
for independent collection activity while the current related object
scope and content are unchanged. Even a complete **empty**
GlobalResourceQuota collection has a moving LIST revision.

The approved two-part contract is now:

- **Completeness provenance (mandatory every read):** each typed scoped
  LIST supplies a non-empty provider `metadata.resourceVersion`; bounded
  item count, non-paginated response, exact Namespace/kind scope and every
  observed object UID/RV/policy/retained metadata are validated and
  recorded. An incomplete, unserved or forbidden LIST is **FAIL**.
- **Stable G1/G2/G3 scope fingerprint:** hash exact served API version,
  per-scope Namespace/kind/count and **every** current object UID, object
  resourceVersion, origin class, full policy and retained metadata SHA.
  Exclude *only the collection LIST resourceVersion*, not the resource's
  own `metadata.resourceVersion`. Distinguish collection revision churn
  from object drift; an object's mutation, missing/new object, changed
  policy/ownership/spec or RBAC correlation still rejects the plan.
- **Complete-scope dry-run:** two fresh, versioned full LIST preflights
  around provider server dry-run are compared after stripping only the
  collection revision fields. Exact object/owner/spec/RBAC and complete
  list scope must still match. The live executor continues to enforce
  independent X.509/SSR/SAR, per-object consent, UID/RV CAS PATCH and
  full authoritative read-back with PostgreSQL START/recovery; G1 never
  grants these authorities.

Older pending G1 plans carry the previous digest contract and **must not**
be silently rewritten or approved; original requester must use existing
governed expiry/re-prepare policy to bind fresh evidence. The change is
source-only under HOLD, with authored but unexecuted regression checks.
No provider mutation, CI/CD, G2/G3 PASS, Released or Re-Adopt is claimed.

## G0 typed Kubernetes SDK inventory dispatch correction (#1229)

A local `kaori-demo` preflight surfaced a retained blocker
`Capsule related quota/limit/RBAC authoritative inventory is incomplete.`
After the diagnostic extension, its failure stage was
`namespaced_quota_limit_rbac_inventory` with `AttributeError`.
Independent `kubectl auth can-i list` checks passed, with one
ResourceQuota, one LimitRange and two Capsule RoleBindings, and the
GlobalResourceQuota v1beta2 CRD served correctly (zero instances).

Source review confirmed a **KAORI SDK dispatch defect**: the
`capsule_handoff_related_inventory._listing` method constructed a
dictionary by eagerly dereferencing **all three** methods from a single
API object. `CoreV1Api` has quota/limit LIST but not RoleBinding LIST;
`RbacAuthorizationV1Api` has RoleBinding LIST but not quota/limit LIST.
The eager lookup raised `AttributeError` before the actual typed LIST
could execute. It now selects the method **name** first and dereferences
only that method on the already-selected Core or RBAC client.

The source regression uses separate Core-only and RBAC-only client
fixtures, matches the real Python Kubernetes SDK API surfaces, and
asserts exactly three read-only scoped LISTs and four resource records.
No provider changes or admission relaxations are introduced. This
fixes the demonstrated source defect; it **does not assert** that fresh
Capsule preflight, successor authority, mutation, G2/G3 execution,
G4 Release or G5 Re-Adopt has passed. Tests are authored but not
executed under the operator's standing CI/CD and runtime HOLD.

## G0 Capsule inventory diagnostics for local DevContainer troubleshooting (#1229)

When the full read-only Capsule Release preflight cannot complete its
ResourceQuota/LimitRange/RoleBinding inventory, cluster GlobalResourceQuota
LIST, or RBAC contract lineage inspection, the standard Release blocker
`Capsule related quota/limit/RBAC authoritative inventory is incomplete.`
**remains FAIL**. The committed `capsule_inventory_failure` receipt now
adds a bounded stage (`namespaced_quota_limit_rbac_inventory`,
`cluster_global_quota_inventory`, or `capsule_rolebinding_lineage`),
exception category, optional HTTP status, and only whitelisted code-owned
error strings. The standard Violet Release conditions UI displays this
diagnostic without exposing provider HTTP response bodies, RBAC subjects,
secret values, or raw Kubernetes exception text.

**Zero GlobalResourceQuota objects is valid** if the cluster-scoped
versioned LIST returns complete metadata/resourceVersion and an empty items
array. The object count alone is not grounds to bypass missing served API
versions, malformed/paginated responses, stale identities, or ownership
provenance. Kubernetes CLI LIST permission does not prove that KAORI's
registered provider identity, served CRD versions, full payload shape,
or RBAC lineage validator succeeded.

Source-only tests are authored, not executed under the standing HOLD. This
diagnostic change does not modify provider resources, waive a blocker,
admit G1/G2/G3, execute handoff, mark Released or authorize automatic retry.

## G3 foreign Namespace full-preservation correction (#1229)

Complete-scope Capsule executor read-back now rejects **any** drift in a
foreign/preserved Namespace: provider UID/resourceVersion, labels, spec,
annotations, ownerReferences, finalizers and other retained metadata.
`_verify_preserved_foreign_namespace` reuses the existing strict
`capsule_preservation_digest` rather than accepting identity and labels
alone. The corresponding regression covers all these mutation categories.
This is a preservation check, not new permission to transfer foreign
resources.


## Capsule single-attempt handoff executor — #1229 integration

The actual Capsule wizard now has a second, explicit **Execute Guarded Capsule
Handoff** confirmation after a successful, fresh whole-scope server
`dryRun=All` preview. The committed preview contains the exact SHA-bound
original worklist and every proposed transfer object identity (kind, Namespace,
name, UID, resourceVersion). On invocation the accepting human Platform Admin
must retain the exact X.509 Kubernetes identity, the approved plan,
independent second-operator acknowledgement, zero dependencies and the
current complete provider scope. Any stale or changed resource, unknown
provenance, foreign owner or unverified **KAORI-correlated RoleBinding**
origin blocks execution. Provider/foreign RoleBindings are preserved, never
changed by this path.

`capsule_handoff_executor.py` reuses the existing canonical metadata-only
patch builders and typed server-side dry-run APIs; it **does not enable**
the earlier separately staged `capsule_handoff_live_patch.py` adapter. One
specific workflow acquires a locked Tenant row and PostgreSQL immutable
attempt ledger, checks operational write-once trigger/role/WAL safeguards
and commits exactly one START in its own database transaction **before the
first provider live PATCH**. It verifies the Capsule CR, Namespace and
complete quota/limit/RBAC/GlobalResourceQuota provider scope, performing
only UID/RV/full-label compare-and-swap for exact consented KAORI Namespace,
ResourceQuota and LimitRange markers. Quota limits, subjects/roleRef, Capsule
v1beta2 CR spec, ownership references, foreign labels and workloads are
untouched. All provider-owned/foreign resources are read and preserved.

If any provider write returns an error/timeout, the workflow stops; it does
not skip to another PATCH or retry. START stays committed even on process
death, preventing a second execution request. The terminal append-only
ledger event is `partial` or `readback_candidate` after an exhaustive
fresh provider read-back. A full-scope AuditEvent links the START/terminal
read-back hashes and a count of all preserved and transferred resource
identities. **This is G3 observation evidence, never itself a G4 Released
transition.** If terminal/SQL commit acknowledgement is missing or unknown,
manual recovery remains mandatory.

G2/G3 **still require authorized** migration and DB role/guard verification,
source validation tests, live Kubernetes dry-run/PATCH, recovery/security
UAT, and human acceptance before a PASS can be claimed. The current
RoleBinding provenance limitation must be investigated before handoff of
KAORI-owned RoleBindings; an operator cannot paper over it with a source
flag. All earlier audit/proof collectors remain gated and are not silently
enabled by this minimal path. G4 and G5 remain independently verified
steps in the approved workflow.

## Disabled live metadata PATCH adapter — #1229 executor source boundary

`app/kubernetes/tenant/capsule_handoff_live_patch.py` stages the actual
Kubernetes API dispatch needed by the G2 executor, **without exposing it as a
live KAORI capability**. Its nonconfigurable
`_CAPSULE_LIVE_PATCH_ENABLED = False` prevents all Kubernetes operations on
entry. No route, scheduler, background job or runtime service imports this
adapter.

Once independently authorized in a separate implementation/review step,
the intended per-object operation is a strict
`read -> server dryRun=All -> validate preview -> re-read unchanged ->
JSON Patch once -> re-read -> classify` sequence. It reuses the existing
Capsule Namespace and ResourceQuota/LimitRange/RoleBinding metadata-only
builders/read-back classifiers and their UID/resourceVersion/full-label
JSON Patch tests. The adapter never sends a spec-changing, create, delete,
replace or workload operation. Its result remains explicitly
`provider_handoff_verified=false` and `release_authorized=false`
even for one apparently transferred object. Unknown provider PATCH outcome
raises immediately with **no retry**; the full attempt must go to an
independent operator recovery path.

This staged primitive is deliberately **not** a complete safe executor.
Before enabling or wiring it, #1229 must prove installed PostgreSQL
write-once START and durable commit, current independent per-resource
successor consent and authentic controller-origin evidence, exact operator
and X.509/SAR reauthorization, whole-scope worklist identity, a recorded
outcome for success/partial/unknown, and authoritative **entire-scope**
post-operation read-back. The current admission assessor and START writer
continue to deny that authority. No user-confirmation checkbox, source
preview receipt, fabricated `start_committed` field, Python parameter, or
feature flag can bypass them. #1230 finalization remains blocked.

Author-only tests cover denied calls, typed `dry_run='All'` versus
once-only live PATCH shape, source drift rejection, non-Release receipts,
and a simulated unknown outcome. **Tests, migration, Kubernetes provider
operations, CI/CD, Full Admission and UAT have not been executed.**

## Complete-scope Capsule server preview — #1229 source extension

The existing authenticated **Preview Capsule provider handoff** Step 3
button now dispatches source-verified server-side `dryRun=All` for
KAORI-correlated Namespace, ResourceQuota, LimitRange and RoleBinding
**metadata-only candidates**, plus explicit typed GET of every observed
related resource. Its newly admitted read-only actor authority rechecks
Kubernetes exact-object GET/PATCH SAR for each related candidate and
uses the existing strict patch builders, policy-preservation checks,
resource UID/RV, current related-resource fingerprints and subsequent
provider GETs. A second entire committed Capsule Release preflight
confirms identical CR/Namespace/GlobalResourceQuota/RBAC/inventory scope
and live source revisions after *every* dry-run.

G1 approval and preview may now tolerate *only* source-correlated
`Capsule Kind/namespace/name retains KAORI provider controls requiring
separately admitted handoff.` warnings if a digest-checked canonical
worklist enumerates those same related objects and has no ambiguous
provider origin, foreign claims, unknown selectors or other blockers.
These warnings are **handoff obligations**, not authorization to PATCH:
the resource transfer label key set is proposed from current provider
metadata solely for preview and is not recorded as trusted resource
consent. Denied RBAC, changed UID/RV, new/deleted objects, ambiguous
RoleBindings, partial LIST or a changed GlobalResourceQuota fingerprint
still aborts preview and is never treated as success.

The existing `kubernetes_tenant_release_capsule_namespace_preview`
AuditEvent target now records
`status=complete_scope_server_dry_run_only`, scoped preview and
preservation counts, `related_mutation_consent_verified=false`,
`provider_execution_admitted=false`, and
`provider_handoff_verified=false`. Normal Registry UI GET reads that
committed receipt without making any live Kubernetes call.
**Do not promote this receipt into G2/G3 PASS**: independent
resource-specific consent/origin evidence, durable START, live
conditional PATCH, authoritative complete post-mutation read-back and
manual partial recovery remain outstanding. No tests, CI/CD or actual
provider operations were executed for this source slice.

## Capsule Platform Admin acceptance error specificity (#1228)

`Current independently approved exact Capsule Release plan is required.`
previously conflated an invalid plan hash/approval, an original requester
trying to act as the separate Platform Admin, and a valid but expired
900-second plan/review. The service now validates the original immutable
plan and reviewer contract **first**, then explicitly rejects (1) the
same original requester and (2) expired plan or reviewer evidence with
distinct safe UI errors. An unrelated or forged plan SHA remains a generic
invalid-exact-plan rejection. No authorization bypass, provider resource
mutation or change to the two-operator separation requirement is introduced.
Regression source authored only; CI/CD and UAT remain under HOLD.

## Expired acknowledged Capsule G1 review — governed zero-attempt restart (#1228)

Local DevContainer screenshots show that `kaori-demo` still displayed
`Independent Review Recorded / Transfer Pending` for an old plan,
while Capsule Platform Admin consent returned
`Current independently approved exact Capsule Release plan is required.`.
The backend correctly requires **both** original `requested_at` and
`approved_at` to remain within the existing 900-second window.
The Registry previously projected `acknowledged` indefinitely, because
that label describes historical review, not **current acceptance authority**.
Unlike Native, Capsule had no source-wired requester restart path for
an *expired acknowledged* plan; it could become operationally stuck even
without any provider PATCH.

New `capsule_handoff_restart.py` is a strictly **no-provider-mutation**
restart. It requires the original requester, exact immutable plan hash
and independent reviewer receipt, expired trustworthy timestamps,
Ready/adopted/Capsule authority and generation, a **fresh complete G0**
provider preflight and normal G1 blocker policy. It demands the installed
PostgreSQL immutable Capsule START ledger (full trigger, restricted DB
role and WAL guards) and **no START rows for this Tenant**; all legacy
execution, actual Release and handback AuditEvent targets must also be
empty. The ledger/execution checks are repeated after taking the Tenant
row lock. Missing schema, privileged/mutable/unreadable ledger, any
partial/unknown START, or changed provider object identity causes
**FAIL/recovery**, never fresh consent or retry.

On positive zero-attempt evidence only, restart records a distinct
fresh SHA with current object-scoped fingerprint and preflight, retaining
the successor and change record but **never** carrying old independent
approval, Platform Admin consent, preview or execution authority to the
new plan. A separate approver and X.509 Platform Admin must consent
again. No quota/limit/RoleBinding/Namespace PATCH is executed.

The existing Violet/HTMX Tenant Release UI now distinguishes
`Capsule Approval Expired` from historical review, hides the stale
acceptance form, and provides a requester-only explicit
`Restart Expired Capsule Plan` action. A non-requester is directed back
to the original requester. The service is still authoritative and rejects
unsuitable attempts regardless of UI state or forged form values.

This change is source-only and **not runtime PASS**. Tests/CI/CD and
PostgreSQL guard installation are held. Operators must first refresh
the `External Capsule Access Inspection` if its evidence has expired;
otherwise G0 will correctly refuse the new plan. See G0–G6 gate baseline
for independent G2 provider dry-run, START and G4/G5 acceptance.

## G1 independent-review drift diagnostics — #1228 DevContainer feedback

The local `kaori-demo` Release wizard successfully prepared the SHA-bound
plan with a new requester, but the distinct authorized reviewer received
`Provider or governance evidence changed; prepare a new plan.` at G1
acknowledgment. No Kubernetes mutation occurred. G1 correctly re-runs a
read-only preflight and **rejects** a different Capsule CR/Namespace UID,
resourceVersion, canonical spec, namespaced related inventory,
GlobalResourceQuota or RBAC-lineage digest. The original message
inadequately distinguished the source of drift.

G1 now derives **bounded category-only** diagnostics from the already
committed plan and fresh preflight: Tenant/Cluster identity, provider object
membership and UID, object resourceVersion, handoff/ownership class,
Capsule spec, namespaced quota/limit/RBAC scope, GlobalResourceQuota scope
and RoleBinding lineage. This is a presentation/error-message correction
only; private RoleBinding subjects, provider payloads, hashes and
credentials are never included in the UI or error. It neither treats an
advanced Kubernetes LIST resourceVersion as harmless nor weakens any
exact scope, actor, SHA, time-window, dependency or permission admission.
A changed LIST digest may reflect a new snapshot revision **or** different
object identities/policy; the diagnostic must never assert which without
independent evidence.

Regression cases for CR UID/RV, spec digest, related inventory SHA,
shared quota SHA, RBAC lineage and ownership changes are source-authored
but not run under the existing gate HOLD. If the latest pending plan is
stale, the original requester must follow the existing governed
expiration/re-preparation flow; a different reviewer cannot manufacture
a matching SHA or bypass a fresh preflight.

## G1 consent vs G2/G3 execution authority

A committed Capsule preflight may contain the **exact** source-known warning
`Capsule controller-generated RoleBinding origins and provider handoff remain
unverified; executor is blocked.`. This warning is a mandatory **G2/G3
execution** blocker, but it is not evidence that the independently reviewed
human is forbidden from *recording G1 consent to a plan*. The shared handoff
approval checker now permits this single, exact warning only when the Capsule
provider is selected, dependency counts are all zero, provider UID/RV and
SHA-bound scope are complete, and the existing related-resource, global quota
and RBAC inventories have matching digests and zero independently recorded
inventory blockers. All other unknown, drift, identity, permission and
ownership blockers continue to prohibit approval.

G1 acknowledgement, subsequent X.509 successor acceptance, and the new
Namespace `dryRun=All` control remain **non-executable**: the Capsule G2/G3
admission evaluator still carries its unconditional controller-origin and
per-resource successor-authorization blockers. Nothing in this change permits
a live PATCH, a START writer, Release or Re-Adopt. The operator must still
satisfy the separate safety, handoff and provider read-back requirements
before progressing to #1230/#1231.

## First wired Capsule provider preview — #1229 functional slice

The initial source slice of the existing four-step Tenant Release wizard offered **Preview Capsule Namespace**
only to the X.509 Platform Admin whose independent Capsule successor consent
was recorded for the exact current plan. The authenticated POST requires
`tenant.manage`, `integrations.manage`, `clusters.manage`, CSRF and explicit
checkbox confirmation. The service rechecks the committed plan SHA, independent
approval, accepting actor, Ready adopted Capsule authority, zero governance
dependencies, refreshed live Capsule CR/Namespace + related-resource fingerprint,
and newly authenticated SSR/SAR with matching X.509 principal and credential ID.

It executes real `dryRun=All` on **Namespace metadata-only JSON Patches** using
the existing strict UID/RV and post-preview read-back helpers; no live
provider PATCH, Capsule CR/spec modification or finalizer is introduced.
It records only an `namespace_server_dry_run_only` non-secret AuditEvent:
`provider_execution_admitted=false`, `provider_handoff_verified=false`,
`release_authorized=false`. Quota/LimitRange/RoleBinding server dry-run
coverage and resource-specific controller-origin/consent proof remain
**unverified**. A passed Namespace preview is **not** G2/G3 PASS and does not
enable Capsule Release. If preflight inventories contain blockers, it fails
closed with an actionable warning; never bypass them to make a demo pass.

The next implementation must bind related-resource previews and a durable
START-fenced metadata-only executor to definitive whole-scope provider
read-back, then wire #1230 transactional Released finalization and #1231
Re-Adopt. The existing `#991` G0–G6 baseline remains authoritative.
No local tests, provider API operation, migration, CI/CD or UAT has been run
for this source-only slice. Review only on `kaori/review/staging-uat`.

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
only (Native evidence remains unchanged). The deterministic SHA-256 of exact scoped objects (including their own
UID/resourceVersion and policy/metadata) and complete Namespace/kind/count
coverage is bound into the existing Capsule Tenant handoff component as
`capsule_related_resources_sha256`. Collection LIST revisions remain
recorded **as mandatory completeness evidence**, but are not themselves
part of the cross-request stability digest. An incomplete read never emits
a trusted resource digest.

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
`v1beta2` API (with a `v1beta1` fallback only after 404). The observer records and validates the full cluster LIST resourceVersion
for authoritative completeness, and SHA-binds exact CR UID/resourceVersion,
canonical spec/metadata and served API version. The collection-wide LIST
revision is not included in the cross-request scope digest. It never clones or
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

## Admission evidence and recovery worklist — source-only follow-up

`capsule_handoff_admission.py` is a **pure, non-executable** evaluator of
the current Capsule Release plan hash, exact provider fingerprint,
independent approval, accepted X.509 successor, matching authenticated
SelfSubjectReview/SAR evidence, actor identity, zero active dependency counts,
fresh authoritative preflight and scoped CR/Namespace/Quota/RBAC evidence.
A record must be independently reloaded and reverified by a future guarded
service; a caller-supplied mapping is never accepted as operational proof.

The evaluator recomputes the namespaced ResourceQuota/LimitRange/RoleBinding
inventory digest and checks the committed Capsule CR component digests and
provider LIST coverage. It also binds the authenticated provider credential,
principal groups and exact SAR scope to the independently accepted actor.
A stale plan, duplicate/missing list, changed object, expired consent,
new RBAC subject, unmatched X.509 identity, missing preflight or forged
controller-origin boolean produces blocking reason codes **without sensitive
principal or credential values**.

`capsule_handoff_worklist.py` derives a deterministic **operator review
worklist** for Capsule Tenant CR preservation, Namespace ownership markers,
namespaced quota/limit/RBAC objects and GlobalResourceQuota. Every object is
classified as provider-preserved, candidate metadata review or operator
investigation. It recomputes source LIST + global quota digests instead of
trusting a hash field supplied by a caller. No raw provider spec, RBAC
subjects, live patch bodies or credentials are included. The SHA-256 worklist
fingerprint, counts and unresolved reasons are part of the pure assessment,
not a persisted provider execution receipt.

**Deliberate hard stop:** `rbac_controller_origin_unverified` and
`resource_specific_handoff_worklist_not_admitted` are mandatory blockers.
`dry_run_admitted=false`, `provider_execution_admitted=false`,
`auto_retry_authorized=false` and `release_authorized=false` are invariant,
including when all supplied preconditions match. No route, scheduler,
DB execution audit, live dry-run, PATCH, retry or finalizer was enabled.
Future actual controller-provenance proof must be a separately security-reviewed
provider authority contract, not a managedFields claim, label, or matching hash.

## Append-only attempt and no-retry recovery state — source-only contract

`capsule_handoff_attempt_state.py` models a **single attempt**, but does not
issue a Kubernetes request, create AuditEvents, or provide an executor.
It validates a narrow v1 event envelope bound to the exact approved plan
SHA-256, generation/cluster, provider fingerprint, deterministic source worklist
SHA-256, one canonical attempt UUID, accepted actor ID, strictly increasing
sequence/timestamps, and the prior event's SHA-256. Receipts contain only
counts, an opaque optional read-back digest, event type, and invariant
`provider_handoff_verified=false`/`release_authorized=false`. Unknown
fields (including accidental credentials or provider objects) are rejected.

| Event | Permitted follow-up | Source-only projection |
| --- | --- | --- |
| No event | None automatically | `no_attempt_observed_not_authorized` |
| `started` | `partial` or `readback_candidate` | `started_outcome_unknown_recovery_required` |
| `partial` | Independent `recovery_reviewed` | `partial_handoff_recovery_required` |
| `readback_candidate` | Independent `recovery_reviewed` | `readback_claim_requires_independent_provider_verification` |
| `recovery_reviewed` | No new start/retry | `manual_review_recorded_no_retry_granted` |

The source model strictly forbids a `provider_handoff_verified` event and
never converts an asserted all-transferred count into Released. A `started`
record with no final provider acknowledgement is **unknown outcome**, not
proof of no write. A manually reviewed partial/read-back claim is still
non-retryable without a new externally governed plan and explicit recovery
authorization. It requires a different human reviewer identity from the
attempt actor, but cannot verify that person's entitlement by itself.

Event SHA chaining is **not** tamper-proof evidence until anchored in a
trusted, append-only AuditEvent stream. The future operational executor
must independently enforce row locks, once-only attempt identity,
committed `started` evidence *before* first PATCH, strong provider read-back
and definitive partial/unknown receipts even on HTTP timeout, interrupted
process or database-write failure. It must check current actor, plan,
successor, Kubernetes TLS, X.509 SSR/SAR and resource origins immediately
before every permitted mutation. This projection does none of those
operations, has no route and never provides an execution capability.

## AuditEvent envelopes and candidate provider read-back — source-only boundary

`capsule_handoff_audit_envelope.py` validates supplied **chronological**
`AuditEvent` rows (not a database query or writer). Each record must have
the dedicated Capsule execution target, correct Tenant, strictly increasing
row ID and timestamp, matching actor, exact event action/type, and validated
`capsule-handoff-attempt/v1` checksum chain. An incomplete, duplicated,
malformed, reordered or wrongly attributed envelope fails closed.
These source checks **do not** establish database append-only guarantees,
audit-stream completeness, SQL durability, or authentic Kubernetes execution:
those require independently enforced operational controls.

`capsule_handoff_readback_evidence.py` compares separately acquired
Capsule Tenant CR, bounded Namespace baselines, all namespaced
ResourceQuota/LimitRange/RoleBinding LISTs and cluster-scoped
GlobalResourceQuota records against the exact original approved source.
It recomputes provider LIST digests and enforces each kind/Namespace's
unique list scope, resource counts, identity, UID and resourceVersion.
It checks provider spec, preserved ownership/finalizer/annotation digests
for KAORI Namespace handoff baselines. Any missing Namespace/baseline/LIST,
wrong kind, stale digest, changed global quota, provider CR/spec drift
or foreign constraint change is rejected or flagged for recovery.

The read-back candidate counts **all** KAORI transfer worklist objects,
including residual ResourceQuota/LimitRange/RoleBinding ownership, never
only Namespaces. Candidate metadata transfer is classified separately
from untouched provider-owned resources. An unchanged KAORI-related control
is still only *pending*; a changed one without separately admitted
resource-specific handoff remains unverified.

`inspect_capsule_audit_readback_link` correlates the recorded
`readback_candidate` SHA, worklist, plan and every transfer counter with
this observation. An exact match produces
`readback_claim_correlated_unverified`, not provider verification.
A partial/unknown operation, a matching checksum, or a manually reviewed
claim **never** authorizes retry or Released.

**Hard trust boundary:** no GitHub source merge, test fixture, audit-event
mapping or caller-supplied Kubernetes response is authenticated evidence of
a live handoff. A future guarded, explicitly consented executor must use
fresh TLS-validated Kubernetes clients, exact SAR permissions, independent
read-back after each permitted mutation, trustworthy append-only persistence,
and human recovery for incomplete operations. This slice introduces no
endpoint, scheduler, persistence, dry-run invocation or live PATCH; all
`provider_handoff_verified`, `readback_authoritative_verified`,
`auto_retry_authorized`, and `release_authorized` values remain false.

## Committed AuditEvent scan and persistence/recovery boundary — source only

`capsule_handoff_persistence_review.py` adds a read-only access path to
the existing SQL `audit_events` table. It fetches **all Capsule execution
records for one Tenant**, ascending by AuditEvent ID, with a fixed
`max_attempt_events + 1` bound to reject overlong attempts instead of silently trimming records.
The inspected records must match the canonical actor, event action, target,
attempt UUID, plan SHA, worklist and hash chain. Rows for prior plans are
**not** filtered away just to make a newer attempt appear empty. A START
without outcome is a recovery-required operation, not permission to retry.

The same module also reviews *proposed* next event envelopes against
committed history without executing an INSERT. `append_authorized=false`
and `trusted_audit_persistence_verified=false` are permanent outputs of
this source-only helper; it does not run SQL writes, lock rows, or grant a
Kubernetes operation. A valid event checksum establishes data consistency
within the supplied snapshot, **not** database immutability, durable
commit, independent human consent, or chronological stream completeness.

`capsule_handoff_persisted_recovery.py` correlates that read-only
history with an optional `readback_candidate` receipt and returns a
non-executable recovery docket. A previously started operation without a
definitive outcome is quarantined. A partial operation requires a fresh,
independent human recovery decision. An exact recorded read-back SHA is
still merely `readback_correlated_but_unverified`; it is not fresh
authenticated Kubernetes read-back and cannot authorize Released.

### Required storage/executor remediation before any live handoff

The shared `AuditEvent` model has an ordinary mutable JSON column and no
Capsule-specific database-enforced insert-only property or uniqueness
constraint. This must be treated as an **open blocking design gap**, not a
PASS inferred from source-only row validation.

A future independently reviewed implementation needs:

- A database-enforced **write-once, non-deletable** Capsule execution ledger
  or a comparably protected append-only event store; immutable attempt
  identity, unique `(tenant_id, plan_sha, attempt_id, sequence)`, and
  explicit unauthorized update/delete rejection.
- A Tenant-scoped transactional lock/fencing strategy, historical-attempt
  scan and once-only START commitment **durably acknowledged before** any
  Kubernetes write. A failed or uncertain commit must stop execution.
- A new freshness/authority decision just before each operation, including
  exact actor, independent plan approval, accepted successor, authenticated
  Kubernetes TLS/X.509 SelfSubjectReview/SAR, source fingerprints,
  provider-owned constraints and explicit resource-specific transfer scope.
- Per-resource conditional metadata-only patch, immediate authoritative
  provider read-back and separately committed partial/verified evidence.
  Timeouts, database errors, process crashes, conflicting controller writes,
  untracked history or uncertain outcomes remain human-recovery blockers;
  never retry automatically.
- Restoration/backup and retention protections for the ledger itself, plus
  testable audit guarantees across the actual database engine and deployment.
  SQL-model-level rules alone are insufficient to prove disaster durability.

None of these missing storage and live-operation guarantees is enabled by
this slice; no DB migration or AuditEvent writer is introduced. #1229
remains OPEN and #1230/#1231 blocked. All test, CI/CD and real provider
operations continue to be held pending explicit authorization.

## Capsule write-once event ledger — migration source only

`app/models/capsule_handoff_ledger.py` and
`migrations/versions/20261011_capsule_handoff_write_once_ledger.py`
define a **dedicated** `capsule_handoff_ledger_events` relation, separate
from the generic mutable `audit_events` table. The new model records only
the canonical attempt envelope, exact Tenant/cluster/generation and
plan/worklist SHA, indexed actor/sequence/event hash, and safe event JSON.
No Kubernetes subject, provider credential or raw resource spec belongs in
the ledger.

The migration is based on `20261009_tenant_released`. It is **authored,
not applied**. It supports PostgreSQL and SQLite explicitly, and refuses
other SQL dialects until their immutability controls are reviewed.
Both dialects enforce bounded event progression (START, one outcome,
optional independent recovery review) and unique Tenant sequence/digest.
Insert guards prevent missing predecessors, parallel/new attempts,
actor mismatch, different provider scope, and event chronology drift.
PostgreSQL uses a Tenant row lock to serialize inserts, and guards
UPDATE, DELETE **and TRUNCATE**. SQLite uses transaction-serialized
predecessor checks and UPDATE/DELETE triggers. Downgrade is forbidden
when events exist.

**Conservative irreversible fence:** only one attempt history is permitted
per Tenant. A future sanctioned restart cannot delete ledger evidence,
reuse attempt sequence or silently reset history. It requires a separately
approved recovery protocol and additive schema extension, not a bypass.

`capsule_handoff_ledger_review.py` provides a bounded read-only query and
compares each persisted indexed column with the canonical event payload
and its original checksum/state chain. It also detects missing START,
duplicate sequence, out-of-order records and changed plan/worklist.
It **never** calls INSERT, UPDATE, DELETE, SQL commit or any Kubernetes API.

### Admission still blocked

A source migration is not proof of installed database triggers, correct SQL
role privileges, WAL/fsync settings, backups or tamper resistance against
database administrators. The target database engine has not been verified
by an executed migration test. A future accepted execution service must
prove the write-once schema installed on the actual engine, restrict DB
role privileges, and ensure atomic persisted START acknowledgement plus
fencing and fresh Kubernetes authority before the first provider mutation.

The new ledger is currently **not used as an execution writer**. Its reader
reports `db_write_once_triggers_verified=false`,
`transactional_start_commit_verified=false`,
`append_authorized=false`, `provider_handoff_verified=false` and
`release_authorized=false`. Generic `AuditEvent` reader remains
observation-only; no legacy Native implementation is changed. The
next work item remains an explicitly reviewed **transactional writer and
live provider executor**, with authoritative Capsule controller lineage,
individual resource handoff and independent human consent, not an
automatic promotion of this source merge. All gates remain HOLD.

## Transactional START writer — source-staged, permanently disabled under HOLD

`capsule_handoff_start_writer.py` implements the next review slice:
`build_capsule_start_candidate` is a **pure** event builder which
recomputes the canonical plan hash and component fingerprint, the exact
Namespace/quota/RBAC worklist SHA, and the original bounded transfer count.
The event contains an attempt UUID, accepted actor ID, canonical START time,
zero observations, zero provider writes, no credentials or raw Kubernetes
policy and a chained SHA-256 digest. It must pass the existing attempt
state projection before a future writer can consume it.

`commit_capsule_start_staged` is intentionally **not registered or callable
for production handoff**. A source constant
`_CAPSULE_START_WRITER_ENABLED = False` rejects every call **before** opening
a database session, querying actor credentials or writing an event. No
environment flag, request body or user confirmation can change this.
Even a separate code modification removing that source gate would still
encounter the existing immutable Capsule admission decision:
`provider_execution_admitted=false` and `dry_run_admitted=false`
until controller provenance and resource-specific metadata authority are
independently implemented and reviewed.

The staged SQL path is for architectural review only. It specifies an
isolated PostgreSQL transaction, Tenant `SELECT ... FOR UPDATE`, current
adopted/Ready Capsule lifecycle check, full legacy-attempt and immutable
ledger scan, reloading of current committed plan/approval/successor consent
under the Tenant lock, and a second check of exact actor and provider scope.
It also requires **separate explicit operator confirmation**, not just an
accepted successor receipt. Only after future authorization could an
INSERT of the canonical START envelope happen; SQL constraint validation
(`flush`) alone is **not** a committed barrier. The transaction must
commit before a separate ledger read-back; no Kubernetes operation belongs
inside this writer, and its return value must never authorize provider
PATCH, retry or Released.

Before a hypothetical START INSERT, PostgreSQL inspection requires all
four enabled database ledger triggers (insert guard and update/delete/
truncate deny), normal replication role, `fsync=on`, synchronous commit,
and a dedicated **INSERT-only** (for mutations) application role which is
neither superuser nor table owner/owner-role member and cannot UPDATE,
DELETE or TRUNCATE the ledger. These checks are defensive source gates,
**not** proof of backup durability, immutable DBA-level history, approved
migration status or real provider authority. SQLite schema remains
inspectable and reviewable but is **not admitted as this distributed
transactional writer backend**.

### Required before operator authorization

1. Obtain explicit approval to execute the schema migration and database
   verification in the intended DevContainer/UAT environment; check
   PostgreSQL trigger behavior, concurrent START fencing, safe downgrade
   refusal, privilege isolation, WAL durability and backup/recovery.
2. Independently validate Capsule controller-generated RoleBinding origins,
   the entire affected resource set, per-resource transfer consent, fresh
   TLS X.509 SelfSubjectReview/SAR and guarded dryRun=All.
3. Security-review a separate source change to activate only a fully
   admitted START transaction, then verify durable commit before **any**
   eligible Kubernetes PATCH. Validate partial/timeouts/crashes and an
   authoritative post-write provider read-back with no automatic retry.
4. Keep #1229 OPEN, #1230/#1231 BLOCKED, and all CI/CD, tests, migration,
   provider operations and Release actions HOLD until individually authorized.

## Controller provenance and exact per-resource admission matrix — source only

`capsule_handoff_resource_admission.py` now produces an exact-scope,
deterministically SHA-bound **per-object** investigation matrix for the
Capsule Tenant CR, every governed Namespace, each namespaced
ResourceQuota/LimitRange/RoleBinding and the complete cluster-scoped
GlobalResourceQuota LIST. This matrix is derived only from the approved
plan fingerprint, resource UID/resourceVersion, policy/metadata digests,
per-kind LIST counts, quota scope SHA and Capsule RBAC intent/effective
lineage. Every object has its own decision, explicit blockers and
`controller_origin_attested=false`,
`independent_resource_consent_verified=false`,
`metadata_only_handoff_admitted=false`. A correlation of KAORI labels
is **not** evidence of authenticated controller causality.

### Source classification boundaries

| Resource | Source correlation | Remaining proof / permitted future behavior |
| --- | --- | --- |
| CapsuleTenant CR | UID/RV and canonical entire-spec SHA | Capsule remains authoritative; never patch spec/owners/finalizers |
| Namespace | Exact Capsule membership, KAORI Tenant ownership and UID/RV | Only precise KAORI metadata could be a candidate; foreign/unknown origin is investigation, not a transfer |
| ResourceQuota | Exact KAORI origin markers, namespaced UID/RV, policy and metadata digests | Verify authenticated creating controller and allocation policy preservation; quota hard/used/spec never rewritten |
| LimitRange | Same exact origin, scope, policy and metadata digests | Verify controller lineage and preservation of all default/min/max limits; no policy rewrite |
| RoleBinding | Same-Tenant Capsule rule intent vs effective grant/roleRef/subjects SHA and UID/RV | Verify authenticated controller and exact grant ownership; no foreign subject, roleRef or RBAC mutation |
| GlobalResourceQuota | Entire bounded cluster LIST, selectors and policy SHA | Always preserve; unresolved selectors and KAORI markers require manual investigation |

**Fixes:** Capsule RBAC intent with a KAORI label for a different
`kaori.io/tenant-id`, partial manager/grant labels or unknown KAORI
keys no longer correlates to the current Tenant. An effective
`ambiguous_kaori` RoleBinding cannot satisfy the intended grant.
KAORI-labeled quota/limit/RBAC with a foreign ownerReference,
mismatched Capsule Tenant label or mismatched Capsule owner UID now
classifies as **ambiguous origin** rather than `kaori_correlated`.
Resource LIST snapshots must match **each** kind/Namespace resource
count even if an attacker recomputes a top-level digest. A Namespace
with `external_or_unattributed` ownership is never a transfer candidate.

`capsule_handoff_controller_audit_claims.py` provides a strict
normalization/correlation contract for a future *trusted Kubernetes
apiserver audit collector*. A bounded claim must match exact target
cluster/Tenant/kind/Namespace/name/UID/resourceVersion,
policy/metadata digests, unique audit ID, complete response stage and
successful API response. It carries only a SHA of controller principal
identity; no raw RBAC subjects, credentials or provider payloads are
persisted. Any foreign, duplicate, stale or unexpected field fails
closed. Even perfect claim correlation **does not** authenticate
the apiserver audit source, controller ServiceAccount, operation
causality or consent: `audit_source_authenticated=false`,
`controller_origin_attested=false`, and
`resource_specific_handoff_admitted=false` remain fixed.

The existing `assess_capsule_handoff_admission` is integrated with
the new per-object review digest and adds explicit blockers when
evidence is missing or candidate origins/consent are unverified.
Provider dry-run, PATCH, retry, Release and controller-origin
verification are **still unadmitted**. No new endpoint, provider
API call, live patch, audit writer, migration execution or lifecycle
transition is introduced here.

**Future admission prerequisites:** obtain trustworthy,
TLS-authenticated apiserver audit collection with independently
verified controller principal lineage (not managedFields or labels),
prove all source/current UID/RV and exact per-resource metadata-only
authority with independent successor consent, re-check actor-bound
X.509 SSR/SAR and provider read-back, and perform explicitly authorized
dry-run/UAT before considering any executor activation. #1229 remains
OPEN, #1230/#1231 BLOCKED. All tests, CI/CD and provider gates HOLD.

## Capsule controller collector receipt + per-resource successor consent (source only)

**Trust is split deliberately into three independent questions:** (1)
whether the normalized controller audit **claim** correlates to the
current resource UID/RV and original policy/metadata digests, (2)
whether the **collection receipt** originated from a pinned backend
collector key and covers the same exact plan/worklist/resource review,
and (3) whether independent humans have explicitly reviewed every
KAORI metadata-only transfer candidate. None of these alone proves
the Kubernetes apiserver generated an authentic, complete audit trail,
that the controller caused an event, or that provider mutation is safe.

`capsule_handoff_collector_receipt.py` supplies a source-only
HMAC-SHA256 authenticity check for a bounded collector receipt. The
caller must inject a 32+ byte key from a **backend-owned, independently
governed trust store** (never a request, user-supplied evidence,
metadata label or GitHub source constant). An exact collector ID and
key ID, canonical batch UUID, recent timezone-aware timestamp,
tenant/cluster/plan/worklist/resource SHA and **all normalized claims**
are MAC-bound; unknown fields, key substitution, tampering, missing
keys, stale data and a different plan are rejected. **HMAC validates
the receipt only**, not apiserver integrity or controller ServiceAccount
causality. Because a trusted collection channel, anti-replay DB
constraints and operationally pinned key registry are not yet
implemented, `collector_key_source_independently_attested=false`,
`audit_batch_replay_prevention_verified=false` and
`apiserver_audit_integrity_verified=false` stay fixed.

`capsule_handoff_resource_consent.py` defines the exact
`capsule-resource-successor-consent/v1` proposal. It matches the
current committed plan, SHA-bound per-resource report, original
worklist, distinct requester/reviewer/successor IDs, current approval
and plan-level Capsule acceptance. Its `transfer_targets` must
cover **every** KAORI-labeled Namespace/ResourceQuota/LimitRange/
RoleBinding candidate, exactly once with unchanged UID/RV,
policy/metadata SHA and an explicit `proposed_metadata_labels_only`
decision. It refuses Capsule Tenant CR, GlobalResourceQuota, foreign
objects, incomplete scope, stale acceptance, duplicate targets,
provider spec, RoleBinding subject/roleRef changes, unknown
annotations and label keys outside the per-kind KAORI allowlist.
Maximum candidate coverage is 30 Namespaces plus 300 related
resources (330); no candidate may be silently omitted. A proposed
manifest is **not** an independently authenticated, durable consent
record and cannot grant operational authority. Namespace metadata
baseline is not yet fully available and must still be obtained
before any eventual provider write.

`capsule_handoff_origin_consent_docket.py` composes the three
source-only checks, enforcing exact audit claim coverage for every
transfer candidate, valid collector MAC, identical SHA-bound scope
and complete successor consent. Its only result is
`collector_receipt_and_resource_consent_correlated_unadmitted`.
It never returns an executable resource body, patch, token or
permission. `collector_mac_verified=true` means a cryptographic
MAC comparison passed **under the supplied backend key**; it is NOT
the same thing as `controller_origin_attested`, current provider
authority, verified resource consent or approval to execute.
`dry_run_admitted=false`,
`provider_execution_admitted=false`,
`auto_retry_authorized=false`, and
`release_authorized=false` remain fixed.

**Required implementation before a real trust promotion:** review and
configure secure key distribution/rotation for the audit collector,
authenticate Kubernetes audit ingestion at source, enforce unique
batch ID/digest and immutable retention in a trusted database or
WORM storage, prove the current Capsule controller principal and
causality independently of labels/managedFields, durably record
separate resource-by-resource human approval and successor acceptance,
and re-fetch authoritative provider UID/RV and namespace/related
metadata before individually admitted dry-run and conditional PATCH.
This PR provides no registered writer, collector runtime, endpoint,
Kubernetes client, Release finalizer or database migration.
All gate execution remains HOLD; #1229 OPEN and #1230/#1231 BLOCKED.

## Collector key pin and append-only audit/consent storage — source-only

### Three distinct trust layers

A collector key **pin** is not an operational trust store. The new pure
`capsule_handoff_collector_key_pin.py` validates a versioned,
cluster-scoped collector/key identity, 32+ byte backend key material,
out-of-band pinned SHA-256 fingerprint and an active UTC rotation
window. It rejects rotated/revoked/foreign/mismatched keys without
returning the key. The caller cannot assert trust with a supplied
`verified=true` field: the result **always** reports
`backend_trust_store_source_attested=false` and
`key_rotation_revocation_enforced=false`. Vault/KMS connection,
authenticated key provenance, key revocation distribution and an
operational collector authentication channel remain **unimplemented**.

The preceding `capsule_handoff_collector_receipt.py` can validate a
batch HMAC under a supplied strong key, but neither HMAC nor a key
fingerprint proves apiserver-generated event authenticity or complete
controller causality. Before any real admission, require a separately
authenticated/retained Kubernetes apiserver audit channel, cluster
controller principal identity and independent control of the key
material. No raw key, Kubernetes principal or RoleBinding subject is
stored in the source-only proof ledger.

### Independent audit batch and consent evidence

Two **staged, not migrated** ORM tables are defined in
`app/models/capsule_handoff_proof.py` and migration
`20261011_capsule_audit_consent_proof_ledger.py`, down-revision
`20261011_capsule_ledger`:

- `capsule_handoff_audit_batches`: one immutable collector batch
  UUID globally and at most one collector batch per **Tenant/plan**.
  Records the cluster, generation, plan/worklist/resource review SHA,
  claim/receipt digests, collector/key IDs, capture time and database
  record time, **not** the raw audit events or HMAC key.
- `capsule_handoff_resource_consent_records`: at most one consent
  per Tenant/plan, three independently identified actor IDs
  (requester/reviewer/successor), exactly 1–330 transfer targets and
  source manifest/scope digests. A composite FK requires its parent
  audit batch to match the **same** batch UUID, Tenant, plan,
  worklist and resource-review SHA; consent cannot refer to a
  different provider inventory merely because its plan ID matches.

Both tables have explicit unique and CHECK constraints,
PostgreSQL **UPDATE/DELETE/TRUNCATE-deny** triggers, and SQLite
UPDATE/DELETE-deny triggers. Unsupported SQL dialects are rejected.
For SQLite, the migration additionally refuses creation when
`PRAGMA foreign_keys` is not enabled, but runtime connections also
need enforcement and independent inspection. Downgrade refuses to
erase either non-empty evidence table. The old generic `AuditEvent`
and Capsule `capsule_handoff_ledger_events` attempt history are
left unchanged. No startup migration, live DDL or SQL INSERT writer
has been introduced.

`capsule_handoff_proof_storage_review.py` performs a **read-only,
bounded Tenant-wide historical scan**, never a convenient latest-plan
filter that could conceal prior attempts. It correlates source
report, MAC-checked receipt, human consent proposal and any
committed batch/consent rows. Duplicate rows, changed batch UUID,
cross-plan/foreign Tenant, differing digests, actor mismatch, missing
parent batch or impossible timestamp ordering fail closed. Empty or
partially populated histories explicitly remain blocked/manual-review
cases. Even exactly matched rows report
`historical_replay_absence_proven=false`,
`database_trigger_installation_verified=false`,
`apiserver_audit_integrity_verified=false`,
`independent_consent_authority_verified=false` and
`resource_specific_handoff_admitted=false`: source inspection
cannot prove database immutability or that a human actually
authenticated and committed a consent.

### Remaining operational gates

**Do not activate any writer or executor from this source merge.**
Before a separately authorized database migration and UAT, review
schema/version compatibility, PostgreSQL INSERT-only least privilege,
trigger immutability including privileged DDL attempts, concurrent
batch collision, WAL/synchronous commit, backup/retention and external
WORM audit anchoring. Then separately implement trusted collector key
resolution and revocation, authenticated apiserver ingress,
transactionally fenced append-once batch/consent writers under
independent human approval, fresh provider UID/RV and policy
read-back, and per-object metadata-only authorization. No deployment,
Kubernetes PATCH, dryRun=All, retry, Release or provider handoff
is allowed by these tables or their readers. #1229 OPEN,
#1230/#1231 BLOCKED; all test/CI/CD/provider gates HOLD.

## Transactional Capsule audit+consent proof writer — disabled staged source

`capsule_handoff_proof_writer.py` prepares the **single atomic PostgreSQL
transaction** required before future trusted audit evidence could be
committed. It is **not** an operational writer. Two unconditional source
constants are `False`:
`_CAPSULE_PROOF_WRITER_ENABLED` and
`_AUTHENTICATED_PROVENANCE_AND_CONSENT_WRITER_ENABLED`.
`commit_capsule_proof_pair_staged` raises `PermissionError` before any
database session, key lookup, actor check or SQL write. No environment
switch, API parameter, boolean `confirmed` or self-asserted source
receipt can enable it. There is no registered endpoint, job, queue,
Kubernetes client or invocation by START/executor.

### Future transaction design (NOT activated)

The staged path requires explicit operator confirmation and a fresh
isolated transaction on an **admitted PostgreSQL** database. It
authenticates the Platform Admin actor from existing KAORI access
controls; locks the exact Tenant with `SELECT ... FOR UPDATE`; rejects
a changed Capsule/Ready/Adopted lifecycle, wrong generation or cluster;
refuses **any previous batch/consent for that Tenant**, even from an
earlier plan; and refuses evidence that could retroactively excuse a
`CapsuleHandoffLedgerEvent` START or legacy Capsule executor record.
The approved plan, independent approval, current successor acceptance
and committed release preflight are read again under the Tenant lock.
The preflight's provider identity, handoff components and fingerprint
must match exactly; consent requester, independent reviewer and
accepted successor must be distinct and current.

Pure `build_capsule_proof_pair_candidate` verifies the complete
MAC-checked normalized audit-claim coverage and exact-scope
resource consent proposal, then constructs two safe ORM INSERT
payloads with the same batch UUID, Tenant, plan, worklist and
resource-review SHA. It never includes a key, raw subjects,
provider policy, Kubernetes API body or user credential. Under a
**future** separately admitted writer, the batch parent is flushed
first, followed by the exact composite-FK consent child, then the
enclosing SQL transaction is committed once. `flush` is NOT a
durability acknowledgment; the writer performs a separate SQL read-back
only after commit. If commit is uncertain, the caller must investigate
historical evidence rather than automatically replay the transaction.

Before those writes the staged PostgreSQL inspector requires all
UPDATE/DELETE/TRUNCATE-deny triggers enabled for both evidence
tables; validated uniqueness, shape, independent actor and composite
FK constraints; a non-owner, non-elevated, INSERT/SELECT-only
application role with no CREATE privilege on the table schema;
`fsync=on`, synchronous commit and normal replication role.
The proof schema/migration has additionally been tightened to unique
`tenant_id` on **both** batch and consent tables. This implements the
same conservative one-irreversible-history-per-Tenant boundary as
the earlier Capsule START ledger; a separately sanctioned recovery
would need an additive design, not an overwrite or retry.

### Pending trust and UAT

**Do not confuse source inspection with a successful DB transaction,
installed triggers, backup durability, authenticated controller identity,
or authenticated/committed human consent.** Those remain unproven. A
separate future operator authorization must install/review migration
and role privileges, establish a genuine Vault/KMS-backed collector
key resolver and independently validated apiserver audit provenance,
and provide an authenticated separate per-resource human approval
workflow. Only then may a security-reviewed source change remove
the two hardcoded blockers and independently verify concurrent replay,
ambiguous commit, crash, partial evidence and WAL/backup scenarios.
The START writer and provider executor remain disabled; even a future
committed proof record would **not** grant dry-run, Kubernetes PATCH,
retry, Released, or provider mutation rights on its own.

All test/lint/CI/CD, schema migration, DB writes, Kubernetes/UAT,
deployment, and staging/main promotion remain HOLD. Issue #1229
stays OPEN and #1230/#1231 remain BLOCKED.

## Backend-only collector key resolution and independent IdP consent identity — source only

The next Capsule proof slice separates **server-governed trust from
caller-supplied evidence**. No runtime adapter, endpoint, writer, Vault
request, authentication callback or provider Kubernetes API operation has
been enabled.

### Collector key broker and independent pin policy

`capsule_handoff_collector_key_resolution.py` defines two backend
protocols: `CapsuleCollectorKeyBroker` (read exact
cluster/collector/key-identity pin and secret) and
`CapsuleCollectorPinPolicy` (read the independently governed
expected fingerprint). These dependencies MUST be registered by trusted
server configuration rather than accepted from a browser request,
collector claim, environment flag or mutable resource label. The
staged resolver cross-checks exact cluster/collector/key IDs, active
rotation window and fingerprint, then validates the normalized batch
claims and MAC without returning key material, credentials or raw
provider policy. Broker exceptions must not leak key paths/tokens.

**Two immutable source gates are currently false:**
`_COLLECTOR_RESOLVER_ENABLED` and
`_TRUSTED_COLLECTOR_INGRESS_ENABLED`. All calls therefore raise
`PermissionError` before invoking the broker or policy. They are
not feature flags and cannot be switched on by caller-supplied input.
Even if both source gates were removed by a separate authorized PR,
a matched key fingerprint and MAC would only establish **receipt
integrity under that server-provided key**, not genuine Kubernetes
apiserver event integrity, complete audit capture, controller
ServiceAccount authorship or replay-safe database commit. Independent
Vault/KMS onboarding, key rotation/revocation validation and immutable
audit-ingress attestation remain unresolved.

### Two authenticated-human claims, not assumed authentic identities

`capsule_handoff_consent_identity.py` supplies an exact, bounded
`capsule-resource-human-session-attestation/v1` envelope for the
independent reviewer and accepted successor. Each claimed
authentication event must have its own canonical UUID, distinct
hashed session and one-time challenge, trusted expected IdP/key
identity, claimed phishing-resistant MFA, UTC-aware recent
authentication/issue/expiry times, and the **same** exact
Tenant/cluster/generation/plan/worklist/resource-review/manifest
and approved metadata-only target-scope SHA. The requester's,
reviewer's and successor's independence remains governed by the
existing approved-plan/consent validator. Review action must precede
successor acceptance and the manifest's recorded acceptance timestamp.
Unknown claim fields, stale or duplicated sessions/challenges, actor
substitution and changed target hashes fail closed.

The pure inspector **does not verify an actual login or MAC**.
The optional IdP MAC verifier is unregistered and guarded by two
source booleans fixed `False`:
`_IDENTITY_MAC_VERIFIER_ENABLED` and
`_AUTHENTICATED_HUMAN_SESSION_INGRESS_ENABLED`.
After future explicit authorization it would need a server-owned
IdP key resolver and independently configured issuer/key fingerprint.
Even an authentic MAC cannot prove the upstream human completed MFA,
that the challenge was issued/consumed only once, or that authenticated
consent has been durably recorded. Consequently
`idp_session_origin_authenticated=false`,
`mfa_challenge_verified=false`,
`one_time_challenge_consumed=false`,
`consent_source_authenticated=false` and
`provider_execution_admitted=false` remain fixed.

`review_capsule_origin_consent_docket` now supports an **optional**
pair of asserted IdP session envelopes, tying their SHA digest into
the existing non-executable review docket. No acceptance of these
claims, with or without MAC bytes, elevates proof to execution
authority. Previously prepared audit/consent evidence without
attestations remains **unverified**; issuer IDs supplied without
attestations are rejected.

### Independent gates still required

A later separately authorized workflow must implement and verify
authenticated backend key broker and independent pin policy, trusted
TLS-authenticated Kubernetes audit ingress/collector identity,
correct controller-to-resource causality, real IdP session issuer
verification and phishing-resistant step-up MFA, one-use
transactionally fenced challenge consumption, separate durable human
action with correct role mapping, and current provider UID/RV read-back.
Only after controlled database migration, role/trigger/anti-replay
verification, tests and authorized UAT can any proposed writer be
considered for activation. The START writer, audit/consent writer
and provider executor all remain disabled. #1229 stays OPEN;
#1230/#1231 remain BLOCKED. No tests, CI/CD, migrations, SQL writes,
Kubernetes provider operations, Released state, or promotion are
permitted without fresh explicit operator authorization.

## G2–G3 namespaced quota/limit/RBAC metadata-only handoff candidates — source-only

The existing Capsule Namespace patch and dry-run source contract now has
a corresponding **pure** per-object variant in
`capsule_handoff_contract.py` for each
`ResourceQuota`, `LimitRange` and `RoleBinding`. It does not create
another source-of-truth framework: it consumes the existing
`capsule_handoff_related_inventory.classify_capsule_related_resource`
record (exact Tenant/Namespace, kind/name, UID/resourceVersion, origin,
policy SHA and full original metadata SHA), and it reclassifies the live
**before** object against that evidence.

For KAORI-correlated controls only, the offline
`build_capsule_related_metadata_handoff_patch` constructs RFC 6902
JSON Patch operations with **test** preconditions on UID,
resourceVersion and **all original labels**; removes precisely the
KAORI ownership labels listed in the independently reviewed target
scope; and assigns the separately selected successor's
`app.kubernetes.io/managed-by` marker. The approved label-key set must
equal **all** present KAORI handoff keys (no partial grant/profile
ownership). Unlike ResourceQuota/LimitRange, a RoleBinding must
additionally include the `kaori.io/access-grant` marker, while its
original grant scope and binding contract SHA are required to match.
Foreign labels and all Capsule membership labels remain untouched.
Foreign/unknown ownerReferences, missing source grant, altered UID/RV,
invalid metadata and spoofed/partial KAORI control fail closed.

`verify_capsule_related_metadata_preview` compares a **separately
supplied** server-side dryRun=All result to the exact expected labels,
policy SHA, original UID/Namespace and preserved annotations,
ownerReferences and finalizers. Dry-run resourceVersion is allowed to
remain the same; the preview is never a live successful handoff.
`classify_capsule_related_metadata_readback` instead distinguishes
unmodified **pending** from fully **transferred** state only when an
actual separately supplied read-back includes a **new** resourceVersion
and the exact transferred marker set. Unexpected label, policy,
RoleBinding subjects/roleRef, external metadata, owner or finalizer
mutation, and partial/stale RV are **FAIL** requiring operator review.
Every result still has
`provider_snapshot_authenticity_verified=false`,
`provider_handoff_verified=false`,
`auto_retry_authorized=false` and
`release_authorized=false`.

**Critical remaining G2–G3 integration:** these are offline
per-object functions only. They do **not** authorize or call the
Kubernetes API, integrate an authenticated per-resource consent
decision into the stopped executor, verify operator identity, or
authenticate fresh provider LIST snapshots. The existing
`inspect_capsule_readback_candidate` retains its conservative
whole-inventory-drift blockers until the complete quota/limit/RBAC
provider LIST/read-back proof and immutable START/execution linkage are
implemented and separately reviewed. A scoped per-resource preview
must not be substituted for **complete** provider read-back,
successor acknowledgment, or a verified Released finalizer.
Regression fixtures were authored but **not run** under HOLD.

## G3 — exact related-resource transitions in complete Capsule provider LISTs (source only)

The existing `inspect_capsule_readback_candidate` now incorporates
`_review_related_scope` for **all** resource candidates from the exact
`build_capsule_handoff_worklist`: ResourceQuota, LimitRange and RoleBinding.
It compares the complete original and current bounded canonical LIST
inventory, preserving every protected/noncandidate resource. An optional
`related_transfer_evidence` maps **every** candidate's
`(namespace, kind, name)` to the original raw object, separately
observed current object and exact reviewed KAORI label-key list.
This raw scope must be complete—no extras, missing targets or arbitrary
secret-bearing fields—or the comparison rejects it.

Each candidate's `before` is verified against its original UID/RV,
policy/metadata hashes and binding contract using the existing
`classify_capsule_related_metadata_readback`. Each `current` raw
object is independently reclassified into the **same exact current
canonical LIST row** with the existing inventory normalizer. Only
a complete metadata-only transfer with a *new* resourceVersion is
structurally `provider_markers_transferred`; unchanged exact
source and RV are `pending_provider_transfer`; wrong/missing raw
evidence, partial transfer, unknown origin, changed subjects/roleRef,
policy, UID, ownerReferences, annotations, finalizers, Namespace or
foreign labels are ambiguous/FAIL. Changed provider LIST revision
is explainable only in a Namespace/kind that actually contains such an
exact candidate transfer, with the original object count preserved.
Other LIST revision drift, additions/removals/replacements, any
foreign/unadmitted row change and GlobalResourceQuota or Capsule
CR policy drift remain blocked.

A changed top-level SHA alone does **not** establish a transfer.
Without complete raw evidence, changed candidate data becomes
`ambiguous_recovery_required`, never success. For existing source
callers with no transferred related resources, unmodified KAORI
candidates may still be counted as pending, while all actual transfer
proof is missing. Results add bounded nonsecret
`related_resource_observations` and deterministic readback SHA/counts;
the full G3 status remains
`readback_candidate_recovery_review_required` and
`provider_snapshot_authenticity_verified=false`,
`provider_handoff_verified=false`, `auto_retry_authorized=false`,
`release_authorized=false` **even with every object structurally
transferred**.

**Still required for G3 PASS:** an operator-authorized service
acquiring both raw Kubernetes snapshots and complete LISTs over an
authenticated provider connection, verified current actor SSR/SAR and
per-object independent consent, immutable START before the first
write, guarded conditional dry-run/PATCH, durable attempt/outcome
evidence, unambiguous complete read-back and manual recovery for
partial/lost-commit cases. No API call, database write, executor,
Release or runtime test is performed by this source-only comparator.

## G2–G3 — full-scope offline dry-run → START → read-back correlation (source-only)

This slice reuses the existing
`capsule_handoff_dry_run.py` and
`capsule_handoff_audit_envelope.py` instead of adding another audit
framework or activating a provider executor. The new
`build_capsule_scope_patch_review` accepts the exact committed
Capsule plan, full related LIST inventory, one raw source Namespace
per plan Namespace, **every** raw namespaced quota/limit/RBAC object
including foreign controls, the preserved Capsule CR, and a current
independent-review/successor **consent proposal**. It checks plan
SHA/worklist/resource-review SHA through the existing validators,
reclassifies raw related objects against canonical provider inventory,
and verifies the exact consent targets/label keys. Ambiguous ownership,
incomplete input, unconsented markers, duplicate/foreign targets,
missing policy or changed UID/resourceVersion are blocked. Capsule CR
and non-KAORI resources remain preservation-only; no raw provider
policy, role subjects, or credential is returned in its review digest.
Every candidate JSON Patch is built by the existing Namespace or
quota/limit/RBAC patch builder, but only the patch SHA and immutable
source identity are retained in the non-executable review result.

`inspect_capsule_complete_dry_run_shapes` then requires a **complete**
set of separately supplied preview objects: one for every and only
the approved KAORI transfer candidate. It reconstitutes the same
source patch review, checks each Namespace/related preview via the
existing metadata and provider-spec preservation validators, and
returns only a digest of the normalized review receipts.
**These caller-supplied preview bodies are not proof that Kubernetes
actually ran `dryRun=All`**; `server_dry_run_completed=false`
and `provider_execution_admitted=false` remain fixed.

`inspect_capsule_scope_g2g3_trace` reuses the immutable-shape START
attempt history and G3 read-back claim comparator, rejecting a missing
START claim, altered plan/worklist/consent/patch SHA, incomplete
preview count or mismatched recorded read-back digest/count. It
distinguishes a merely correlated structural trace from pending,
partial or ambiguous/manual-recovery outcomes, and **always**
reports `start_db_commit_verified=false`,
`provider_write_order_verified=false`,
`server_dry_run_source_authenticated=false`,
`readback_authoritative_verified=false`,
`provider_execution_admitted=false`,
`auto_retry_authorized=false`, and
`release_authorized=false`. A matching caller-provided event chain
cannot prove that START was committed before the first live PATCH,
nor that any provider result came from a trusted API session.

**Operational G2/G3 work still blocking #1229:** separately
authorized/apiserver-authenticated acquisition and full-list snapshot
integrity; verified controller ownership and separately authenticated
per-object consent; exact SSR/SAR and server `dryRun=All`; actually
committed write-once START prior to live work; conditional PATCH with
fresh UID/RV under operator authorization; authoritative whole-scope
read-back, durable event/outcome append, recovery for lost
acknowledgment/partial mutation and independent successor acceptance.
Source contracts cannot authorize or substitute these operations.
Test fixtures are **authored, NOT executed**. #1230/#1231, migration,
CI/CD and Kubernetes/UAT execution all remain **HOLD**.

## G2/G3 scope completeness hardening — explicit preserved CR/GlobalResourceQuota (source-only)

Source audit of the existing offline G2→G3 path found two integrity
gaps: the new regression fixture lacked the required
`capsule_related_inventory.blockers` field, and
`build_capsule_scope_patch_review` previously **reported a complete
worklist count without listing the Capsule Tenant CR or any
GlobalResourceQuota in its per-resource manifest**. The fixture now
follows the canonical inventory shape, and the manifest includes
one immutable-source preservation item for the Capsule CR and each
cluster-scoped GlobalResourceQuota, with exact kind/name/UID/RV and
policy/spec SHA bound to the approved worklist. Its complete item
count, identities and source versions must **equal every worklist
item**; no resource may disappear through count subtraction. Unresolved
GlobalResourceQuota selectors remain FAIL.

The operation for those cluster-scoped objects is explicitly
`preserve_source_only_unverified`, **not** a planned PATCH or verified
current provider read-back. `global_quota_provider_readback_verified`
remains `false` even when the source manifest is complete. The
existing `inspect_capsule_scope_g2g3_trace` now revalidates the
manifest's canonical SHA, unique exact worklist membership, each
UID/RV and policy SHA, correct mutation-vs-preservation decisions,
and complete transfer/preserved counts before correlating any START
or read-back claim. Caller-rehashed dropped Capsule CRs, injected
GlobalResourceQuota items and converted preservation-to-PATCH entries
are rejected rather than treated as credible execution scope.

Regression fixtures were authored for the missing field,
explicit Capsule CR and shared quota inclusion, unknown selector
rejection, rehashed altered preservation items, and continued
false trust flags. **No pytest, CI/CD, live provider source scan,
SQL commit, server dryRun=All or Release was executed.** G2/G3
remain blocked until independently authenticated provider
collection, installed write-once START, fresh authorized
conditional executor, exact GlobalResourceQuota preservation
read-back and complete UAT all pass by separate operator authority.

## G3 source consistency — plan-pinned RBAC lineage and unresolved findings (source only)

The existing full-scope `inspect_capsule_readback_candidate` also
checks the source RBAC controller/intent lineage, rather than treating
valid quota/limit/RoleBinding LIST digests as sufficient evidence.
Its **source** `rbac_lineage.lineage_sha256` must match the canonical
Capsule CR component's `capsule_rbac_lineage_sha256` under the
SHA-bound plan, with the unadmitted lineage status and
`controller_origin_verified=false` intact. An altered source
lineage, missing inventory status or malformed `blockers` field is
rejected even when related LIST and GlobalResourceQuota digests match.

Both source and current snapshots must retain explicit
`read_only_related_inventory` posture, `observed_not_handoff_authorized`
GlobalResourceQuota status, and unverified RBAC lineage contract status.
Their bounded blocker lists cannot hide unresolved foreign-owner,
RBAC grant/controller, GlobalResourceQuota selector or collection
findings behind recomputed resource digests. The one permitted
non-authoritative observation warning is the exact canonical message
that an approved KAORI-correlated related resource still requires
handoff; in **current** inventory that warning is valid only while
the same target is classified `pending_provider_transfer`.
A claimed `provider_markers_transferred` resource with a leftover
KAORI-owned warning is inconsistent and remains a G3 blocker.

Regression fixtures were **authored but not executed** for source
lineage SHA mismatch, caller-switched `controller_origin_verified`,
changed inventory/lineage status, source and current malformed blocker
lists, unresolved current RBAC/global quota/foreign findings, permitted
pending warning, and contradictory transferred warning. This is
**source correlation**, not authenticated apiserver audit, proof of
actual controller identity or successful handoff. All source/runtime
writer, Kubernetes server `dryRun=All`, provider PATCH, SQL commit,
UAT, CI/CD and Released gates remain HOLD. #1229 stays OPEN;
#1230/#1231 remain BLOCKED.

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
