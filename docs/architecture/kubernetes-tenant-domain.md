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

## Tenant Registry — contextual lifecycle actions (#1022)

Tenant Registry keeps the canonical committed-state table, filters and
pagination while limiting each row's Actions cell to one **Manage/View**
control. The operator-requested inline expansion was reverted after browser
Visual QA showed unwanted page geometry and large blank scrolling regions.
The original KAORI **native top-layer dialog** remains authoritative for
management, independent of registry/table overflow. Its interior preserves
the existing full-width Release Readiness → Handoff Inventory → Governed
Handoff → Verification/Release flow, plus provider and lifecycle cards.

Existing authorized POSTs render a fresh Tenant workspace and OOB operational
toast. Replacing that workspace previously destroyed its open native dialog.
The shared `native_dialogs.js` now preserves only explicitly opted-in dialogs
(`data-kaori-dialog-preserve-on-swap`) by snapshotting the active dialog ID
before HTMX swaps `#tenant-admin-workspace`, then reopening the newly rendered
dialog with normal focus handling after swap. Explicit user Close/Escape/backdrop
and unrelated navigation remain ordinary dialog behavior; the separate
destructive Decommission confirmation remains separate. The dialog inherits
prefixed `registry_*` paging/filter state and Tenant identity via `hx-vals`
so the exact selected dialog exists on the next committed-state response.
No new backend mutation or provider governance path is introduced.

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

Decommission remains separate and uses the existing destructive confirmation
modal; the expandable panel itself does not require an overlay.

This is a **presentation composition only**. No provider mutations, endpoint
changes, permissions, HTMX targets, committed-evidence contracts or automatic
Release/decommission eligibility changes are introduced. Native-dialog
keyboard/focus/ESC handling reuses `app/static/js/native_dialogs.js`; table
styles reuse `components/table.html`. Local DevContainer review must verify
small-screen, light/dark, focus/close, state transitions, blocked evidence and
HTMX replacement. Developer Check, Full Admission, and live-provider UAT
remain separate acceptance gates.


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
