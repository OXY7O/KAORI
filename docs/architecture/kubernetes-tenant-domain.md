# Kubernetes Tenant Domain

## Authority

Tenant is a Kubernetes capability/domain in KAORI. The global navigation destination is **Kubernetes → Tenant**. Native Kubernetes and Capsule are provider implementations behind one provider-neutral Tenant contract; provider names do not define separate product workspaces.

## Domain boundary

KAORI owns canonical tenant intent, provider binding, lifecycle, orchestration, committed evidence, governance, correlation, and audit. Kubernetes and Capsule remain authoritative for the enforcement they execute.

The persisted foundation begins with Tenant → Cluster binding → Environment (Development / Staging / Production) → Namespace ownership, plus provider binding, lifecycle/ownership state, correlation, and provider evidence.

Memberships, access grants, credentials, resource profiles, policy, activity correlation, Native enforcement, and Capsule enforcement are delivered by their bounded child workstreams rather than being preimplemented in this foundation.

## Provider authority

Provider binding is per tenant. `native_kubernetes` and `capsule` are the initial provider identities. One governed capability for one tenant has one active reconciliation authority at a time. A binding must never change merely because another provider becomes unavailable. Capsule-to-Native authority transfer is permitted only through explicit `native_recovery` after equivalent enforceable protections are materialized and verified.

## Capsule Namespace attachment entry point (#1124; current UI authority)

Initial **Adopt Capsule Tenant** already imports every Namespace with
unambiguous Capsule correlation in the same committed KAORI adoption.
Subsequent Namespaces added directly to Capsule may surface in live
**Tenant Discovery** as separate, ungoverned `Capsule Namespace` rows.
Only these eligible rows offer **Review Attachment**; adoption of a new
Tenant continues to offer **Review Adoption**. The existing shared
preflight handles Capsule's single existing-Tenant Environment target,
provider UID/resourceVersion, ownership and RBAC evidence, and submits
through the canonical `/discovery/adopt` handler. Managed/blocked rows,
missing privileges and ambiguous ownership never offer an actionable attach.

Tenant Detail no longer shows an unconditional **Namespace Attachment /
Available** accordion or asks for manual provider identifiers. No new
provider API, callback or approval authority is introduced. The legacy
attachment handler may remain registered for compatibility but is not
presented as a second onboarding UI. Capsule provider remains authoritative
and attach is mirror-only, with no Kubernetes write or implicit RBAC grant.
The removed accordion also removes one HTMX/CSRF POST form; remaining
Release/Handback/Decommission forms keep existing behavior and shared
Violet layout. CI/CD, automated gates, Visual QA and formal UAT remain HOLD.

## Ownership

KAORI distinguishes `managed`, `discovered`, and `adopted` resources. Discovery must not silently claim provider resources.

## Capability and integration lifecycle

Tenant readiness follows the existing capability framework: provider evidence → canonical capabilities → Tenant requirements → feature readiness. Capsule is discovered through the existing Kubernetes connection/API authority; it is not registered as a second endpoint and is not an Infrastructure Automation/Orchestration integration.

Capsule compatibility follows KAORI's annual compatibility policy and five-year qualification lookback. This is KAORI qualification policy, not an upstream Capsule support guarantee. Concrete version qualification, upstream lifecycle evidence, CRD/API compatibility, and observed runtime capability evidence remain separate signals.

## UI and settings ownership

Operational management belongs to **Kubernetes → Tenant**. Settings does not receive a second Tenant management surface. When downstream provider discovery/compatibility work owns the evidence, **Settings → General → System Information** and **Compatibility Versions** extend their existing contracts with relevant Tenant/Capsule information.

## Full-cycle acceptance target

The completed feature must prove create → provider selection → profile/namespace provisioning → access/credential governance → managed resources/policy → reconciliation → effective-state verification → audit/governance evidence → update/revoke → governed decommission. Native Kubernetes baseline UAT is mandatory; Capsule-backed UAT is required when the approved compatible Capsule test cluster is available.

## Tenant Operations — primary Allocation / Operational reconcile tabs (#960)

Tenant → Operations uses **one shared primary Content Tabs row** rather than a
nested `Drift & Reconcile` subtab hierarchy. Its five primary tabs are
**Provisioning**, **Runs & Evidence**, **Allocation Drift**,
**Operational Reconcile**, and **Activity**.

- `tab=allocation-drift` displays the **Capsule Tenant Quota Drift** and
  **Capsule Shared Allocation Drift** paginated registries.
- `tab=operational-reconcile` displays **Namespace & Allocation Drift** and
  **Access Reconciliation** as primary paginated registries. The additional
  **Provider Authority** registry remains available in a native
  `View Provider Authority` disclosure collapsed by default; it is not copied
  or removed.
- Prior bookmarked `tab=drift-reconcile` links are accepted as backward
  compatibility aliases: `drift_view=operations` opens Operational Reconcile,
  otherwise Allocation Drift. Newly generated navigation, filters, and pagers
  use **only** the primary tab values, not nested `drift_view` state.

The five original registries retain independent Rows/page/filter query
parameters, canonical empty-state pagination, source-authoritative committed
evidence, and explicit human reconciliation actions. The shared
`content_tabs.render_links` component continues to own URL and HTMX
navigation without a second tab controller, third-level sidebar item, or
provider-side mutation.

Local human acceptance must exercise all five primary tabs, both drift
workflows with empty and populated datasets, browser refresh/back/forward,
per-registry filters/Rows/HTMX, light/dark and mobile views. This is not
staging UAT or production acceptance evidence.

## Tenant Overview — integrated authority & lifecycle (#1081 follow-up; latest detail presentation authority)

Human DevContainer feedback supersedes three distracting standalone surfaces
without weakening governance:

- **Provider Authority:** remove the separate read-only disclosure because
  Provider and Reconciliation Authority are already committed facts in
  Tenant Overview. Keep the original `#tenant-provider-authority` anchor on
  the existing Overview Reconciliation Authority row for inbound links.
  Provider execution/enforcement remains Kubernetes/Capsule authoritative.
- **Authority Boundary:** relocate the **single unchanged authoritative
  statement** into one compact neutral `role=note` row *inside* the Overview
  record sheet. No standalone callout, duplicated provider text, or implied
  transfer of authority.
- **Lifecycle Actions:** relocate the protected lifecycle disclosure *inside*
  the bottom of the same Overview record. Its `#tenant-lifecycle-actions`
  deep link and `tenant_detail_open_section=lifecycle` auto-open behavior
  remain; no second tall numbered card. Preserve Decommission and Retry
  authorization, all recorded preflight blockers, exact CSRF/HTMX payload,
  destructive confirmation modal, and read-only semantics. A normal page
  render does not start lifecycle mutation.

The Hero subtitle is now **“Manage Tenant governance, provider authority,
and lifecycle with committed evidence.”** #1079 Governance Scope KPI section,
Native Release wizard, optional Platform Admin Handback, Capsule Namespace
Attachment, 14 total governance forms, global Operational Toast and provider
read/write boundaries are unchanged. The two optional standalone Handback/
Attachment accordions still use the existing `tenant-governance` native
disclosure group; the Overview lifecycle control no longer participates
in that separate accordion group.

This is a presentation/placement change, not new lifecycle policy. Source
tests cover one provider boundary statement, no duplicate Provider Authority
card, one lifecycle disclosure within Overview, exact form/modal/blocker
preservation, anchor stability and revised section order. Browser light/dark,
desktop/mobile, read-only, blocked/executable, released/decommissioned states
need human DevContainer Visual QA; CI/CD, Developer Check, Full Admission,
staging UAT, main promotion and deployment remain HOLD.

## Tenant Overview compact committed record (#1081; historical compact foundation, integrated placement supersedes boundary/footer arrangement)

DevContainer review of the initial #1081 record sheet found that the two inner
sub-panel headers, dedicated Record History band and tall Description band
still consumed too much height. The current **Tenant Overview** preserves
one bordered KAORI surface, but uses a **single compact header** and the
following direct information hierarchy:

1. Exact full Tenant ID in the existing wrapped monospace `technical_value`
   presentation.
2. Eight committed facts in a responsive **4/2/1-column** grid: Cluster,
   Provider, Ownership, Lifecycle (canonical semantic status), Reconciliation
   Authority, Generation, Registered and Last Updated.
3. A small conditional historical Namespace audit footnote, distinct from
   active Namespace coverage.
4. A final inline-label Description row, never clipped or truncated; preserve
   whitespace without introducing template-indentation artifacts.

Avoid duplicating already visible #1079 Governance Scope KPI metrics. Only
KAORI committed Tenant and Cluster state is read for this record. Values
remain literal provider bindings and governance facts (not derived provider
health); unknown dates show `Not recorded`. Extra-long ID, cluster, authority
and description text wrap safely, with existing Violet tokens and shared
`section_intro` / `table_label` / `technical_value` macros. No custom
component, new provider request, data mutation, permission or backend change.
Preserve the standalone Authority Boundary note, four-step Release wizard,
14 existing CSRF/HTMX forms, toast and all other governance workspaces.

This supersedes only the earlier #1081 two-inner-panel/Record-History-band
composition, not #1079's established posture grid or #1075's lifecycle
semantics. Human local browser review (mobile, light/dark, long values)
remains required. Developer Check, CI/CD, Full Admission, UAT and deployment
remain HOLD pending explicit authorization.

## Tenant Detail — committed Namespace / Resource Profile mapping (#1136)

The canonical Tenant Detail now includes **Namespace & Resource Profile Mapping**
directly before the Release/Handback administration section. It reuses
`section_intro`, `operational_section_card`, shared status labels and
the approved Violet responsive operational **card** and empty-state patterns.
As of #1138, the large mapping table has been replaced by **one card per
Namespace** to keep a single Namespace readable and make multiple Namespace
allocations scan-friendly. Follow-up #1140 makes the card grid
**count-aware**: one Namespace consumes the full operational panel width;
two or more use two columns at `xl` and one column on smaller viewports.
There is no fixed half-width allocation for a single card, no page-wide
horizontal overflow, and no change to the shared operational card or quota
metrics. This is a **bounded five-card committed projection**,
not a second Namespace Registry:
select only records correlated by the exact TenantEnvironment tenant ID, eager
load their Resource Profile, order by newest generation records and retain
Released/Deprovisioned history with clear historical labels. A link opens
the existing Namespace Provisioning Registry filtered to that Tenant for
the full collection. No provider GET, new management action, global
profile mutation, schema migration or workflow branch is introduced.

Each card distinguishes Native/other adopted provider-baseline lineage from
a real linked Resource Profile, shows the **profile public ID** where linked,
the pinned Resource Profile snapshot version and customization, allocation
control state (historical records are explicitly **last committed**),
Namespace ownership/lifecycle/generation and provider UID/last reconciliation
evidence. CPU/Memory requests/limits, Pod slots and storage are frozen
KAORI `allocation_quota_json` snapshots; unknown/unrecorded values are
not fabricated and **not interpreted as live Kubernetes utilization**.
A reusable Resource Profile definition may be revised to a new version
without changing a Namespace's already-pinned snapshot until a separately
admitted Allocation Change or rollout.

