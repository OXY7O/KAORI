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

## Tenant Release Step 3 — structured independent approval evidence (#1089; current presentation authority)

Human DevContainer review of Release wizard **Step 3: Independent approval and handoff**
found an acknowledged plan, external reference, long SHA-256, and Platform Admin
verification stacked as nearly equal paragraphs. The canonical Step 3 now
has a compact KAORI icon/title, a separation-of-duties note, and distinct
committed evidence regions:

- **Active handoff plan** is a single compact locked-plan status panel showing
  the original pending/acknowledged/not-replaceable state, successor owner,
  and change-record reference. It explains plan immutability and governed
  restart without implying Release is authorized. Expired plans still
  distinguish original requester and required fresh preflight.
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

The same committed plan/approval/claim attributes, requester/reviewer
separation, endpoint actions, one-active-plan policy, successor identity
checks, CSRF/HTMX, approval/dry-run/executor/read-back/restart conditionals
and global toast remain authoritative. No new readiness algorithm,
provider-side operation, identity mapping, credential or approval engine.
The outer Release wizard continues to own one active URL-scoped step, while
this content stays committed-state driven. All **10 Step 3 conditional forms**
and **14 Tenant forms** remain present in source.

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

The UI distinguishes `Assessment Required`,
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
