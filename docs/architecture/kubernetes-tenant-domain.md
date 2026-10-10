# Kubernetes Tenant Domain

## Authority

Tenant is a Kubernetes capability/domain in KAORI. The global navigation destination is **Kubernetes → Tenant**. Native Kubernetes and Capsule are provider implementations behind one provider-neutral Tenant contract; provider names do not define separate product workspaces.

## Domain boundary

KAORI owns canonical tenant intent, provider binding, lifecycle, orchestration, committed evidence, governance, correlation, and audit. Kubernetes and Capsule remain authoritative for the enforcement they execute.

The persisted foundation begins with Tenant → Cluster binding → Environment (Development / Staging / Production) → Namespace ownership, plus provider binding, lifecycle/ownership state, correlation, and provider evidence.

Memberships, access grants, credentials, resource profiles, policy, activity correlation, Native enforcement, and Capsule enforcement are delivered by their bounded child workstreams rather than being preimplemented in this foundation.

## Provider authority

Provider binding is per tenant. `native_kubernetes` and `capsule` are the initial provider identities. One governed capability for one tenant has one active reconciliation authority at a time. A binding must never change merely because another provider becomes unavailable. Capsule-to-Native authority transfer is permitted only through explicit `native_recovery` after equivalent enforceable protections are materialized and verified.

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

## Tenant Details native KAORI workspace — human Visual Review correction (#1067)

Follow-up to #1065 and inherited #734 architecture. The first detail implementation
carried the **generic** Tenant Management Hero, an overview Provider Readiness
card, a duplicate in-page Tenant heading/breadcrumb/back button, and a
three-column dialog snapshot framed as one enormous white modal. The global
capability router also defaulted the detail endpoint to **Overview**, even
though the workflow belongs to **Tenants**. This duplicated authority and
misrepresented the navigation state.

The corrected design has a **single, Tenant-specific transactional Violet Hero**
using the approved shared `page_hero` helpers. Its h1 is the committed Tenant
name and it shows lifecycle, cluster, provider and generation. The Hero's
**only action** is Back to the filtered Tenant Registry. The generic
cluster-wide Provider Readiness aside is intentionally absent: it belongs on
the Tenant capability overview and collection surfaces, not an individual
Tenant detail. There is no secondary page breadcrumb; the **global navbar**
resolves `tenant.tenant_detail` as Kubernetes → Tenant → Tenants →
Tenant Details. Both the capability navigation and sidebar map this route to
the **Tenants** active key rather than defaulting to Overview.

Below the Hero, standalone committed-state cards summarize Namespace count,
environments, ownership and reconciliation authority. On desktop, a narrow
sticky section navigation lives beside the full-width Release Governance,
Native Handback, Capsule Attachment, Provider Authority and Lifecycle cards;
mobile layouts flow linearly. The working area has **no modal shell**, duplicate
page header, fixed-height scroll trap, close footer or generic top-layer dialog.
Short destructive Decommission confirmation remains the existing shared modal
component, with unchanged CSRF and safety checks.

The **Hero and body share the same `#tenant-management-detail` HTMX target**,
so any POST that changes lifecycle/status replaces current committed detail
evidence including the Hero; normal HTML POST still redirects to this detail
page. Existing OOB Operational Toast remains in the global app toast stack;
no custom stacking-context/z-index escalation is added. Read-only GET
is provider-independent. The current 14 governance forms, independent
reviewer, SHA/UID/RV validation, provider read-back and audit authority are
all unchanged. Runtime browser Visual QA, pytest and Full Admission are
pending; no staging/main or Kubernetes deployment was authorized.

## Tenant Registry → dedicated Tenant Management detail (#1065, supersedes #1022 presentation)

Tenant Registry retains the canonical committed-state summary table, Cluster /
Environment / Lifecycle / Search filters, default pagination 5 and a single
right-aligned **Manage/View** link per Tenant. Complex governance actions now
live at `/kubernetes/tenant/tenants/<tenant-id>/manage`, an independent,
permission-scoped full page based on the *same exact committed Registry row*
projection, unconstrained by Registry filtering or pagination. Missing Tenant
IDs return 404. There is no inline expansion below the table (rejected in
#1039/#1041), and there is no long-lived native management dialog overlay.

The detail page reuses the shared Tenant Hero/layout, breadcrumb back to the
filtered Registry, compact Namespace/Environment/Lifecycle snapshot, in-page
navigation and full-width Release Governance, Native Release/Handback,
Capsule Attachment, Provider Authority and Lifecycle cards. These stay
read-only for `tenant.view` users and permission/CSRF-gated for managers.
Existing service endpoints, two-actor plan authority, evidence read models,
provider inventory and destructive-operation rules are **unchanged**.
All 14 existing POST forms include a bounded `tenant_detail_id` plus
prefixed `registry_*` context for browser fallback and HTMX.
`_tenant_section_redirect` renders the same dedicated detail partial for
HTMX POST and emits the **existing** OOB Operational Toast; normal POST
redirects back to the same Tenant detail. Because the everyday management
workflow is not an HTML `<dialog>`, its toast is no longer obscured by
the browser's modal top layer. The only retained modal is the approved
short-form destructive **Decommission confirmation**; it is removed with the
replaced detail fragment after the action. No custom toast z-index, new
provider mutations or alternative authorization engine were introduced.

The Platform Operations Work Inbox deep link for an independent reviewer now
points directly at this detail route rather than the removed
`manage_tenant_id` auto-opening dialog. Approval still requires a different
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