**Verified cross-Release lineage (#1138):** For Native re-adoption,
the current Tenant's committed `re_adoption_lineage` explicitly binds
`predecessor_tenant_id`, prior Tenant generation/correlation ID and
`provider_uid_verified=True`. Only this bounded ancestor chain (up to
five prior Tenant generations), matching exact cluster, Tenant slug, provider,
prior Released lifecycle and the same immutable provider UID and namespace
name, can expose prior Released Namespace allocation snapshots. A
cross-Tenant name-only match is forbidden. The cards provide optional,
keyboard-accessible `Lifecycle History` disclosure with each verified
predecessor's pinned Resource Profile and quota snapshot. If the evidence
does not satisfy all checks, omit that history and show that no **verified**
cross-Tenant lineage is available; never fabricate one from Gen 3 or
rename/reuse of a Namespace. History is a bounded committed database read,
not a live provider request, and does not compare or claim current
Kubernetes state. The existing filtered Namespace Registry remains the
source for the full current Tenant list, not a cross-Tenant administration
view.

**Native verification sequence and required invariants:**
`Discover/Adopt existing Namespace → materialize its equivalent observed
baseline → admitted managed Allocation Change (if requested) → live
provider read-back of ResourceQuota/LimitRange → governed Native Release
handoff → live read-back with unchanged provider allocation spec →
independently authorized Handback / residual recovery if necessary →
fresh Discovery → explicit new generation Re-adopt`.
Native Release transfers the scoped KAORI ownership/manager metadata to
its successor, **not CPU/memory/storage/quota or workload sizing**. Therefore
Kubernetes allocation changes must already be admitted, executed and
verified **before** Release; Released state and ownership markers change
while committed and effective resource values remain identical. Handback
or metadata recovery additionally changes authorized ownership metadata
only. Historic generation snapshots and exact provider UID/RV evidence are
retained for an auditable pre-/post-release comparison. Read-only mapping
cannot substitute for provider GET or quality/UAT proof.

Source integration is limited to `kaori/review/staging-uat` for DevContainer
review; automated gates, provider mutations and staging/main promotion
remain HOLD pending separate authorization.

## Tenant Details Governance Scope — shared estate posture composition (#1079; current scope UI authority)

Human visual reference: the existing **Kubernetes Tenant Overview → Governance
Scope → Tenant Estate** section. Reuse exactly its approved **shared KAORI
components**, not manual cards: `section_intro.render`, `operational_section_card.render`
with `body_classes='p-0'`, and `resource_posture_grid.render(columns=4)`.
The card owns the header icon, title, description, spacing and border, while
the posture grid owns vertical separators, compact metric icons, responsive
grid layout, tone treatment and light/dark compatibility.

A single Tenant is **not the entire fleet**: use four committed values
already available in Tenant Details — **Active Namespaces, Environments,
Reconciliation Authority, Lifecycle** — rather than the aggregate overview's
Tenants, Managed Clusters, Credentials and Findings values. The section card
is titled **Tenant Governance** with a concise Tenant-specific description.
Do not fabricate fleet-wide or live provider results, or duplicate the earlier
two separate Resource Coverage/Governance Authority cards. Preserve the
independent **Authority Boundary** info note and the governed Release wizard.

This supersedes only the four-metric **presentation** in #1077, not its
source-of-truth, permission, audit or workflow standards. Browser desktop/
mobile, light/dark, long metric values and toast Visual QA is pending;
Developer Check, Full Admission, staging and deployment remain HOLD.

## Native Platform Admin verified Kubernetes TLS prerequisite (#1047; detail UI authority)

The Platform Admin Native successor-acceptance contract requires a **registered,
verified Kubernetes API TLS connection** before provider SelfSubjectReview
and scoped SelfSubjectAccessReview. Its authoritative backend guard is
`cluster.kubernetes_connection.verify_ssl is True` in
`native_platform_admin_authority.verify_native_provider_admin_authority`.
A KAORI superuser, independent approval, success on an unverified transport,
or a typed successor reference must never substitute for this trust boundary.

Human DevContainer feedback showed Step 3 still exposing **Verify Provider &
Accept as Platform Admin** for a non-TLS-verified cluster connection, which
deterministically failed with `Verified Kubernetes TLS is required for
Platform Admin authority`. Step 3 now uses the **existing committed
KubernetesConnection.verify_ssl** state and offers a compact **Verified TLS
Required** explanation instead of a doomed submit. Its settings link appears
only when the operator has `clusters.manage` and a registered Cluster exists;
other operators are asked to contact the Cluster administrator. For otherwise
current, independently acknowledged plans, Step 4's next-action panel mirrors
the same prerequisite without changing the five checkpoint data model. The
original acceptance form remains available if TLS verification is enabled,
but the backend still revalidates the connection and provider principal at
submission time. No new provider request is made by the normal UI.

**Operator remediation must use the canonical Kubernetes Connection edit
workflow:** verify kubeconfig CA certificate and API endpoint certificate
hostname/SAN, enable **Verify Kubernetes API TLS Certificate**, run the
existing Test Connection, save the connection, then complete **Full
Validation**. Changes invalidate saved operational readiness; never flip
the DB field manually or disable certificate verification for convenience.
Changing the cluster connection is a separate security/deployment-sensitive
operation, requiring authorization and human UAT; it is not performed as
part of this UI change. Expiring plan/review evidence must be restarted
under the original requester + independent reviewer flow.

All 14 existing Tenant governance CSRF/HTMX form sources, SHA/fingerprint,
authn/RBAC and Release rules stay unchanged. Review-only merge to
`kaori/review/staging-uat`; runtime tests, browser Visual QA, CI/CD,
Developer Check, Full Admission, staging UAT and deployment HOLD.

## Native external read-back: current evidence versus historical receipts (#1095 follow-up)

Human DevContainer feedback after clicking `Verify Provider Read-Back` found
the backend correctly returned **Native External Handoff Read-Back Blocked**
(`A complete independent plan, successor reference and passed dry-run are
required.`) even though Step 3 displayed a historical **Dry-Run Passed** and
an expired independently reviewed plan. This is a **false UI affordance**:
the previous Step 3 rendering checked only the presence of a same-SHA
successor-reference and dry-run receipt, whereas
`native_handoff_readback.observe_external_native_handoff_committed`
requires the exact plan/reviewer, claim and dry-run evidence to be current,
scope/fingerprint-matched and mutually consistent. With stale approval the
function rejects **before** making a Kubernetes provider read.

The committed `project_native_release_readiness` now exposes UI-only
`external_reference_current` and
`external_readback_prerequisites_current`, using the **existing**
`_checked_recently` helper. Current evidence must include fresh plan and
independent approval, SHA/actor/fingerprint correlation, fresh same-owner
external reference, and a fresh exact-fingerprint dry-run receipt that
neither mutated provider objects nor authorized Release. These values
are **presentation hints, never a new admission authority**; the backend
continues to check `_plan_hash`, tenant identity/dependencies/provider
state and complete preflight evidence before contacting Kubernetes.

Step 3 now displays a compact, contextual explanation instead of the
unusable checkbox/button when evidence is expired or incomplete. With
`approval_expired`, the original requester must follow Step 4's governed
restart; this creates a new plan SHA and requires a separate fresh reviewer,
new reference and fresh dry-run. The form is shown only when its advisory
prerequisites are current. The action is explicitly **Inspect External
Handoff**: read-only inspection **after an external operator actually
performed the handoff**, not the **KAORI-controlled Execute Native Handoff**
path and never a successor consent grant. Historical read-back counters
are labeled as recorded history rather than current proof.

Original 14 Tenant form/CSRF source contracts, provider-authoritative
checks, RBAC/TLS, separation of duties, time limits, AuditEvents,
partial-handoff recovery and UAT/Release admission remain unchanged.
Only committed projections and form presentation were refined. Unit/source
tests are authored; DevContainer Visual QA and all CI/CD, Developer Check,
Full Admission, staging/UAT, promotion and deployment remain **HOLD**.

## Tenant Release wizard navigation and confirmation/result semantics (#1095; current UX authority)

Human DevContainer review found that all four Release wizard step cards and
Previous/Next links were plain full-page GET links, while mutation POSTs
already used scoped HTMX fragment swaps. Because the entire committed
Tenant Detail is re-rendered after every POST, native required checkboxes
reset by design, leaving it unclear whether the operator had just
**checked**, **submitted**, **received a rejection**, or **committed evidence**.

Wizard step navigation now follows the existing KAORI HTMX model:
`hx-get` + `hx-select="#tenant-release-governance"` +
`hx-target="#tenant-release-governance"` +
`hx-swap="outerHTML show:none focus-scroll:false"`, with `hx-push-url`
set to the same canonical step URL as its preserved `href`. An authorized
HTMX GET returns the existing committed Tenant Detail fragment, but HTMX
swaps only the Release Governance card rather than the entire shell or
Tenant Overview; ordinary GET and browser history
restoration retain the original full-page route. `hx-history="false"`
prevents caching historical tenant authorization evidence in HTMX snapshots:
back/forward must request fresh committed state. No new routes, provider
calls or wizard approval state are introduced, and no-JS navigation works.

All 14 existing Tenant governance forms retain POST URLs, CSRF, field names,
HTMX replacement and global Operational Toast. Native
`hx-disabled-elt="find button[type='submit']"` prevents accidental
double submissions during the request and the existing HTMX indicator
is visible near the action viewport. The single server-recorded
`g.tenant_operational_feedback` result is also passed into the existing
Tenant Detail response and shown inline above the active Release step,
with the same title/message as the original Operational Toast. It is a
**request outcome**, never an inferred provider commit or approval stage.
Confirmation checkboxes are explicitly **one-shot operator intent**:
checking a box alone does not persist governance approval; re-render/reset
after POST is intentional, and only server-reported results plus fresh
committed evidence/Activity Audit establish what happened. Never carry
checked consent across steps, browser history or expired plan SHA.

This presentation correction does not alter separation of duties, current
approval expiry/TLS requirements, Release execution, read-back, role guards,
AuditEvents, governance admission, provider authority or any external
object. Contract tests are authored; runtime tests, light/dark/mobile
browser QA, CI/CD, Developer Check, Full Admission, UAT, promotion and
deployment remain HOLD until separately authorized.

## Governed no-transfer recovery after historical failed Native executor (#1104; #1057 child)

An expired, independently approved Native Release plan with a committed
`in_progress` -> `partial_handoff_recovery_required` executor audit cannot
be restarted using ordinary expired-plan renewal, even with 0/2 verified.
The earlier executor bug #1102 (preview vs approved component) could fail
before the first provider write; a negative mutation counter alone does not
prove provider state or authorize retry.

This is a **two-person, read-only-first** governance extension for fully
verified no-transfer only. The requester/assessor cannot self-approve; the
original executor may independently review a canonical no-transfer
assessment. Unknown/partial/full mutation remains fail-closed, with
separate manual recovery. Normal Tenant GETs consume committed KAORI
state only.

1. **Requester assessment** (original plan `requested_by` actor):
   require one exact SHA/fingerprint/generation Native plan, originally
   independently approved but now expired. For #1118, verify one or more
   complete ordered `native_handoff_started` →
   `native_handoff_recovery_required` pairs with the **same** executor actor
   throughout, 0 verified and `provider_mutation_performed=False` for
   every terminal receipt. Any orphan/duplicate/out-of-order/unknown/mutated
   attempt or non-canonical same-plan read-back remains blocked.
   Any same-plan external read-back must independently satisfy the existing
   full canonical `provider_handoff_not_started` receipt contract, and its
   immutable content is included in the recovery source-history digest. Any
   partial/full/unknown/duplicate history fails closed. Perform current
   authoritative Release preflight and compare the original complete
   provider identity, ownership handoff inventory, fingerprint and all
   dependencies. Reuse existing canonical dry-run evidence and read-only
   `_read_resource` / `summarize_native_handoff_recovery` to verify
   original UID/resourceVersion, every KAORI marker, specification SHA256
   and retained foreign metadata hash. Require all components
   `pending_provider_transfer`. Persist immutable SHA-bound assessment,
   audit history digest, every failed event ID and attempt count,
   assessment actor and provider proof hash. **No provider PATCH**.
2. **Independent recovery decision**: a second authorized operator must
   be different from the original requester/assessor. The original failed
   executor may independently approve this **canonical verified-no-transfer**
   assessment, since all historical attempts, read-backs and fresh
   authoritative provider proof have already been validated. The decision
   binds assessment SHA, history digest, exact plan/fingerprint, observed
   provider proof and current timestamps. It grants *only* a fresh
   requester plan renewal, never provider transfer, consent or Release.
   Self-approval by the requester and unsafe/partial evidence remain blocked.
3. **Original requester restart**: backend revalidates original plan,
   original independent approval, new distinct recovery decision, full
   executor/read-back history, fresh authoritative provider preflight and
   exact preserved provider proof, before and under the existing Tenant
   lock. The new handoff plan SHA is a new immutable audit event with
   `supersedes_plan_sha256`, `no_transfer_recovery_assessment_sha256`
   and `no_transfer_recovery_authorized_by` lineage. Old approval,
   dry-run, reference and Platform Admin acceptance do **not** carry over.
   Another authorized independent reviewer must approve the new SHA, and
   a fresh verified Platform Admin acceptance/dry-run is necessary before
   any later authorized handoff.

Assessments and decisions expire through the existing 15-minute
`_checked_recently` contract. If a decision expires or history changes,
the requester must assess again and obtain a new independent decision.
The review UI reads two additional committed AuditEvent targets and
reuses the existing Release Governance panel, Violet status badges,
CSRF/HTMX POST, pending/Toast and focus patterns. No new provider authority,
automatic retry/rollback, new admin token, weakened TLS/RBAC, or
Released commit is introduced.

The present Docker Desktop evidence includes live UID/RV and KAORI owner
labels, which is **supporting data only**; it is not equivalent to a
successful full assessment of spec/foreign metadata and exact audit
history. CI/CD, unit tests, Developer Check, Full Admission, browser QA,
live Kubernetes actions, UAT, promotion and deployment remain HOLD
until separately approved.

## Expired Native plan recovery after canonical zero-transfer read-back (#1057; latest recovery authority)

DevContainer screenshots exposed a **stranded renewal** after an expired
independently acknowledged Native Release plan: Step 4 treated *any* same-plan
read-back as evidence of a partial handoff, even when the committed receipt
reported **0 transferred resources**. The original requester could not use
`Restart Expired Handoff Plan`; a different account also could not restart
because separation of duties must remain intact. Step 3 still offered a
`Preview Native Transfer` dry-run on expired evidence, resulting in an
expected backend rejection.

A read-back count of zero **alone is never clearance**. Recovery
`provider_handoff_not_started` is now a narrow, auditable classification
only when the **full canonical read-back receipt** and its nested recovery
agree: exact plan SHA, Tenant/cluster/generation/fingerprint, matching unique
external-handoff resource identity and original UID/resourceVersion; every
object is `pending_provider_transfer`; provider specs/foreign metadata
preserved; transferred count is exactly 0, pending count equals exact
resource scope, and all provider mutation/transfer/consent/Release flags
are explicitly false. Missing, conflicting, partially transferred, fully
transferred or legacy counter-only receipts remain **FAIL CLOSED**.

Before an expired plan can be superseded, the requester-only backend:
1. Revalidates the exact committed, previously acknowledged plan, independent
   reviewer, expiry timestamps and explicit confirmation.
2. Reads **all** historical read-back receipts and Native executor attempts
   for this Tenant and rejects every unsafe event for the same plan.
   A later zero-transfer observation cannot conceal earlier partial/full
   transfer or an executor attempt. Invalid/missing SHA receipt provenance
   also blocks recovery.
3. Performs the **existing fresh provider-authoritative Release preflight**,
   including dependency-zero checks, UID/resourceVersion, original live
   provider identity and unchanged handoff fingerprint. This check remains
   mandatory even when every historical observation says no transfer.
4. Acquires the existing Tenant row lock, verifies no competing plan, and
   re-reads committed read-back/executor history to reject new receipts
   recorded during the preflight before committing the replacement SHA.
5. Persists immutable `supersedes_plan_sha256`, restart reason and
   `restart_zero_transfer_readback_reverified` evidence. The new SHA has
   **pending** independent review; prior approval/reference/dry-run/
   successor consent are not inherited and no Kubernetes mutation occurs.

The committed-state Step 4 readiness projection receives read-back and
executor history for the paginated Tenant set. It distinguishes
**Safe for fresh verification (not auto-clearance)** from **Recovery
required**. Only the original requester with existing permissions sees
the explicit restart confirmation; other users are told to request that
operator. Step 3 no longer presents Native Dry-Run if the plan/independent
approval/review has expired. These are presentation hints: server-side
restart and all other Release security gates are always authoritative.

This bounded follow-up **does not** allow any partial/full transfer retry,
mark provider ownership transferred, verify successor consent, commit
Released, bypass X.509/RBAC or create a general rollback engine.
Native Kubernetes is still authoritative. Human DevContainer review, unit
tests, contract tests and staging/UAT evidence are pending. CI/CD,
Developer Check, Full Admission, promotion and deployment remain HOLD
until separately authorized.

## Read-only Native executor no-transfer recovery assessment (#1110)

A prior provider executor can report `partial_handoff_recovery_required`
and 0/2 verified with `provider_mutation_performed=False`, while the original
plan and independent approval have expired. Recorded 0 does **not** establish
that no Kubernetes mutation occurred; a read-only GET of UID/RV and KAORI
markers is preliminary provider evidence, not a complete canonical recovery
decision. The existing restart guard continues to reject every same-plan
executor attempt.

The committed-readiness projection now exposes advisory
`no_transfer_assessment_candidate` only if there is current-plan executor
history with one or more complete `in_progress` →
`partial_handoff_recovery_required` pairs in newest-first committed order.
The start record does not yet contain mutation/verified outcome fields;
the final failure must explicitly report zero verified, no mutation, no
provider verification or Release, with an exact plan SHA/fingerprint.
Any orphan, malformed, mismatched or incomplete executor event, non-canonical
same-plan read-back or known/unknown provider effect suppresses the advisory. The Step 4
recovery panel explains candidate versus blocked evidence alongside the
separate #1104 governed requester assessment, independent decision and
requester-only fresh-plan restart controls. The **candidate itself** offers
no mutation or restart authority, is not an admission predicate and never
overrides `restart_blocked_by_readback`.

The separately implemented #1104 governed recovery workstream requires fresh
authoritative Kubernetes inspection of all originally approved components:
UID/RV, exact ownership markers, complete spec hash, retained foreign
metadata, dependencies, previous AuditEvents and in-progress operations,
then a distinct immutable approval by a permitted independent reviewer.
Only the original requester may attempt a fresh Plan SHA after the service
revalidates the proof and audit history. Historical AuditEvents must never
be erased, nor may their observations be reinterpreted as Released.
Developer Check, CI/CD, Full Admission, UAT and deployment remain HOLD.

## Bounded multi-attempt no-transfer recovery (#1118)

DevContainer evidence established two historical started/failed-before-write
Native executor attempts on the exact original Plan SHA: both terminal
receipts report 0 verified and no provider mutation; four original
read-backs independently returned `readback_proves_handoff_not_started=True`.
Those observations are **historical only**, not current provider authorization.

The approved #1118 source-only contract extends #1104's historical parser
from one pair to one or more complete chronological pairs. Every start/failure
must match the same original plan SHA/fingerprint, tenant/generation, selected
scope and single executor actor. Every terminal failure must contain verified
zero, empty verified components, explicit false mutation/verification/Release,
and a real error record. Any missing, repeated, out-of-order, mixed-actor,
partial, successful, or otherwise ambiguous attempt fails closed. The
original read-back predicate applies to **all** same-plan observations,
including those between attempts. SHA256 history binds every event's ID,
actor, action and metadata. Assessment also records all failed event IDs
and attempt count, and the original-requester restart revalidates them.

Source-only admission does not authorize a Kubernetes PATCH or Release.
Fresh provider-authoritative preflight and TLS-verified GET of original
UID/RV/spec/foreign metadata, complete dry-run evidence and dependency
checks remain mandatory before immutable assessment; an independent
second-operator decision (potentially by the original executor, but not
the requester/assessor) remains required before a new requester-owned
SHA can be reviewed. No old approval/dry-run/consent is inherited.
No provider mutation, workflow deployment or CI/CD gate was executed.
Tests, Developer Check, Full Admission and formal UAT remain HOLD.

## Native handoff approved component versus preview evidence binding (#1102; #1048 authority)

During DevContainer testing of the approved Native Release flow, the
KAORI-controlled provider executor recorded a failure on the first
ResourceQuota as `ValueError`, 0/2 verified and
`provider_mutation_performed=False`. The current execution code passed a
canonical `dry_run_native_handoff_component` receipt to
`build_native_successor_handoff_patch`, but the dry-run receipt intentionally
does **not** contain the approved `handoff` or `ownership` classification.
The downstream `build_native_handoff_patch` correctly rejects missing
authority before a live PATCH. The exact live error message remains
sanitized in the AuditEvent; this is a source-level causal finding.

The Native executor now resolves the **approved original plan component**
for each exact preview key (namespace, kind, name, UID), and requires
a unique match, `handoff=external_acceptance_required`,
`ownership=kaori_marker_correlated`, matching resourceVersion, and
canonical dry-run operation/live-unchanged flags. It validates all such
plan-preview pairs **before** committing `in_progress` and before any
Kubernetes mutation. The approved plan component is the *only* input to
the existing successor PATCH builder; the preview receipt remains the
provider-state proof for classification, spec/foreign metadata hashes,
post-change verification and read-back. This is **authority binding**, not
permission elevation or fallback to user-provided ownership labels.

All original security boundaries remain: actor-restricted accepted X.509
identity, fresh SHA/fingerprint and independent approval, Kubernetes
SelfSubjectReview and scoped SelfSubjectAccessReview, conditional UID/RV
JSON PATCH, metadata-only changes, spec/foreign metadata preservation,
provider read-back, partial-transfer audit lineage, no Released commit on
executor failure. Previously recorded `partial_handoff_recovery_required`
is NOT reset by deploying a code fix. The actual provider state must be
independently inspected before existing governed recovery can be authorized;
old approval expiry and actor separation still apply.

Source-only regression tests were authored for realistic preview receipts
without governance fields across Namespace/ResourceQuota/LimitRange, exact
plan authority match, and fail-closed stale/foreign/duplicate components.
Runtime test execution, provider/UAT, Developer Check, Full Admission,
CI/CD, main promotion and deployment remain HOLD pending explicit approval.

## Current Native executor recovery as Release wizard priority (#1091 follow-up)

DevContainer human feedback confirmed the original requester, independent reviewer
and accepted Platform Admin correctly share **3/5 committed readiness** across
accounts, while their buttons are scoped by actor (`Resume Verified Native
Handoff` for the accepted operator, `Preview Native Transfer` for another
eligible operator). After an executor attempt failed with **0 of 2 provider
objects verified**, Step 3 still displayed **Transfer Pending** and Step 4
**Verification Required**, although the current exact-plan executor had
already recorded `partial_handoff_recovery_required`.

The authoritative operation remains
`native_handoff_executor.execute_native_handoff_committed`. Its AuditEvent
records plan SHA, fingerprint, status, `verified_count`,
`expected_component_count`, `provider_mutation_performed` and sanitized
resource+exception-class summaries under `errors`. **0 verified does not
mean no resources mutated**: writes can precede a failed post-write read-back.

The committed-only `project_native_release_readiness` now exposes
`provider_handoff_recovery_required` *only* for the latest
`partial_handoff_recovery_required` executor receipt matching the current
plan SHA and handoff fingerprint with `provider_handoff_verified=False`.
The fourth checkpoint displays **Recovery Required** rather than generic
Pending, remaining incomplete; this flag never admits a mutation or Release.
Step 3 header prioritizes **Recovery Required** over **Transfer Pending**,
and Step 4's **Next required action** prioritizes recovery over normal
approval/TLS/verification guidance. It shows read-only 0/2 (or actual
counts), explicit mutation reported Yes/No/Unknown, at most three already
sanitized error summaries, an Activity Audit event type and a link back to
the existing Handoff Evidence step.

No automatic resume, no new "safe to retry" classification, no new endpoint,
and no change to role-scoped conditional form eligibility or backend
provider checks. The operator must correlate the same Plan SHA in
`tenant.release.native_handoff_recovery_required` and independently inspect
current Kubernetes marker/UID/resourceVersion evidence before authorizing
existing governed recovery. No evidence supplied in the screenshot proves
the specific provider failure class; detailed root-cause resolution remains
an operator investigation, not a fabricated release-success state.

This remains consistent with the Violet design system, committed
read-model, HTMX history and global Operational Toast. Existing tests now
cover current-versus-historical executor SHA/fingerprint, a 0-verified
mutation-positive attempt, form retention and recovery precedence.
DevContainer QA, runtime tests and all CI/CD, Developer Check, Full
Admission, staging/UAT, main promotion and deployment stay HOLD.

## Native Release expiry consistency and Step 4 recovery workspace (#1091; latest detail UI authority)

DevContainer feedback confirmed an expired, independently acknowledged Native
plan: Step 4 correctly projected **Release review Expired** and
**Independent approval Recorded · Expired** (0/5 checkpoints), while Step 3
still said **Transfer Pending** and displayed Platform Admin acceptance.
The backend `accept_native_successor_handoff_committed` already requires
current plan and approval timestamps (both within the existing 900-second
window), SHA/fingerprint and distinct requester; presentation alone must
never pretend stale evidence is executable.

Step 3 now uses **the same committed `row.native_release_readiness`
projection** as Step 4 to display **Approval Expired** or **Review Expired**.
A compact warning links directly to Step 4 recovery. The existing Native
Platform Admin consent form is only presented when both
`approval_complete` and `review_complete` are true, in addition to
existing non-requester, permission and plan-state guards. Capsule's separate
authority and other Native backend safeguards are unchanged. Expiry remains
server-authoritative at submission time (a page can become stale while open).

Step 4 replaces a long narrative card with one bounded **2-area responsive
readiness + next required action** workspace: five committed checkpoints
with original status/detail and semantic tones, plus one conditional
recovery/action panel. In the expired case, the existing **Restart Expired
Handoff Plan** form stays exactly requester-only and requires explicit
confirmation and fresh provider preflight; read-back/recovery blocks
restart, and other operators see a clear instruction to ask the original
requester. When only provider review is stale, link back to Review Scope;
when approval is not completed, link to Approval & Handoff. No false Release
CTA, no automated restart, no provider API call from normal UI, no new
readiness policy. Existing Release/Finalize safety controls after Step 4,
provider read-back and audit remain intact. Five checkpoints are never
equivalent to approval to promote staging.

The implementation stays presentation-only: reuse shared Violet surfaces,
`table_label.status_label`, HTMX/form patterns, full SHA evidence and
responsive text. All 14 original Tenant forms/CSRF including restart and
Platform Admin remain in source; role/readiness conditions control which
forms render. Existing security authority #1057/#1040/#1045/#1047–#1049
remains controlling. Human light/dark/mobile, requester/reviewer, expired
plan, read-back and post-expiry navigation QA pending. pytest/lint,
Developer Check, CI/CD, Full Admission, staging UAT, promotion and
deployment remain **HOLD** until explicit direction.

## Release Step 3→4 actionable handoff guidance (#1183; 2026-10-11 DevContainer)

Native Release readiness is evidence-only. Independent Review Recorded and a
successful **Preview Native Transfer** (dry-run) do **not** prove Platform Admin
acceptance or a provider mutation. `External Reference Unverified` is not
consent. Step 4 shows **2/5** when only review and independent approval pass.
The correct next operation is in Step 3: a distinct authorized Platform Admin
(non-requester) must verify the registered Kubernetes X.509 TLS connection,
provider SelfSubjectReview and scoped SelfSubjectAccessReview, and explicitly
record acceptance for the same Plan SHA. Only after accepted, current dry-run
and independently admitted provider execution/read-back may an authorized
Platform Admin execute the Native handoff; the canonical finalizer is separate.
If the logged-in account created the plan, its acceptance form remains absent
and the UI now explains why, instead of silently hiding the action.
No new provider mutation, bypass, account privilege, successor token or
Release shortcut is introduced.

The Resource Profile allocation blocker is shortened for faster reading but
still states independent approval, verified provider handoff/read-back, and
non-destructive preservation. The original long blocker remains in the
explicit trusted-reason allowlist for historical plan compatibility only; new
reviews produce the shorter reason.

## Dev Container UI follow-up — cohesive approval surfaces and expired recovery (#2401)

After human screenshots of the acknowledged Native plan, Step 3 now keeps
**Handoff Actions** in a single unbroken Violet surface (reference form
and conditional authorized Platform Admin action or requester-only note).
The external read-back area remains one companion surface. Its unavailable
state is inline under the same header, not an extra card inside a card.
Both columns stretch to a common workspace height on desktop and stack
naturally on narrow screens. The read-back prerequisite branch, owner
permissions, exact plan SHA and provider verification POST remain original
authorities; UI spacing never implies eligibility or transfers ownership.

Step 4 **Approval Expired** is now an unboxed semantic recovery sequence
with three ordered steps, driven by the same read-back guard: verify
ownership, request governed recovery **instead of restart when blocked**
(or restart only as the original requester when safe), then obtain fresh
independent approval for a newly prepared plan SHA. Historical approval
remains audit evidence, never current authorization. The existing CSRF
and explicit requester-only restart form, conditional no-transfer note,
and role-restricted alternative instructions remain intact. Native
provider-effect recovery always overrides restart. Source contract tests
check Jinja structure, conditional branches and unchanged forms; runtime
Dev Container tests/visual acceptance are still outstanding. Official
CI/CD admission remains HOLD.

## Release Governance Step 3–4 approval layout and verification guidance (#2401; 2026-10-18)

The Step 3 governed workflow now uses Title Case for **Independent Approval and
Handoff**, **Prepare Handoff Plan**, **Approval Boundaries**, and **Planned
Handoff Record**. The independent reviewer consent text is shortened to
"I reviewed the successor, change record, and provider evidence; no transfer
occurred." Its required checkbox, same-Plan-SHA confirmation and backend
authorization rules remain unchanged.

For an independently acknowledged Native plan, the external successor
reference action and the role-gated Platform Admin verification now occupy
a responsive 3:2 actions/evidence workspace rather than narrow form cards
followed by a full-width inspection warning. The original external
read-back inspection form or conditional unavailable/stale prerequisite
status is **moved unchanged** to the evidence column; on mobile the columns
stack. This preserves all current plan/SHA, actor, trusted X.509, checked
provider permissions, HTMX, CSRF, independent approval, and exact provider
read-back gates. Capsule/expired/other roles keep their separate conditional
scope. Reference evidence never creates consent; read-back never transfers
ownership by inspection. No provider mutation was introduced by layout.

Step 4 **Next Required Action → Verification Required** uses the same Violet
status/ordered-list/navigation pattern already approved for review expiry
and pending approval. Its short checklist is conditionally derived from
committed successor acceptance and provider transfer projections, with
requester versus independent Platform Admin wording retained. Ineligible
actions remain excluded; the existing Step 3 HTMX navigation is not an
approval or Release endpoint. Provider recovery, approval expiry, TLS failure
and review expiry retain higher priority; admission and human UAT stay HOLD.

## Tenant Adoption vs Allocation Cutover — Current Authority (#777, #762, #769, #771, #773, #2481)

**Authority precedence:** #777's human-approved **Managed-on-Adopt** contract governs
new eligible adoption. #762/#768/#769 describe **legacy committed
Adopted / Observed** records and their explicit subsequent allocation
cutover; their original observation-first adoption language is historical,
**not an alternate automatic fallback for new adoption**. The current
Native/Capsule cutover services decide eligibility, not the label of a
Resource Profile or an available CRD field.

Two independently governed ownership dimensions must never be conflated:
- **Tenant/Namespace lifecycle:** a Namespace can remain
  `ownership_status=adopted` after KAORI manages its quota.
- **Allocation control:** `adopted_observed` means recorded provider evidence
  without KAORI mutation authority; `kaori_managed` requires successful
  admitted authoritative write + provider read-back; **Drifted** requires an
  explicit reconciliation decision, never an automatic mutation on Sync.

| Entry condition | Appropriate workflow | Provider authority / outcome |
| --- | --- | --- |
| New Discovered Native or Capsule with admitted, unambiguous allocation | Review Adoption → **Adopt & Manage** | Recheck live authority/UID/resourceVersion, capacity + ownership; equivalent provider write/read-back before allocation becomes Managed |
| Previously committed legacy **Adopted / Observed** Native Namespace | **Adopted Native Governance Cutover** | Supported Native ResourceQuota / Container LimitRange; Namespace lifecycle stays adopted |
| Previously committed legacy **Adopted / Observed** Capsule Tenant CR quota | **Capsule Tenant Quota Governance** (#773) | `Tenant.spec.resourceQuotas` with admitted `tenant_resource_quotas`; write only authoritative Tenant CR |
| Previously committed legacy **Adopted / Observed** Capsule shared quota | **Capsule Shared Allocation Governance** (#771) | Exactly one admitted `GlobalResourceQuota` with `shared_global_quota`; do not multiply shared quota by Namespace |
| Allocation already **KAORI Managed** | Managed Allocation Change, or explicit Drift & Reconcile | No repeated cutover; Sync observes only |
| Capsule owner with only namespaced Native ResourceQuota, absent/unhealthy/multiple/unsupported Capsule quota authority | **Control Unavailable**; preserve evidence and stop | No Capsule-managed adoption, no Native cutover bypass, no automatic observed-only adoption |

**Capsule authority is capability-first, source-specific.** The Tenant CR observation key is `capsule_tenant_resource_quotas` and the distinct shared quota key is `capsule_global_resource_quota`. Serving the
`Tenant.spec.resourceQuotas` schema is necessary but not sufficient.
Tenant CR quotas and GlobalResourceQuota have **separate** governance
services/commit paths; selecting the wrong quota path must be disabled
rather than substituted. A namespaced ResourceQuota label referencing a
Capsule Tenant proves correlation, not a supported Tenant/GRQ write path.
The observed `kaori-adopt-lab-v2` has no Tenant CR quota and no
GlobalResourceQuota but has a namespaced ResourceQuota: correctly blocked
as `native_namespaced`. Never create competing provider quota solely
to pass UAT.

**Failure semantics:** preflight is read-only; mutation-capable submit
revalidates fresh provider and admission evidence. A failed/unverified
provider attempt must not be represented as a completed cutover.
Explicit legacy cutover and new managed adoption both require provider
read-back before committing managed allocation. Provider drift remains
committed observed evidence until separately accepted/reapplied by an
authorized operator. The current service contracts and tests, not older
issue text, are authoritative when wording differs. No new mode or
permission is added by this documentation clarification.

## Capsule Managed Adoption Authority Preflight (#2463, 2026-10-18)

The approved **Adopt & Manage** path is a mutation-capable governance cutover,
not a read-only adoption. Capsule quota ownership must be proven before that
action is offered. Capability-first preflight uses the same predicate as
commit-time validation: one supported Capsule Tenant.spec.resourceQuotas or
GlobalResourceQuota source with matching available served capability and no
unresolved authoritative dimension conflict; genuinely absent quota may
retain the existing empty-source behavior. A Native namespaced quota under
Capsule management does not grant KAORI a Capsule source-write path, even if
its observation would otherwise report `observed`.

**Fail-closed flow:** Discovery → selected live deep preflight → classify
authority + capability + unsupported/ambiguous fields → show
**Control Unavailable** and a disabled managed-adoption submit for
unadmitted paths → fresh submit-side identity and authority recheck →
existing provider-specific cutover/read-back only when admitted.
The UI exposes blockers and technical evidence without offering
implicit provider writes. The submit service validates before allocating
KAORI governance rows; provider remains authoritative and there is no
Native fallback or silent observed-only mode. Failure of the server-side
predicate is not approval to retry; user must inspect actual provider
evidence and repeat a fresh preflight. Protected approval/CSRF/HTMX
mechanics and existing committed-read surfaces are unchanged.

## Tenant Release Step 3 — structured independent approval evidence (#1089, #2401; current presentation authority)

Human DevContainer review of Release wizard **Step 3: Independent approval and handoff**
found an acknowledged plan, external reference, long SHA-256, and Platform Admin
verification stacked as nearly equal paragraphs. The canonical Step 3 now
has a compact KAORI icon/title, a separation-of-duties note, and distinct
committed evidence regions:

- **Active handoff plan** now uses two adjacent responsive evidence cards (#2401):
  the read-only locked-plan review state and the planned successor owner /
  change record. Cards stack on narrow screens. The same pending/acknowledged/
  expired conditionals and original-requester fresh preflight requirement are
  preserved; neither card claims provider ownership has transferred.
- The exact **Plan SHA-256** remains visible in a wrap-safe monospace value
  directly beneath the plan; it is not ellipsized or substituted with a
  status chip. A short acknowledgement line makes the outstanding external
  owner acceptance, provider handoff and verified read-back explicit.
- **External successor evidence** is a separate compact neutral panel
  containing the original `External Reference Unverified` semantic warning,
  full reference and an explicit boundary: this external evidence claim is
  *not* additional approval, verified consent or provider ownership transfer.
- For eligible distinct authorized Platform Admin operators, the exact
  existing verification form is placed in a focused, labeled panel with a
  concise registered X.509 connection/permission explanation, the original
  required explicit checkbox authorization (plan SHA and exact resources),
  and the unchanged submit action.

For the **eligible Prepare Handoff** state, Step 3 reuses Step 4's
responsive **3:2 two-panel** presentation: a compact successor/change-reference
form on the left and a read-only **Approval boundaries** sequence on the
right. The sequence explains independent reviewer separation, external
provider consent/ownership authority, and the separate committed checks
before Release. At smaller breakpoints the panels stack; the existing
desktop-bounded/mobile-full-width form and button contract from #2390
remains unchanged. It is guidance, not a recorded review, live provider
status, or extra approval control. Existing locked, expired, blocked and
provider recovery states keep their previously approved presentation.

The same committed plan/approval/claim attributes, requester/reviewer
separation, endpoint actions, one-active-plan policy, successor identity
checks, CSRF/HTMX, approval/dry-run/executor/read-back/restart conditionals
and global toast remain authoritative. No new readiness algorithm,
provider-side operation, identity mapping, credential or approval engine.
The outer Release wizard continues to own one active URL-scoped step, while
this content stays committed-state driven. All **10 Step 3 conditional forms**
and **14 Tenant forms** remain present in source.

**Step 4 Approval Pending — compact numbered list (#2401 follow-up):**
Within the unchanged `not native_cycle.approval_complete` branch of
**Next Required Action**, replace the horizontal 3-card approval path with
the existing Step 3 `Approval boundaries` vertical ordered-list pattern:
numbered Violet tokens, divided shared surface, title, and one concise
sentence per action. Row meanings remain independent-review approval,
external successor acceptance by an authorized Platform Admin, and later
provider handoff/read-back before Release. These are guidance milestones
only, not committed approvals. The single-sentence role-separation status
and original Step 3 HTMX CTA remain; no new backend, provider calls, forms,
permissions, or implicit admission. Preserve mobile wrapping, keyboard,
light/dark and existing recovery/expiry precedence. Source contract tests
were updated; runtime and browser UAT are pending under CI/CD HOLD.

**Release Step 4 Review Expired action content (#2401 follow-up; presentation only):**
The `native_cycle.review_expired` conditional now displays the Title Case
**Next Required Action** header and a balanced Violet action region with
current recorded **Review Expired** status, the need for fresh authoritative
provider preflight, three sequential read-only instructions and its
original Step 1 HTMX link. The instructions explicitly require inspection
of refreshed committed identities, dependencies and blockers, then
revalidation of exact plan/independent approval freshness. They are
guidance, **not** automatic provider refresh, successor consent,
re-review, restarts or Release authorization. Existing priority order
(provider handoff recovery → approval expired → review expired →
approval pending → TLS → other verification) and all original permission,
CSRF, navigation and action contracts remain unchanged. Source contracts
are updated; runtime and Dev Container visual acceptance are pending.

**Release Governance contextual guidance / Step 4 pending action (#2401):**
The shared `components/info_tip.html` provides pointer, keyboard and touch
guidance alongside the permanent Release Governance heading. It distinguishes
committed review, independently approved plan, external successor consent,
provider handoff/read-back and authorized finalization. The Step 1 condition
cards use shortened operator summaries for Namespace provider mutation and
KAORI-linked allocation ownership; the exact original provider/governance
reason stays accessible under **Exact recorded reason** and remains unchanged
in committed evidence. In Step 4 only the `approval_complete == false` action
branch gains a structured status and three not-yet-complete gates (review,
successor acceptance, provider verification), followed by the same HTMX
navigation CTA. Expiry, provider recovery, TLS and other branches are untouched.
No approval evidence, provider mutation or Release state is synthesized.

This supersedes *only* Step 3 presentation from the earlier #1075/#1077
four-step wizard, not its admission/security rules. Browser Visual QA for
pending/expired/acknowledged, unverified/verified reference, native/Capsule,
different requester/reviewer, light/dark, mobile and long digest is pending.
CI/CD, Developer Check, Full Admission, staging UAT, main promotion and
deployment remain HOLD until explicitly authorized.

## Managed allocation blocker contract — preflight vs handoff admission (#1085 corrective)

A Resource Profile-linked adopted Namespace produces a **known, explicit
handoff obligation** in `release_preflight._release_blockers`, not an
unresolved identity failure. The independent review/restart admission
function `release_handoff_approval._can_confirm_plan` must recognize
that **exact current managed-allocation message** alongside previously
recognized handoff obligations. In the #1085 copy refinement, this message
was lengthened without updating `_EXPECTED_HANDOFF_FRAGMENTS`, causing a
correctly classified preflight snapshot to fail restart with the generic
`Unresolved provider, identity or governance blockers prevent approval`
error. The corrective follow-up synchronizes the narrow known-text
recognition with the generated preflight wording and adds a test passing
the actual `_release_blockers` output into `_can_confirm_plan`.

This does **not** permit missing/changed provider UID or resourceVersion,
ambiguous or foreign ownership, active Tenant dependencies, unknown
provenance, malformed inventory or already-read-back partial handoff.
Independent approval, fresh authoritative provider evidence, exact plan
SHA/fingerprint and requester-only expired-plan restart remain compulsory.
The provider remains authoritative; no provider mutation, automatic
acceptance or Release occurs. Any future changes to handoff blocker copy
must update its admission classification and coupled regression tests in
the same issue/PR.

## Capsule Release independently verified successor acceptance (#1228; no provider transfer)

Step 3 of the existing Release Governance wizard supports **explicit Capsule
Platform Admin consent** separately from Native provider acceptance. After
an independently acknowledged exact Release plan, an authorized, non-requesting
Platform Admin confirms the handoff scope. KAORI uses the registered cluster's
verified-TLS Kubernetes **X.509** identity through SelfSubjectReview and
SelfSubjectAccessReview `get`/`patch` on the cluster-scoped
`capsule.clastix.io/tenants` object and each governed Namespace. Capsule
Tenant CRs are not namespace-scoped. All scoped resources require complete
UID/resourceVersion, Capsule provider ownership and the Capsule spec SHA-256
from #1227; changed spec, plan, generation or independent review **fails
closed**. Application authorization uses the existing Tenant, Integrations
and Cluster Manage permissions, not provider-label identity or a new token.

The separate append-only `kubernetes_tenant_release_capsule_successor_acceptance`
AuditEvent stores the explicit actor, verified X.509 identity, scoped
authorization evidence, plan SHA, fingerprint and bounded provider identities.
Routine Tenant UI reads committed evidence, with no provider request on GET.
This acceptance sets `consent_verified=true`, but **always**
`provider_mutation_performed=false`, `provider_handoff_verified=false` and
`release_authorized=false`. It is **not** Capsule handoff or a Released
lifecycle transition. The provider-specific guarded dry-run/executor,
read-back, finalizer and real Kubernetes UAT remain separate workstreams
#1229–#1231. Source-only DevContainer integration; CI/CD, admission gates,
provider mutations and deployment remain on HOLD.

## Capsule Release authoritative spec scope digest (#1227; preflight-only)

The existing `release_handoff_inventory.capsule_tenant_handoff_evidence`
records the authoritative Capsule Tenant **UID/resourceVersion**, ownership
classification and provider-controlled quota presence. It now additionally
computes a **bounded canonical SHA-256 of the complete live Capsule Tenant
spec**. This digest is stored as `capsule_spec_sha256` in the same committed
`handoff_components` entry and participates in the existing
`handoff_fingerprint` / exact independent handoff plan scope. The digest
covers quota, LimitRange, Namespace options, owner, additional RoleBindings,
RBAC rules and future provider spec dimensions without copying their raw
contents into KAORI. Canonical JSON preserves object-order independence;
malformed, non-JSON or oversized specs **fail closed**. The digest is a
correlation/integrity receipt, **not** authority to manage or patch Capsule
fields.

The existing Release **Provider IDs** disclosure displays the Capsule
spec digest when newer committed preflight evidence contains it; older
records remain readable without a fabricated digest. The existing blocker
text and provider mutation/managed Resource Profile gates, X.509, actor
separation, live UID/RV guards and handoff consent requirements remain
unchanged. This task does **not** implement successor acceptance, Capsule
PATCH/executor, verified read-back, Released finalizer or UAT. Those are
separate children #1228–#1231 under #991, and the present DevContainer
review is **source-only with CI/CD and Kubernetes mutation HOLD**.

## Tenant Release Step 2 — compact two-line resource summaries (#1085; latest detail UI authority)

Human DevContainer review of the #1085 initial evidence-first design found
large unused vertical space in the per-resource layout: separate type/name,
ownership/manager and identifier-toggle rows were repeated for each resource.
The current Step 2 keeps a **single compact list** with **one native
`details/summary` per resource**. Closed rows are approximately two lines:
resource Kind/Name and status on the first; Namespace when distinct,
Ownership and Manager (all literal committed evidence) on the second.
The status and **Provider IDs** cue remain visible, and the complete row
is keyboard-operable with hover/focus. Opening the native disclosure reveals
exact Namespace, provider UID and resourceVersion at full width. This
eliminates the third standalone disclosure row and redundant per-resource
horizontal divider, without hiding or truncating immutable evidence.

The source-derived total resource count is folded into the section subtitle;
the original committed handoff-required count remains the semantic status
badge. No second full-width metric band. The one list has compact padding,
mobile wraps without horizontal scroll, and no internal scrollbar. The
original Handoff Required / Ownership Conflict / Observed classes remain
unchanged. The note that display does not authorize transfer or deletion,
the unreviewed/empty states, and all Release governance safeguards are
preserved. This is a layout-only successor to the earlier #1085
"evidence-first provider handoff scope" arrangement, not a second handoff
model. It does not change provider authority, server-side decisions,
preflight blocker wording, provider requests, CSRF/HTMX or modal behavior.

DevContainer light/dark, mobile and expanded-identifier human visual review
is still pending; no CI/CD, Developer Check, Full Admission, staging UAT,
promotion or deployment is authorized.

## Tenant Release Step 2 — evidence-first provider handoff scope (#1085; historical first pass)

DevContainer feedback identified dense, stacked unstructured text in the
four-step Native/Capsule Release wizard **Provider handoff scope**. The
current canonical Step 2 is a **single structured read-only resource list**
within the existing Release panel (not separate cards or an additional tab):
one short title/description, committed handoff-required count, committed
recorded-resource count, then separated resource rows. Each row leads with a
type icon (Namespace / ResourceQuota / LimitRange / CapsuleTenant), exact
resource kind/name, and the preflight's original **Handoff Required /
Ownership Conflict / Observed** semantic status. Ownership marker correlation
and provider manager are distinct, labeled facts, not a sentence blob.

An accessible native **Provider identifiers** disclosure on each resource
shows the exact committed Namespace, provider UID and resourceVersion without
truncation. The initial list is scan-friendly; keyboard users can expand
each item for immutable identity evidence. Long values wrap, no extra
horizontal scrolling or nested list scrollbar, and the original no-review /
empty-evidence states remain distinct. `handoff_components` and
`handoff_required_count` come **only** from the recorded Release preflight;
no separate provider API, client state, or inferred readiness. The scope
retains an explicit read-only handoff boundary: observing provider objects
does not approve, transfer, or delete resources. Original wizard navigation,
11 Release POST forms (14 Tenant governance forms overall), independent
approval, UID/RV guards and live provider read-back remain unchanged.

The existing managed-allocation preflight blocker is expanded to explain
that an adopted Namespace linked to a KAORI Resource Profile still requires
**explicit independently approved allocation handoff with authoritative
provider read-back**; KAORI cannot silently abandon the allocation or
delete provider resources. This is wording only: the same
`resource_profile_id is not None` guard still blocks Release, and no
handoff policy/admission calculation changed.

Focused contract/unit tests are authored for field retention, semantic
statuses, failure/empty branches, exact blocker content and preservation
of all forms. Runtime tests, DevContainer browser Visual QA, Developer
Check, CI/CD/Full Admission, staging UAT, main promotion and deployment
are HOLD pending explicit authorization.

## Capsule Release dependency guidance and readable conditions (#1204)

A Capsule Tenant's **Release preflight** can record active Access Grants,
Memberships, KAORI-mutated allocations, managed Resource Profiles and
external Capsule owner/RBAC handoff obligations simultaneously. The
`release_handoff_approval._can_confirm_plan` guard requires **all** committed
Tenant dependency counts (credentials, Access Grants, Memberships, enabled
Groups, managed resources, advanced capabilities, domain reservations and
exposure policies) to be zero. An independent reviewer who has correct
permissions still cannot acknowledge a plan if active dependencies remain:
for example, the 2026-10-11 `kaori-demo` screenshot records **1 Access
Grant and 1 Membership**, either sufficient to block approval. The server
re-runs current provider preflight on every approval attempt; a blocked
acknowledgment does not mutate the provider or complete Release.

Step 1 presents **short display-only condition titles and operator actions**
for known recorded blocker patterns. The **verbatim original blocker** is
retained in committed AuditEvent evidence and exposed via a native,
keyboard-accessible `Exact recorded reason` disclosure on each responsive
condition. Unrecognized reasons remain visible unchanged, never implicitly
trusted, ignored, or reclassified as eligible. A concise dependency summary
describes the gate without equating an active dependency with permission to
delete a Kubernetes/Capsule resource.

Step 3 differentiates **independent reviewer eligibility** from **handoff
approval eligibility** using existing committed dependency counts for
read-only guidance; active dependencies prompt resolution via existing
governance workflows followed by a fresh `Review Release`. Neither form
gating, existing CSRF/HTMX routes, ownership handoff/read-back checks nor
server-side approval policy is changed. This is a DevContainer source
presentation refinement, not completed Capsule Release UAT or an approved
provider mutation.

## Tenant Release wizard responsive action density (#2390; review presentation)

The four-stage Release Governance wizard retains full-width **committed evidence**
and provider inventory: Step 1 readiness status and recorded blockers, Step 2
Native/Capsule resource list and exact UID/resourceVersion disclosures, Step 3
approval/read-back evidence, and Step 4 verification checkpoints remain
unconstrained. Provider authority and immutable audit facts are unchanged.

Only **action forms** are width-constrained on desktop using existing KAORI
responsive utilities: the Successor owner / Change record and external
reference inputs use `max-w-xl`; confirmation/recovery/handoff/finalization
forms use `max-w-2xl`. Their inputs fill the constrained form, while CTA
buttons are `w-full` on phones and `sm:w-auto` on larger screens. The
Step 4 flex-column Release Governance fallback also aligns its button to
the start rather than stretching it. The Step 1 Review Release CTA already
uses responsive sizing, and Step 2 remains strictly read-only. No new CSS
component, form field, permission branch, POST route, CSRF/HTMX behavior,
confirmation requirement, provider mutation or step navigation was introduced.

Local review acceptance requires desktop/mobile and light/dark visual checks
covering clear/blocked preflight, authorized requester/reviewer states,
Native/Capsule, expired plans, recovery and verified finalization. This
layout-only work is on `kaori/review/staging-uat` path pending human
DevContainer review; official Developer Check, Full Admission, staging/main,
deployment and release remain HOLD until specifically authorized.

## Release Review Scope and step prerequisites (#1144; current visual refinement)

The four-step Tenant Release wizard keeps its original one-active-step HTMX/URL navigation, fail-closed backend guards, exact Review Release POST and committed provider evidence. Step 1 now uses a single full-width status/action/coverage surface: the recorded preflight status and exact blocker count, one prominent Review Release button, and three compact review dimensions (provider resources, allocation ownership, governance dependencies). Exact source blocker messages are retained in the native accessible `View recorded conditions` disclosure; no-clear-blockers does not assert provider acceptance.

Steps 2–4 reuse one read-only Violet/neutral **inline guidance note** (same icon, spacing, title and typography), with conditional step-specific content for not-reviewed, reviewed-without-handoff, missing Integrations Manage, and finalization-blocked cases. The note is not a toast, approval, alert severity, or executable control; it does not replace committed provider inventory, review results, independent approval, read-back or any explicit consent. The existing Release endpoint/permissions, HTMX forms, audit, 17 total Tenant forms/CSRF and all provider mutations remain unchanged.

Source-only regression covers the unified scope, common note, original authoritative branches, unchanged form counts and Jinja parse on later execution. Local DevContainer visual/functional human acceptance pending (desktop/mobile, light/dark, recorded/no-record, blocked/clear). CI/CD, runtime gates, Full Admission, provider UAT, staging/main promotion and deployment remain HOLD until specifically authorized.

## Tenant Governance Scope and permanent Release wizard (#1077; historical Release/authority foundation; scope presentation superseded by #1079)

Human Visual Review of #1075 rejected the generic four-KPI dashboard, the
expandable Release shell with numeric badge 2, and the dense Review Scope
wall of blocker text. This workstream **supersedes presentation only**;
provider-side handoff, independent review, Release authorizations, and
committed audit evidence remain governed by the existing services.

**Governance Scope** now groups existing committed dimensions into two
responsive KAORI cards: **Resource Coverage** (active Namespace count,
Environment count) and **Governance Authority** (reconciliation authority,
lifecycle). There are no duplicated or fabricated provider live metrics.
The unchanged authority contract (“KAORI presents committed governance
evidence; Kubernetes or Capsule remains authoritative for provider
resources.”) is shown **once** inside a neutral, accessible
**Authority Boundary** information box below Tenant Overview, with its
original historical Namespace lineage note preserved separately.

**Release Governance** is now a regular always-visible section, using
the established icon treatment instead of the numeric badge and eliminating
the outer `details/summary` wrapper. All four numbered URL-addressable
wizard steps and 11 original Release form authorities remain. Other
provider-specific governance sections retain their permission-scoped,
keyboard-accessible expandables. Step navigation preserves normal
URL/history and active stage after POST without changing backend gates.

**Review Scope** is a concise evidence-first view: a prominent committed
readiness/count, the unchanged Review Release action, and a compact
review-coverage summary. When blockers exist, an accessible **View recorded
conditions** disclosure exposes **all original exact blocker messages**
with their committed count; evidence is not discarded, summarized as
fabricated severity, or hidden from users who explicitly inspect it.
Absence of blockers is never represented as approval or permission to
execute Release.

Two lengthy explanatory footnotes are removed from the UI at the user's
request. Their underlying architecture requirements **remain mandatory**:
navigation never grants approval, a reference is not external consent,
independent review must be valid, X.509 Platform Admin authority and
provider read-back remain required. Normal HTMX Operational Toast,
CSRF/authorization, state recovery and all 14 existing form endpoints
are unchanged. Runtime tests, browser Visual QA (responsive/light/dark),
Developer Check, Full Admission and UAT remain HOLD.

## Tenant Overview + governed Release wizard (#1075; historical #1075 architecture, updated by #1077)

Follow-up human visual review of the approved #1073 two-column Violet
Hero/accordion requested three adjustments: shorter Hero purpose text, a
complete Tenant Overview redesign with **no Quick Links**, and Release
Governance as a **real four-step wizard**, analogous to KAORI's controlled
resource-generation procedures rather than an expanded list of 11 forms.

The Hero remains the existing `page_hero.context_card()` composition; its
supporting copy is now **“Manage Tenant governance and lifecycle.”** No new
Hero taxonomy or provider readiness panel was added.

The former **Identity & Origin** and **Governance State** Overview surfaces
present canonical Tenant ID, Cluster, Provider, Generation, registered date,
description, Ownership, Lifecycle, Reconciliation authority, updated date
and historical Namespace lineage where applicable. Long values wrap,
missing description uses the standard neutral empty text, and all values
come from KAORI committed evidence. **Quick Links are removed.** Four small
summary cards outside the Overview retain their existing dashboard roles.

**Release wizard — one active step at a time:** four bookmarked
`release_step=` URLs and a semantic Previous/Next navigation replace the
inner `tenant-release-workflow-details` disclosure. The outer governed
Release section remains permission/lifecycle-gated. The named stages are
**Review Scope** (committed preflight and blockers), **Provider Scope**
(UID/RV inventory and provider preservation), **Approval & Handoff**
(existing handoff plan, separate reviewer, explicit Platform Admin
acceptance, guarded dry-run/execution/readback), and **Verify & Finalize**
(current readiness, required verified transfer and exact Release forms).
The step navigator is presentation only: following Next is **never**
approval, preflight success, transfer consent or completion evidence.
Each existing service performs its original fail-closed checks.

The `_tenant_detail_context()` projector accepts only the four known
step keys; unknown values resolve to `scope`. It builds exact
`tenant_release_step_urls` from the established Tenant GET route,
preserving filtered Registry state and a Release anchor. Eleven Release
forms carry hidden `tenant_release_step` alongside existing
`tenant_detail_section`, exact Tenant ID, CSRF, plan SHA and registry
context. The standard HTMX POST swaps the same Hero + selected step with
global OOB Operational Toast; an ordinary POST redirect also restores the
selected step. The Work Inbox independent reviewer deep link goes directly
to `release_step=approval`. After a lifecycle transition the normal
service-controlled Release/Handback eligibility still takes precedence
over visual wizard state.

No new provider mutations, auth, RBAC grants, foreign metadata changes,
Release shortcut, duplicate endpoint or separate wizard state machine.
This supersedes only the **Overview layout and Release disclosure**
of #1073, not its canonical Hero or existing governance architecture.
Desktop/mobile/light/dark Visual QA, focused pytest and relevant quality
gates still require Developer Check and Human Acceptance. CI/CD, staging
and deployment remain HOLD until explicitly authorized.

## Tenant Details approved KAORI Hero/context and accordion design (#1073; superseded only for Overview/Release layout by #1075)

The latest user-provided KAORI reference was a **Delete ConfigMap** two-column
violet Hero. Only its **composition** is authoritative: the existing
`page_hero.shell_classes()` + `layout_classes()` + `intro()` on the left
and `page_hero.context_card()` on the right with title, status, two metric
tiles and a full-width bottom action. The operator rejected mockups that
copied Delete ConfigMap content or invented non-standard Hero panels.

The current Tenant Details implementation reuses those **shared macros**
without new CSS/hero variants. Left: committed Tenant identity, governance
description, cluster, provider, generation. Right: contextual **Tenant
Details / Governed Resource State** card, actual lifecycle status,
committed Active Namespace count and Ownership, and one **Back to Registry**
action. No fabricated example timestamps, fake provider status or unsupported
access authority. Tenant created/updated timestamps, when present, use the
actual model fields and stay in the overview detail rather than the Hero.

Below the Hero are **four responsive compact committed summary cards**
(Active Namespaces, Environments, Reconciliation Authority, Lifecycle) and
a clear **two-column Tenant Overview** (identity/history facts beside
description and links to existing KAORI pages). All long workflows remain
on this one routable Tenant page, but present as accessible native
`details/summary` governance sections: **Release Governance**, Native
Platform Admin Handback/Re-adopt, Provider Authority and Lifecycle.
Capsule Namespace attachment belongs to Tenant Discovery/Adoption, not to
this management governance page. Inapplicable mutation sections stay absent because
the original permissions and provider/lifecycle checks remain authoritative.

Release shows a **four-stage stepper preview by default**. Its full
independent review, provider inventory and finalizer forms are in a
secondary on-demand native disclosure, avoiding an immediate wall of
nested forms and tiny text. Work Inbox deep-links to the expanded
Release workflow, and a committed `tenant_detail_section` form field
preserves the currently operated accordion after all 14 POSTs. The
server validates the section against current KAORI actor permissions,
provider and Tenant lifecycle; Released transitions fall forward to
Handback where eligible, otherwise to Provider. The regular HTMX swap
refreshes the Hero/accordion and global OOB Operational Toast without
placing the workspace inside a modal. Only the existing short destructive
Decommission confirmation remains modal.

No new provider requests on a normal GET, new permissions, credential
fields, ResourceQuota/LimitRange mutations, or release shortcuts. All
approved #1047-#1049 security/governance boundaries remain in services.
Previous #1071/#1069/#1067/#1065 layouts are historical, not active design
authority. Browser responsive/light-dark Visual QA, tests, Developer Check,
Full Admission and Kubernetes UAT must be accepted separately; CI/CD and
deployment stay HOLD.

## Tenant Management single-page UX correction (#1071; superseded by #1073)

The previous Native Tenant detail layout iterated through a relocated dialog
(#1065), a large custom Hero / sticky sidebar / four-KPI dashboard (#1067),
and a secondary content-tab application (#1069). The user rejected all three
presentations in live Visual Review. **Those are superseded UI decisions**;
preserve their service/governance work but do not copy their layout patterns.

**Current approved direction: one normal scrollable KAORI Tenant Management
detail page**, not another dashboard or application. Apply the same shared
Violet Hero macros and page spacing as other current Tenant pages:
`page_hero.shell_classes()`, `layout_classes()`,
`content_classes()`, `intro()`, `title_classes()`,
`description_classes()`, `persistent_metadata()`, and
`primary_action_classes()`. There are no local Hero height/padding
overrides. The HTMX loading indicator is positioned absolutely (out of normal
document flow): its default opacity-hidden state previously consumed line
height plus layout spacing, creating a false vertical gap between the primary
capability navigation and the Tenant Hero. Only **Back to filtered Registry** is an action in the Hero.
The main capability navigation stays **Tenants** active and global navbar
breadcrumb ends at the committed Tenant name.

Following the Hero, present one concise **Tenant Overview** with managed
Namespace/environment scope, Cluster, ownership and reconciliation
authority. Avoid duplicating Tenant name/lifecycle into KPI grids.
The normal page then presents clear full-width sections, in lifecycle
order: **Release Governance** (only where eligible), **Platform Admin
Handback/Re-adopt** (only Released Native where eligible), **Provider Authority**, and **Lifecycle Actions**. Attach a previously
ungoverned Capsule Namespace only from **Tenant Discovery → Review Attachment**
under the already-governed Capsule Tenant, using its existing provider-
verified UID/resourceVersion preflight and explicit destination Environment. Every section has a clear heading, concise
description, authoritative evidence and only its legitimate actions.
Release has a single full-width bordered panel with four divided phases:
**01 Preflight and blockers → 02 Provider handoff scope → 03 Independent
approval and handoff → 04 Verify and finalize**, with readable persistent
blocker lists and full inventory (no internal list scrollbar or nested
phase cards). Avoid repeated numbering badges.

The original 14 CSRF/HTMX forms are retained as-is. The outer
`#tenant-management-detail` HTMX fragment includes Hero plus content,
so lifecycle updates refresh committed state and the global OOB
Operational Toast stays visible without a modal top layer. Normal
POST redirects to the same detail page. The independent-review Work
Inbox link uses the page's `#tenant-release-governance` anchor rather
than a removed `?view=release` tab. Only existing short Decommission
confirmation remains modal.

No service, provider mutation, RBAC, independent approval, evidence,
history, capacity, or reconciliation authority changes were introduced.
Project status remains review-only: pytest, Developer Check, Full Admission,
browser Visual QA (desktop/mobile light/dark), Kubernetes UAT, staging/main
promotion and deployment are HOLD until explicitly authorized.

## Tenant Registry → dedicated Tenant Management detail (#1065, supersedes #1022 presentation)

Tenant Registry retains the canonical committed-state summary table, Cluster /
Environment / Lifecycle / Search filters, default pagination 5 and a single
right-aligned **Manage/View** link per Tenant. Complex governance actions now
live at `/kubernetes/tenant/tenants/<tenant-id>/manage`, an independent,
permission-scoped full page based on the *same exact committed Registry row*
projection, unconstrained by Registry filtering or pagination. Missing Tenant
IDs return 404. There is no inline expansion below the table (rejected in
#1039/#1041), and there is no long-lived native management dialog overlay.

The detail page now follows the shared Tenant Violet Hero and natural
single-page flow (#1071 is the current presentation authority). A concise
Tenant Overview precedes the conditional Release, Handback, Capsule
Attachment, Provider Authority and Lifecycle sections. No secondary
Content Tabs or sticky sidebar remain; existing forms still enforce their
service-side permissions and independent approval.
Existing service endpoints, two-actor plan authority, evidence read models,
provider inventory and destructive-operation rules are **unchanged**.
All 14 existing POST forms include `tenant_detail_id` and
bounded prefixed `registry_*` context for browser fallback and HTMX.
The rejected `tenant_detail_view` state has been removed.
`_tenant_section_redirect` renders the same dedicated detail partial for
HTMX POST and emits the **existing** OOB Operational Toast; normal POST
redirects back to the same Tenant detail. Because the everyday management
workflow is not an HTML `<dialog>`, its toast is no longer obscured by
the browser's modal top layer. The only retained modal is the approved
short-form destructive **Decommission confirmation**; it is removed with the
replaced detail fragment after the action. No custom toast z-index, new
provider mutations or alternative authorization engine were introduced.

The Platform Operations Work Inbox deep link for an independent
reviewer now opens this exact Tenant detail route with the
`#tenant-release-governance` anchor, not the deleted modal or tab state. Approval still requires a different
authorized actor, the same committed plan SHA and canonical backend checks.
The old native-dialog reopen logic remains a shared component for other
existing dialogs, but Tenant Registry does not opt in to it.

The **Release Governance** card presents an ordered, full-width workflow
instead of three controls that resemble interchangeable tabs. **Release
Readiness** remains first, with a standalone **Review Release** POST action,
latest committed review status and persistent multiline blocker evidence.
Three stable, numbered sections follow: **(1) Handoff Inventory**, whose
read-only provider objects are visible without an expanding toolbar;
**(2) Governed Handoff**, which displays the authorized successor/change
form and independently gated approval within a permanent full-width card;
and **(3) Independent Verification & Release**, which states the remaining
external ownership/read-back requirements and keeps the existing explicit
Release action conditional on authoritative preflight. Without a review or
handoff eligibility, the relevant section shows concise non-action guidance,
not an empty disclosure. The only nested disclosure retained within this
workflow is optional detailed Native dry-run evidence. Stable card boundaries
do not change position when the operator inspects handoff evidence or a form.

Lifecycle **Blocked** appears together with its Decommission warning panel
instead of as a detached badge. Capsule attachment still verifies authoritative
UID/resourceVersion and does not automatically grant RBAC. Release preflight
status and dependency blockers remain persistent inline evidence, never a
hover-only Info Tip. Governed Handoff keeps every prior permission, CSRF,
HTMX, plan fingerprint, independent actor, Native dry-run, provider read-back,
successor-reference and destructive Release guard. An internal acknowledgment,
unverified external reference or dry-run is **not** proof of a successor's
acceptance or authority to mark provider-mutated resources Released.
### One active Release handoff plan and reviewer authority (#1045)

One Adopted Ready Tenant has at most one currently actionable handoff plan.
Under the existing **Tenant row lock**, the Prepare service checks the latest
committed plan and independent approval before writing another AuditEvent:
**pending within the 15-minute window** blocks all duplicate prepares,
regardless of who submits the request; **acknowledged** blocks re-preparation
while external provider handoff is pending. It cannot silently turn the
independent reviewer into a new requester. A correctly formed **expired and
unacknowledged** plan may be renewed only by the **same original requester**
through a fresh canonical provider preflight. A different reviewer cannot
silently take over the expired request; a change of requester needs a separate
explicit reassignment workflow. Unexpected statuses, malformed or future
timestamp evidence fail closed. No new backend approval executor, bypass, automatic plan amendment or
privileged Super Admin exception is introduced. Restarting an acknowledged
handoff requires a separate governed authority/workstream, not this UI.

The Registry computes `release_handoff_preparation_state` using the exact
same service predicate as the backend. The **Prepare Handoff** form is shown
only when there is no plan, or when an expired/unacknowledged plan is
reopened by the original requester; a pending/acknowledged plan and other
operators facing an expired plan see the locked successor/change summary.
The independent reviewer sees
**Acknowledge as Independent Reviewer** only while the current plan is
pending and the viewer is a different actor with existing permissions.
A requester cannot approve their own plan and another authorized operator
cannot replace it by posting directly to the Prepare route. This retains
#1040 Work Inbox one-plan/first-wins resolution semantics.

The **External Reference Unverified** receipt is a non-authoritative claim
recorded after independent KAORI acknowledgment. It is **not** a second
independent approval and does not certify successor consent, provider handoff
or Release eligibility. The existing Native dry-run/read-back are likewise
limited evidence; a trusted external acceptance verification/executor remains
separately governed. The dedicated detail page places lifecycle status beside Tenant identity and
provides accessible Back to Registry links at both ends of the workspace. No Release/provider mutation
is introduced by these changes.

### Multi-approver Work Inbox projection (#1040)

The existing Platform Operations **Work Inbox** projects the *same* Tenant
Release handoff request for every currently active user with both
`tenant.manage` and `integrations.manage`, except the requesting operator.
It reads committed `kubernetes_tenant_release_handoff_plan` and
`kubernetes_tenant_release_handoff_approval` AuditEvents; it does not create
recipient-specific approvals or a second approval authority. Work items are
computed from approved KAORI state on Inbox read without provider calls,
database writes, notification fan-out, new tables or duplicate alert channels.
The latest plan per Tenant is authoritative; earlier committed plans are
**Superseded**. When the plan's 15-minute approval window expires, a pending
item becomes **Expired**, non-actionable. The Inbox's pending count includes
only current, eligible, unacknowledged requests.

One reviewer may open a deep link to the **dedicated Tenant Management page**
and acknowledge the current plan (subject to permission, distinct actor,
fresh canonical provider read, fingerprint, and locked duplicate-check).
After the committed approval event, the winning reviewer sees **Approved**,
and the other eligible reviewers see **Resolved by another reviewer**. This
is not an expiration or multiple approval votes. A dismissed/marked-read
notification cannot approve or reject a plan; Work Inbox approval items are
separate from mark-as-read notifications. Existing per-user Work Inbox badge
and panel show committed request counts after refresh. The UI does not choose
an approver by name, bypass a role revocation, or treat internal approval as
external provider handoff/ownership acceptance. The approver's task deep link to `/kubernetes/tenant/tenants/<id>/manage`
resolves one exact committed Tenant, independent of pagination; all mutation
routes still independently enforce permissions and provider authority.

The Inbox uses a bounded recent committed plan history for a responsive
view; it does not replace AuditEvent as the full retention/audit history.
If a future workflow requires explicit assignee, rejection, escalation,
SLA routing, persisted recipient delivery receipts or push notifications,
those are separately governed workflow capabilities, not assumptions made
by this approval read model.

For a plan awaiting independent approval, the requesting operator sees
**Awaiting Independent Approver** and cannot approve their own plan, even when
Super Admin. Any **different authenticated KAORI user** with both
`tenant.manage` and `integrations.manage` may open **Tenant Registry →
Manage → Release Governance → Governed Handoff** and acknowledge the current
plan after inspecting the evidence; an account is not assigned as approver by
the UI or implicitly selected from users. The backend enforces actor inequality,
plan fingerprint, freshness and permission. If future policy needs a named
approver assignment, that is a distinct governance authority/workstream and
must be approved separately. Internal acknowledgment is not verified external
successor acceptance or provider ownership transfer.

Decommission remains separate and uses only the existing confirmation modal.
The main Tenant detail workflow never requires a browser top-layer overlay.

This is a **presentation/navigation change only**. It adds one read-only
Tenant detail GET, redirects existing POST feedback to its HTMX partial,
and updates Work Inbox navigation. Existing mutation endpoints, permissions,
committed-evidence contracts, resource/Release decisions and provider behavior
are unchanged. Table styles reuse `components/table.html`. DevContainer
review must verify mobile/light/dark, keyboard navigation, browser back,
committed blockers, OOB toast, independent reviewer, Decommission confirmation
and 5+ Tenant pagination. Developer Check, Full Admission and live-provider
UAT remain separate HOLD gates.


## Discovery adoption destination UX (#983)

Native Kubernetes Discovery Adoption Preflight offers two distinct destination
modes when eligible existing Tenant Environments are available:

- **Create a new KAORI Tenant** (default): the operator supplies Tenant Name
  and Environment; KAORI creates an Adopted Tenant with an initial managed
  Namespace allocation baseline after its existing provider safety checks.
- **Attach to an existing KAORI Tenant**: the operator chooses an eligible
  existing Tenant Environment. The UI hides and disables the new-Tenant name
  and environment controls, displays selected destination Tenant/Environment
  as read-only committed context, and keeps the observed Kubernetes Namespace
  name unchanged. The resulting operation is **Namespace Attached · Managed
  Allocation**; it must not create or rename a Tenant or automatically expand
  Tenant Access Grants.

The existing Adoption modal controller owns the destination change behavior
and reinitializes it after HTMX preflight replacement. The Discovery Review
trigger targets the HTMX-owned `#tenant-adoption-preflight-slot`, and the
controller resolves the actual swap target from the HTMX event detail or DOM
event target. Both the successful and provider-revalidation-error HTML fragments are
rendered **visible by default** when inserted into the HTMX-owned slot; their
visibility does not depend on post-swap callbacks, JavaScript timing or browser
caching. The existing delegated controller enhances focus and document scroll
locking once per response via swap/settle/request events, while preserving
close/ESC behavior. Failed preflight loads surface a concise, accessible
**Adoption Review Unavailable** operational warning with a safe retry or
permission action and confirmation that no Adoption was performed. Neither view
submits Adoption automatically. HTTP status, internal endpoint names, browser
debug instructions and server log locations are not shown in the normal UI;
support personnel can inspect the browser Network response and corresponding
server logs when troubleshooting. Raw HTML response bodies and Kubernetes
secrets must never be echoed into the UI. A failed preflight request cannot
be fixed by changing modal layout. In particular,
a Flask 500 with `jinja2.exceptions.TemplateSyntaxError` during
`render_template()` is a **template compilation failure**, not a Kubernetes
provider, authorization, or interactive-modal failure. The existing
`tests/contracts/kubernetes/test_existing_tenant_namespace_attachment_contract.py`
must parse both successful and error preflight templates with the Jinja
parser; source-only delimiter balancing cannot replace actual template
parsing. Header language,
readiness summary, human confirmation and submit label reflect the active
mode. Create-specific fields are disabled for the attachment request so they
are neither validated nor posted, and are re-enabled when returning to Create.
The backend remains authoritative via `attach_environment_id`, canonical
cluster/provider/UID/resourceVersion validation and a fresh provider read.

Both Native modes may perform admitted Kubernetes allocation writes with
provider read-back; attachment is **not** observation-only. Capsule's separate
provider-mirrored attachment mode remains unchanged and must not be mistaken
for Native managed allocation cutover. This is a presentation-only adjustment,
not a relaxation of Tenant ownership, RBAC or provider authority.


## Tenant registry table precision — Devcontainer Review (#1035)

Kubernetes Tenant follows the existing fixed-column, truncation, and inspectable
identity convention of the KAORI Kubernetes Storage Inventory and
`docs/design/components/TABLE_AND_LABEL.md`.

The Resource Profile, Tenant, Namespace, Membership, Group, Access Grant,
Namespace Access, Operations (Provider Authority, Namespace, Access
Reconciliation, Allocation Drift, all four Evidence modes), Capacity Budget,
Discovery, Capsule Tenant Quota Drift, and Capsule Shared Allocation Drift tables
now specify proportional header widths and explicit horizontal overflow
boundaries. Dense identity and supporting values truncate in their own columns;
full values remain inspectable through the existing `title` attribute and
owned dialog/detail workflows where available. The action column reserves
space for the actual action set and is **never** truncated to make text fit.
The four conditional Operations Evidence table headers retain independent
100%-width distributions.

**Tenant Discovery desktop layout (#1134; scoped correction):** The old
`min-w-[1300px]` forced the Review column and action outside the visible
desktop card. Discovery now follows the already-established canonical
responsive table policy: `min-w-[960px] lg:min-w-0` with a fixed
seven-column distribution of **20/16/11/9/14/13/17%**, reserving 17% for
Review Adoption/Attachment. Only Discovery opts into an optional compact
Cluster Identity width; the shared 12rem default is untouched for other
KAORI tables. Long identifiers truncate with their full-value title;
status badges, all seven semantic columns, Info Tip, empty state, filters
and canonical pagination retain existing behavior. The local
`overflow-x-auto` container still bounds narrow-table scrolling for
mobile/small tablets; at desktop width the table fits the available
card rather than creating a scrollbar solely due to minimum width.
Source-only presentation change; browser Visual QA and quality gates HOLD.

**Tenant Registry correction (#1035 follow-up):** the earlier 1300px
minimum forced horizontal scrolling even when the surrounding desktop Registry
had enough room for seven columns. The Tenant Registry now uses a 1040px
minimum (remaining inside the existing responsive overflow wrapper for genuinely
narrow viewports) and rebalances its header widths to
**20/19/12/9/15/13/12%** for Tenant/Cluster/Environment/Namespaces/Provider
Authority/Lifecycle/Actions. The Cluster identity retains its shared minimum
and the Manage/View action keeps a reserved non-truncated column; supporting
Lifecycle text truncates with an accessible full-value title. No other Tenant
table widths or shared table primitives are changed.

The **Namespaces** column now presents only the canonical active count and
short `active` label. Its tooltip retains historical record count context,
while the detailed “N historical Namespace records retained” evidence moves
to the dedicated full-width **Tenant Management detail page** beside the
Namespace summary. Historical Namespace records are not included in the
active count, and no persisted commitment/lifecycle value is changed.
Desktop table fit and responsive narrow-screen scroll are separate cases:
at wide desktop layouts the old forced scrollbar should disappear; at smaller
viewports the canonical table remains intentionally horizontally scrollable
rather than hiding the last Actions column or compressing critical evidence.

Cluster Estate now enforces its already documented proportional columns under
fixed-layout geometry. Credential Registry and Capacity Decisions already have
locked fixed-layout contracts and are intentionally unchanged.
This refinement changes no committed Tenant data, permission gate, pagination,
HTMX target, provider authority, or Kubernetes mutation semantics.

This is application of an existing table pattern, **not** a new global UI
standard. Pending checks: existing contract tests, formatter/static quality gates,
responsive/light/dark Devcontainer Visual QA and human acceptance. Review
integration target is `kaori/review/staging-uat`; CI/CD admission and
staging/UAT/deployment are explicitly held.

## Managed Release Re-adoption safety boundary (#1049)

The admitted observation-only `Released` history remains eligible for fresh
Discovery/Re-adoption when immutable provider UID and previous-generation
lineage agree. A **previously KAORI-mutated** provider object is different:
removing KAORI metadata or leaving the Namespace UID unchanged is not proof
that its verified successor agrees to return control. Re-adoption must not
silently take governance away from an external successor after a Release.

The existing `discovery_adoption.py` lineage checks therefore require fresh,
explicit successor handback authority for any previous provider mutation,
managed handoff marker, or recorded verified handoff. Until #1047/#1048/#1049
admit such a trustworthy handback contract, the new generation is blocked.
This applies both to Tenant-level and Namespace-level previous Released
records. It does not weaken the existing observation-only flow or create a
second Discovery or Release engine. The separate existing provider-authority,
capacity, UID/resourceVersion and human adoption preflights remain mandatory.

The guard is deliberately fail-closed: the current code **does not** accept
a manually entered change reference, a new provider label, a stale approval,
or a forged local consent flag as handback evidence. A future approved
successor-authenticated handback must be bound to the immutable Released
lineage and a freshly observed provider UID/resourceVersion before the guard
can admit a managed Re-adopt. No live Kubernetes mutation or Released
finalization is introduced by this protection.


## Native Platform Admin Release → handback → Re-adopt (#1049, 2026-10-10)

Approved authority: Native Kubernetes infrastructure is administered by a
small KAORI Platform Admin group. Ordinary users obtain delegated access via
JumpServer, pipeline, or scoped Tenant RBAC rather than infrastructure
administrator credentials. The already registered, TLS-verified Kubernetes
X.509 kubeconfig provides the **provider execution identity** (observed
principal `kubernetes-admin`, group `kubeadm:cluster-admins`). This does not
prove that a KAORI human has authorized a Release: explicit KAORI admin
confirmation and a separate independent reviewer supply that proof (#1047).
See the current `kubernetes-tenant-access-governance.md` security contract.

**Native Release is a provider-preserving governance handoff, not a transfer
of Kubernetes RBAC or a resource deletion.**

1. The KAORI Platform Admin establishes exact plan SHA, provider
   UID/resourceVersion, allocation inventory and dependencies. An independent
   KAORI administrator reviews the exact plan and a different authorized
   Platform Admin explicitly accepts governance Release. The existing
   kubeconfig is checked using Kubernetes `SelfSubjectReview` and
   `SelfSubjectAccessReview` for named resource `get` and `patch` rights.
   No successor token or client private key is uploaded by a user.
2. The existing Native executor (#1048) conditionally transfers only KAORI
   governance labels via UID/RV JSON Patch over ResourceQuota and LimitRange
   first, then Namespace. A final provider-side dry-run and strict read-back
   require identical resource specs, quotas, limits, foreign metadata and
   workload identity. It records partial/in-progress recovery rather than
   falsely claiming Released.
3. After a complete matching execution receipt, the canonical `Released`
   finalizer re-reads all provider objects, validates the administrative
   authority and zero active KAORI governance dependencies, and updates the
   existing Tenant/Namespace lifecycle and AuditEvent history atomically on
   the KAORI side. It does not issue provider writes or erase previous
   allocation snapshots. Resource and workload values remain unchanged.
4. **Re-adoption is a new explicit governance decision.** A currently
   authorized Platform Admin validates the Released lineage and provider
   connection anew, explicitly confirms handback and removes only the
   manager label through conditional Kubernetes PATCH plus provider read-back.
   New `handback_governance` evidence is bound to the old release plan,
   provider UID and resourceVersion. A future fresh Discovery/Adopt follows
   existing admission checks and creates the next Tenant/Namespace generation;
   the previous Released generation remains immutable. Prior approval is
   never automatically reused or treated as current authorization.

**Native ownership marker consistency (#1126).** Native Provisioning and
Allocation Cutover write the canonical `kaori.io/resource-profile` label.
The existing Native handoff marker contract must classify it as KAORI-owned,
along with `app.kubernetes.io/managed-by`, `kaori.io/tenant-id`,
`kaori.io/environment`, and historical `kaori.io/tenant-generation` /
`kaori.io/profile-id` labels. Only after the original KAORI ownership,
UID/resourceVersion, exact approved plan and provider identity are verified,
the Native executor removes those KAORI-owned keys that are present and
sets the approved successor manager. No Kubernetes spec, CPU/memory,
quota, unrelated label (including plain `environment`), annotation,
RBAC or provider authority is changed. Dry-run, read-back and Handback
fail closed when an old KAORI ownership marker remains.

This source correction applies only to **future authorized** Native
handoffs. For already `Released` / `Handback Verified` objects such as
`tenant-uat-demo` and its ResourceQuota, existing historical
`kaori.io/resource-profile` residue must stay **Blocked** in Discovery.
A separate, explicitly approved, provider-authoritative and auditable
metadata remediation is required: verify exact immutable release/handback
lineage, UID/RV, all affected provider components, nonownership metadata
and specs, perform a narrowly scoped conditional mutation with read-back,
then commit new evidence without rewriting any historical receipt.
Never automatically patch, repeat Handback, force Re-adopt, or remove
provider labels manually. All runtime mutation/security gates remain HOLD.

### Legacy Native Verified Handback residue: read-only assessment (#1129)

The #1128 provider-remediation workstream is split so historical evidence
can be assessed without creating a Kubernetes mutation authority. The
source-only service
`native_residual_recovery_assessment.assess_legacy_native_profile_residue_readonly`
is an **explicitly invoked, fail-closed diagnostic**, not a Tenant UI button,
automatic reconciler, new endpoint or PATCH executor. It requires an
existing authorized KAORI Platform Admin, exactly the Released Native
managed-handoff Tenant generation, a matching original dry-run / Released
receipt / latest verified Handback with the same plan, successor, cluster,
Namespace UIDs and complete Namespace/ResourceQuota/LimitRange scope,
zero remaining KAORI dependencies and verified live X.509 provider identity
through the existing SelfSubjectReview / named get + patch
SelfSubjectAccessReview. These authorization reviews are read-only
provider API calls; no provider mutation occurs in the assessment.

**Historical hash-version preservation:** old pre-#1126 dry-run receipts
treated `kaori.io/resource-profile` as *foreign* metadata. Their
`retained_metadata_sha256` must be recalculated with the **old fixed**
four-marker projection (`managed-by`, `tenant-id`, `environment`,
`profile-id`), never with the new six-marker projection. The assessor
also checks the original spec SHA, foreign labels and annotations,
ownerReferences/finalizers, historical last-Handback component RVs,
Namespace lineage and exact profile public ID; any other owned marker,
successor manager or drift blocks assessment. The only recognized
candidate residue is precisely `kaori.io/resource-profile`; arbitrary
`kaori.io/*` stripping is forbidden.

An advisory `read_only_recovery_candidate` result has
`cleanup_authorized=False`, `re_adopt_admitted=False`,
`evidence_committed=False` and `provider_mutation_performed=False`.
It **must never** be consumed as an execution authorization. Any future
provider recovery executor, independent human approval/Separation of
Duties, fresh CAS preconditions, partial-write evidence recovery and
append-only immutable audit/Namespace RV lineage updates require separate
security/design acceptance under #1128. Existing Discovery remains
Blocked and no historical AuditEvent or provider object is edited.
Tests, Developer Check, Full Admission, Kubernetes UAT and CI/CD remain
HOLD; source review is not formal admission.

### Reviewed source-only Native residual cleanup executor (#1128)

The earlier read-only assessment (#1129) is **not** a mutation token.
The #1128 source-only recovery workstream implements a separate,
append-only **Prepare → Independent Review → Execute → Read-back** contract,
reusing existing Platform Admin permissions, TLS-verified Kubernetes
`SelfSubjectReview` / named `SelfSubjectAccessReview`, and native JSON Patch
helpers. Both requestor and independent reviewer must be authenticated
KAORI Platform Admins, and their actor IDs must differ. An execution is
allowed only under the reviewer's authenticated request identity with
exact, unexpired reviewed plan SHA, fresh same-cluster provider assessment
and unchanged UID/resourceVersion/component digest. The #1132 implementation integrates this capability with the existing
**Tenant Detail → Platform Admin Handback & Re-adopt** section through
four permission-gated POST actions: **Assess live provider** (read-only),
**Prepare** (requester), **Independent Approve** (different Platform Admin),
and **Execute & Verify** (the independently approving actor).
No background job, new resource administration workspace, or automatic
Discovery/Adopt endpoint is introduced. The four routes are not used by
ordinary Tenant Detail GET and remain subject to independent actor, CSRF,
existing role, plan SHA and explicit confirmation checks.

The only potential mutation under an authorized future execution is the
literal `kaori.io/resource-profile` label on the **two fully evidenced**
historical resource components (or equivalently complete historical
evidence scope) through UID/RV/value-tested `application/json-patch+json`.
ResourceQuota/LimitRange are ordered before Namespace. Before every write,
an admission dry-run and fresh GET must preserve spec/CPU/memory, immutable
ownerReferences/finalizers, annotations and all non-profile labels.
After every write and again across the complete scope, provider read-back
must prove identical identities, preserved specs, no KAORI ownership
markers and exact new RV. Missing/changed/quota/provider evidence fails
closed; there is no forced retry after ambiguous/partial writes.

Execution records an immutable **started** AuditEvent before any provider
PATCH and a verified or partial-recovery receipt afterwards. A partial,
failed or unfinished attempt blocks further automatic execution/replay.
Only after *fully verified* provider coverage does KAORI atomically append
a new recovery receipt and add `residual_recovery_governance` projections
to Released Tenant and Namespace records; previous `release_governance`
and `handback_governance` receipts remain unmodified. A future explicit
Re-adopt may acknowledge the newer Namespace RV only when the existing
verified Handback plus the exact new append-only recovery AuditEvent,
receipt checksum, released Tenant/Namespace UID and provider RV all match.
Discovery remains the gatekeeper and never auto-Adopts.

**Authority and runtime HOLD:** The reviewed #1132 source wires an
explicit HTTP entry point but does **not** run a Kubernetes PATCH,
test suites, Developer Check, Full Admission or formal UAT. The live
mutation route is sensitive: it requires the same authenticated independent
reviewer, a fresh exact SHA/UID/RV/provider assessment and an explicit
checkbox. Integration into the review branch is **not permission to
exercise the operation while provider mutation/UAT HOLD remains**.
Human security acceptance and explicit execution authorization are
required before using the recovery action against Kubernetes. No direct
staging/main changes or external mutations have been performed.

### Historical Namespace Recovery visual hierarchy (#1188; DevContainer)

The `Historical Namespace Recovery` section preserves the existing #1132
governed state machine and all explicit authority checks, but uses the KAORI
Violet responsive layout: a compact icon/title and **committed-evidence status**
badge; a four-step numbered explanation strip (numbers are **not** completion
indicators); a persistent Discovery-first guidance note; two independently
labeled assessment actions; and a distinct Prepare Recovery Plan card with
required change reference, explicit confirmation and primary action. The
separate committed Plan, independent reviewer approval, provider execution
evidence and verified Discovery branches retain the same scoped, fail-closed
controls and no-retry rules, with readable bordered surfaces. An unresolved
provider execution is never presented as successful. No new provider calls,
permissions, endpoints, scripts, automatic adoption, confirmation waivers, or
contract semantics are introduced; 4 original CSRF/HTMX POST forms and 2
existing Discovery navigation links are preserved. Use only existing KAORI
surface/border/Violet/focus tokens and responsive wrapping for light/dark
DevContainer Visual QA. This is **source-only review**, not a grant to execute
sensitive Kubernetes cleanup while governance/security/UAT gates are HOLD.

### Released Native recovery and Discovery UX ownership (#1132)

A verified Native Handback may still have older residual KAORI profile
labels. The Handback section must **not** imply a clean Discovery simply
because the Handback receipt is verified. The Tenant Detail uses only
committed AuditEvent projections for the latest recovery plan, approval
and execution. On explicit HTMX POST, Assess invokes the existing
read-only provider assessment, which must never be stored as an approval.
Prepare requires a change reference and confirms current provider
scope. Independent approval must be by a distinct authenticated actor.
Execute is only rendered to the approving actor with an unexpired
unchanged plan and separate explicit confirmation; the service rechecks
all original evidence and provider authority server-side.

The UI initially offers a **Check Discovery First** link; when
Discovery is already eligible, no recovery is required. Otherwise it
distinguishes `Recovery Check · If Blocked`,
`Pending Independent Review`, `Approved — Not Executed`,
`Recovery Review Required` (including partial or in-progress), and
`Recovery Verified`. Incomplete/expired evidence has **no retry button**
or phantom reset; no new live provider reads occur during ordinary page
loads. Once the append-only terminal receipt and new RV ledger are
verified, **Open Discovery & Review Adoption** navigates to the existing
Discovery page. This is navigation only: the new adoption generation
still requires fresh provider UID/RV, zero residual ownership, canonical
provider preflight, exact predecessor lineage and user submission.

Responsive Violet status/steps, form CSRF, scoped HTMX swap,
loading/disabled controls, operational toasts and permission
boundaries reuse existing Tenant patterns; the form UI is a shared
partial rather than duplicating a second provider dashboard.

The `successor_owner` label is an administrative governance marker, **not
a Kubernetes IdP group, RBAC entitlement or credential recipient**.
Historical bearer-token successor receipts and old acceptance UI are
superseded, not eligible for active transfer. Admin certificates remain
inside the existing provider credential lifecycle; a credential identifier
such as an X509SHA256 hash is non-secret correlation evidence. A live
provider-principal change or any SAR denial blocks the current operation.
Cluster-admin-level credentials represent a privilege concentration risk;
separately review an eventual least-privilege connection, without expanding
this Release issue into a new identity-management subsystem.

Capsule-owned Tenant resources require their separate provider-authority
design; Native PATCH is never reused blindly for Capsule. This change is
merged only into the local DevContainer review branch. Unit/contract gates,
Kubernetes UAT, security/visual review, staging promotion and deployment
remain HOLD until expressly authorized.

## Release Step 3 Dev Container visual refinement (2026-10-23)

The accepted functional Native lifecycle UAT covered externally adopted Namespace,
managed Resource Profile changes, and provider-preserving Release. The next
presentation increment under #2401 rebalances **Independent Approval and Handoff**
without changing the governing transaction. Pending/acknowledged/expired plan
state, successor/change record and full Plan SHA remain committed evidence. The
acknowledged Native step uses two equal-width responsive peer surfaces for
Handoff Actions and External Handoff & Read-Back instead of a 3:2 desktop split.
On narrow screens the peers stack without clipping identifiers.

**Evidence Boundaries** is a native keyboard-accessible disclosure within the
read-back surface, keeping all three original boundaries available without an
oversized always-open nested information block. The Native Transfer Preview
retains its required checkbox, original CSRF/HTMX POST target and non-mutating
server-side dry-run semantics, but places the explanation and compact CTA
adjacent at desktop widths while stacking them on mobile. Provider identity,
read-back and Release admission gates are unchanged. Nothing in the redesigned
presentation confers independent review, verified successor consent, provider
transfer or a Released state.

Visual QA for this increment must capture Native acknowledged state (including
unverified external reference and verified Platform Admin), pending/expired
and blocked alternatives, optional Capsule paths, long exact SHA/UID/RV,
keyboard disclosure/focus, light/dark and responsive breakpoints. Jinja parse,
focused Tenant contract tests, and the existing lint/quality checks remain
required; official staging admission and provider mutation remain HOLD.

## Release Step 3 flat workflow sheet — Dev Container review (2026-10-23)

Follow-up human visual feedback for #2401 rejected repeated bordered cards in
the acknowledged Native Release view. The existing reviewed Jinja implementation
is flattened without introducing a new UI component, workflow state, provider
request, RBAC permission or transaction. Approval Expired remains the single
semantic warning. The recorded review state, planned successor/change record,
and full Plan SHA-256 form an unboxed summary strip separated by a rule.

The accepted-plan workspace retains its two peer sections. Handoff Actions
uses divider-separated committed evidence rows (unverified external reference
and independently verified Platform Admin authority); External Handoff &
Read-Back uses plain informational text with a single non-authorizing recovery
deep-link when prerequisites expire. Evidence Boundaries and historic Native
Dry-Run retain their keyboard-accessible native disclosures with thin dividers
instead of nested panels. High-impact forms and required confirmations remain
distinct where needed for operational safety. Violet semantic status badges,
light/dark design tokens and responsive wrapping remain authoritative.

This is a **presentation-only** change: all original POST endpoints, HTMX
targets, CSRF forms, permission predicates, dry-run, immutable plan SHA,
external successor consent, provider read-back and Released gates remain
unchanged. Source-level structural checks cover original Jinja controls,
23 forms/CSRF/HTMX POST and 8 disclosure pairs. Human Dev Container visual QA
must still verify expired/acknowledged/pending and blocked states, native/Capsule
branches, long identifiers, small screens, keyboard and light/dark mode before
acceptance. Official Developer Check, Full Admission, staging/main admission,
deployment and release remain on HOLD.

## Native Release Step 3 evidence row refinement — 2026-10-23

The follow-up #2401 visual feedback requires shorter copy in the Platform Admin
Approved, External Handoff & Read-Back, and Approval Expired sections, and a
more readable expanded Native Dry-Run evidence register.

The accepted-plan preview remains a read-only, non-mutating server dry-run
receipt; it is never provider ownership transfer. Its native accessible
disclosure separates Native Dry-Run, the committed outcome, and a neutral
`Historical / Not Current` marker, derived exclusively from
`native_release_readiness.dry_run_passed`. The original plan SHA correlation,
component coverage, exact Kubernetes Kind/Name, and untruncated UID are
preserved. Resource identities are displayed as responsive two-column rows
with thin dividers and selectable identifiers. Each UID reuses the existing
KAORI clipboard handler (`app/static/js/clipboard.js`) using
`data-kaori-copy-root`, `data-kaori-copy-source`, and
`data-kaori-copy-button`. There is no new JavaScript or provider request.

Dry-run errors remain visible if present, while a missing error list
does not create an empty error container. The UI still states
`Provider mutation: none. Release is still blocked.` An expired plan
still requires original-requester restart with a new SHA and independent
review; previous references and dry-runs may not be reused. Shorter
copy does not change SelfSubjectReview/SelfSubjectAccessReview checks.

No changes to the external engine, Native/Capsule authority, reviewer
separation, approval freshness, HTMX/CSRF, provider mutation, or Release
finalization. Dev Container Visual QA is required in both themes and
responsive breakpoints, historical/current/expired, long UID, error,
copy, and keyboard cases. Official admission and deployment remain HOLD.

## Native Release Platform Admin consent and concise prerequisites — 2026-10-23

Follow-up to #2401 preserves the approved Native Release Governance Step 3
workflow but reduces overlong instructions: expired approval still requires
the **original requester** to restart with a new plan SHA and independent
review; stale evidence is invalid. An external successor reference alone
does not prove consent. KAORI still checks provider identity and scoped
authority with its existing Kubernetes X.509 connection before recording
explicit Platform Admin consent; no separate successor credentials are
collected.

The native acceptance confirmation now uses a single compact Violet-soft
surface with a left accent and visible focus-within state, consistent with
the existing KAORI semantic tokens and without another surrounding card.
"Platform Admin Consent" is an action prompt, not an Approved/Released
status badge. The existing **required** checkbox and immutable plan SHA
remain bound to the same POST, verified provider scope and RBAC; a checked
box is explicit authorization for this one governed consent submission,
not a completed provider transfer or license to change Kubernetes
resource values. No new workflow, JS, provider calls or data state.

Dev Container Visual QA must cover keyboard checkbox/focus, checked/
unchecked validation, mobile and light/dark modes, expired/stale and
ready-to-consent conditions, long identifiers, and confirmation that
the independent review, provider handoff and Release remain separate.
Runtime tests, official Developer Check/Full Admission and staging
promotion remain HOLD pending explicit human authorization.

## Release independent approval Guide and compact consent — 2026-10-23

Step 3 of Native Tenant Release reuses the canonical `components/info_tip.html`
title-level `variant='guide'` immediately beside **Independent Approval
and Handoff**, not an independent help button. The shared Info Tip controller
handles pointer hover, keyboard focus and touch; the Guide describes the
distinct requester/reviewer, immutable plan SHA, Platform Admin consent,
external successor acceptance, provider handoff/read-back and Release gates.
Mandatory evidence, expired warnings and explicit acknowledgement remain
visible independently of the popover.

The source-authoritative external-reference recording checkbox now states
that a reference is for external verification only and does not prove
acceptance or authorize transfer. The original requester still cannot
self-approve or substitute references/dry-runs for independent authorized
Platform Admin verification and acceptance.

Platform Admin consent keeps its single `required` checkbox, form CSRF,
HTMX POST, plan SHA and exact-scope governance. The prior strong Violet
left border is removed; the same neutral-border Violet-soft background
retains accessible focus-within feedback without depicting approval as
already completed. Its abbreviated attestation is one visual line when
the desktop column permits and wraps naturally on narrow viewports.
`I authorize handoff for this plan SHA and exact scope; values stay unchanged.`
is a confirmation of a bounded decision, not provider execution.

This presentation-only work changes neither Kubernetes X.509/RBAC checks,
independent reviewer requirements, provider-owned state, SHA binding,
Dry-Run, provider mutation or Release gating. It needs Dev Container
Visual QA in light/dark, narrow/wide and keyboard/touch paths, including
long names, stale evidence and false/true confirmation. All official
Developer Check / Full Admission / promotion gates stay HOLD.

## Native Handoff Step 3 compact desktop actions — 2026-10-23

Human Dev Container review of the acknowledged Native Release step revealed
unnecessary nested borders and long two-line explanatory copy. The existing
two-column Handoff Actions / External Handoff & Read-Back layout now reserves
slightly more desktop width for read-back content while preserving natural
wrapping on mobile. This is a presentation choice, not a new layout system.

External reference and Platform Admin evidence remain divider-separated
committed rows with concise status text. The External Handoff inspection
form loses its extra rounded bordered card and uses a simple inline
divider. Its required confirmation still asserts **external operator handoff
has completed**, requests **read-only Kubernetes marker inspection**, and
cannot itself record successor consent, write provider resources, or Release.
The existing governed Native Handoff executor remains the KAORI-controlled
transfer path; no external provider authority is adopted by KAORI.

Native Transfer Preview remains a required checkbox plus a secondary
action, displayed in a thin full-width border/divider row rather than
an inset filled card. Its text explicitly states that the server-side
dry-run does not persist provider metadata, quota, or limits. The HTMX POST,
CSRF, fingerprint/SHA correlation, provider checks and eventual execution
and finalization gates are all unchanged.

Desktop copy is shortened to fit normal available line widths where
practical; text deliberately retains responsive wrapping and overflow
protection on smaller windows and with browser zoom. Accessibility,
light/dark contrast, keyboard checkbox focus, pending/expired/blocked
branches, and Native/Capsule boundaries require Dev Container Visual QA.
Previous Native Adopt → Resource Profile change → Release UAT acceptance
does not cover this newly revised visual state. Official CI/CD admission,
staging/main promotion and release remain HOLD.

## Native Release Step 4 expired restart evidence row — 2026-10-23

A targeted Dev Container visual refinement under #1091 shortens only
the original-requester Restart Expired Handoff Plan confirmation area.
The UI displays a compact read-only note: committed read-back reported
zero transferred resources, but any restart still checks the current
authoritative provider state (exact UID/resourceVersion, ownership,
and dependencies) and grants no automatic clearance. A small Info icon
uses existing Violet tokens without adding a nested warning card.

The required confirmation remains an explicit, separately readable
checkbox acknowledging unchanged provider ownership, followed by the
existing Restart Expired Handoff Plan secondary action. Spacing and
responsive button width are unified with the KAORI form-action grammar.
No label, handler, POST/HTMX/CSRF, plan SHA, requester-only/RBAC gate,
read-back freshness condition, or audit evidence semantics changed.
The button still does not bypass blocked read-back or provider recovery.

Dev Container visual QA must cover normal desktop, mobile, light/dark,
keyboard focus, expired and blocked cases and non-mutation semantics.
Official Developer Check, Full Admission and staging/main remain HOLD.
