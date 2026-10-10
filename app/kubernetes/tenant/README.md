# Kubernetes Tenant Management

Issue #61 is the parent product authority. Issue #125 owns the integrated Tenant workspace and final end-to-end UAT composition over the bounded implementation authorities #112–#124, #654, and #655.

## Product boundary

KAORI exposes one expandable `Kubernetes → Tenant` capability parent. Native Kubernetes and Capsule remain provider implementations behind the same canonical Tenant model and never become sibling product menus.

The approved Tenant destinations are:

- **Overview** — Tenant Collection Snapshot, multi-cluster estate posture, governed allocation/capacity evidence, prioritized operator attention, and recent Tenant activity. Navigation remains owned by the five Tenant sidebar destinations; Overview does not duplicate them as a Quick Actions strip.
- **Tenants** — canonical Tenant Registry plus a subordinate administration workspace for Tenant Setup, Memberships, Access Grants, Credentials, and Namespace Access.
- **Resource Profiles** — governed presets/custom profiles, allocation lineage, and capacity policy.
- **Namespace Provisioning** — namespace creation, allocation changes, ResourceQuota/LimitRange evidence, and capacity decisions.
- **Operations** — provisioning status, runs/evidence, drift/reconciliation, and Activity through internal Content Tabs.

### Cluster prerequisite and committed-read boundary

Tenant follows the shared #894 Provider Prerequisite Blocking contract while preserving #774 committed-read behavior.

- **No Kubernetes cluster registered** — Tenant is terminally blocked after the Hero. The canonical level-3 Tenant navigation remains visible for orientation, the normal Hero identity/metadata vocabulary remains stable, and the shared Kubernetes setup blocker owns remediation. Page-specific Tenant operational content is not rendered.
- **At least one cluster registered** — committed KAORI Tenant state remains readable even when live Kubernetes operations are restricted, validation is required, or the provider is temporarily unreachable. Live provider connectivity is presented separately and provider-backed mutations continue to fail closed.
- Zero-registration blocking must not be implemented from `native_available` alone. Registration existence and live/provider readiness are separate authorities.
- Provider absence must not hide route-level navigation; navigation expresses information architecture rather than evidence availability.

This preserves #750 terminal zero-cluster content blocking, #774 committed-state read availability, and #894 cross-domain navigation/Hero consistency without making normal Tenant pages depend on live provider requests.

### Resource Profile lifecycle

Resource Profile administration preserves the approved #113 allocation authority while avoiding profile sprawl:

- **Small / Medium / Large / Extra Large** keep server-authoritative numeric sizing values fixed. Operators can revise the **Managed ownership mask** and **Advanced Controls**; a contract change increments the same logical profile to the next version.
- Built-in revision never accepts operator-supplied numeric values. Canonical preset values are rehydrated server-side, so `Small vN` cannot silently redefine Small sizing.
- **Custom** profiles remain fully operator-managed. Edit may change name, description, enabled state, quota, storage guardrails, Container LimitRange values, and Advanced Controls.
- Existing Namespace allocations remain pinned to their committed `resource_profile_version` and frozen allocation snapshot after any profile edit.
- Resource Profile Registry exposes pending rollout state. **Attached Namespace Rollout** applies the current version to active Native Namespace attachments for one selected Tenant; each Namespace independently passes capacity admission, provider mutation, and read-back.
- A failed Namespace rollout stays on its previous committed version. Capsule attachments continue through Capsule-specific admitted governance paths; the Native rollout action never bypasses Capsule authority.
- **Hard Delete** remains limited to Custom profiles with **zero Namespace references and zero Capacity Decision references**. Built-in logical profiles cannot be deleted.
- Disable stops future selection without deleting historical profile identity or evidence.

Namespace Provisioning and Operations follow the same KAORI page hierarchy established by Tenant and Resource Profiles: **Snapshot → Estate → Workspace → focused Content Tabs**. Namespace Provisioning separates Provision Namespace, Allocation Change, and Capacity Decisions while the Namespace Registry uses canonical filters and default-five pagination. Operations separates Provisioning, Runs & Evidence, Drift & Reconcile, and Activity without creating third-level sidebar destinations.

Operations task views stay inside the page so the sidebar remains exactly two interactive levels. Only the five approved Tenant destinations are supported; superseded workspace routes are not retained.

## Evidence and provider authority

Normal Tenant workspace reads are composed from committed KAORI state. Live provider calls remain inside the owning mutation/reconciliation adapters, plus explicitly live surfaces such as Provider Connectivity and Tenant Discovery.

### Committed read model and Native provider readiness

Native Kubernetes remains the mandatory baseline provider for Native Tenant mutations. Tenant does **not** depend on Analytics, Metrics Source, or Alertmanager. Provider-backed mutation readiness follows the canonical Kubernetes runtime contract: the cluster must be connected, explicit `ready` or `degraded` validation states are operational, and a connected legacy registration with a null readiness field uses the connected-implies-ready compatibility fallback. `validation_required`, `blocked`, unavailable, failed, or disconnected states remain fail-closed for provider-backed mutations.

Provider readiness is **not** a page-level read gate. Tenant Registry, Resource Profiles, committed Namespace state, access/credential metadata, Operations evidence, and committed capacity/snapshot evidence remain readable from KAORI state even when the Kubernetes API is unavailable. With zero cluster registrations the setup guidance remains visible, but committed KAORI records are not hidden. With a registered but non-Ready provider, the Hero reports **Provider Operations Restricted** while the committed workspace remains available.

The two snapshot concepts are intentionally separate:

- **Tenant Collection Snapshot** — committed evidence produced by `kubernetes.tenant.sync`; it retains last-success, source cutoff, scope, coverage, and exceptions while the provider is offline.
- **Live Provider Connectivity** — a short, explicit live Kubernetes API reachability probe. The on-demand endpoint remains available for supported operational flows; routine Tenant page reads do not perform live probes, and child pages do not expose a second connectivity panel. A probe result never replaces the committed snapshot.

This boundary does not weaken mutation safety. Create/provision/reconcile/credential/provider mutations continue to use their owning readiness/capability checks and fail closed. Discovery from #736 remains the explicit live-provider read exception.


Routine Tenant reads also keep expensive supporting evidence bounded. Operations uses the canonical Namespace/Tenant registries with workflow/decommission support disabled when those controls are not rendered. Tenant Overview batches KAORI-owned capacity policy, committed Namespace allocation, Capsule shared-allocation evidence, and committed Capacity Analytics snapshots across the registered cluster estate before applying the existing per-cluster capacity classification and operational sort. Snapshot freshness and stale/blocked semantics continue to use the canonical materialization reader; no live provider request or new cache is introduced.

Tenant Overview owns a registered **Tenant inventory correlation** job while Kubernetes remains authoritative for observed cluster resources:

```text
Kubernetes provider observation
→ kubernetes.inventory.sync
→ committed Kubernetes inventory

KAORI Tenant state + committed Kubernetes inventory
→ kubernetes.tenant.sync
→ worker-generated Tenant Collection Snapshot
→ Tenant Overview
```

`kubernetes.tenant.sync` runs through the canonical Platform Operations registered-job scheduler and the existing `inventory` worker queue. It does not introduce a Tenant-specific scheduler framework and it does not perform Tenant reconciliation or provider mutation.

Non-Overview Tenant pages (Tenants, Resource Profiles, Namespace Provisioning, and Operations) render **one canonical Inventory-style Snapshot Context Bar** beneath the Hero, reusing `components/snapshot_context_bar.html` through the existing `_collection_snapshot_context.html` partial. The bar preserves status, source, last successful collection, committed scope, committed namespace coverage, and snapshot exceptions — including `Not Collected`/stale/partial states. The same committed snapshot bar also remains on **Overview**, where **Sync Tenant / Configure Sync** actions are unchanged. Child pages render no Live Provider Connectivity panel or Check Live Connectivity action and issue no provider probe during normal committed reads.

Overview actions follow the established operational sync pattern:

- **Sync Tenant** — manually dispatch `kubernetes.tenant.sync`.
- **Configure Sync** — open the registered-job policy for automatic cadence.

The existing global **Sync All Inventory** quick action remains the cross-domain orchestration entry point and includes Tenant sync alongside Kubernetes/Object Storage inventory domains allowed by the operator's permissions. Tenant Overview does not duplicate that global action.

Successful manual dispatch follows the TLS synchronization behavior: the HTMX click updates worker progress without creating a completion toast or incrementing the Notification Deck immediately. The worker persists the operator notification only when the job reaches a terminal state, with Tenant/namespace/cluster coverage and exception evidence from that completed snapshot.

Capacity Analytics remains a separate committed evidence authority. Tenant sync must not fabricate missing capacity data or imply that refreshing Tenant inventory refreshes `analytics.capacity`. Overview keeps per-cluster capacity information compact: posture, freshness, and a path to Capacity Analytics are shown instead of detailed allocation tiles or meaningless `N/A` values. The cluster estate follows the canonical KAORI table and pagination contract with 5 rows by default and 5/10/25/50 page-size choices; full fleet inventory remains owned by Kubernetes Inventory.

- Native Kubernetes is the mandatory baseline provider.
- Capsule is capability-aware and optional.
- Degraded/unavailable Capsule capabilities fail closed.
- Provider state and reconciliation authority are explicit committed evidence.
- Capsule-only advanced mutations require admitted compatible capability evidence.
- Native Recovery remains an explicit governed authority transfer, never an automatic fallback.

## Tenants workspace composition

The Tenants destination keeps a small page-level governance summary visible above one tabbed workspace:

```text
Hero
→ Multi-Cluster Posture
   └── Tenant Estate
→ Tenant Workspace
   ├── Tenant Registry
   ├── Tenant Setup
   ├── Memberships
   ├── Access Grants
   ├── Credentials
   └── Namespace Access
```

`Tenant Registry` is the default tab and uses the canonical KAORI server-backed registry contract: shared loading bar, Cluster/Environment/Lifecycle/Search filters, committed-state reads, semantic labels, responsive horizontal overflow, default 5-row pagination, 5/10/25/50 page sizes, and HTMX progressive enhancement with the Tenants route as the real navigation fallback.

**Tenant Release Step 2 — compact resource summaries (#1085; latest UI):**

DevContainer refinement removes repeated vertical gaps in Provider
handoff scope. A single short heading now includes the committed total
resource count, while the original handoff-required status badge remains.
Each resource's **native `details` summary** is one clickable two-line
row: icon, full Kind/Name, original semantic status, and inline labeled
Namespace (when distinct), Ownership and Manager. The on-row **Provider IDs**
cue opens exact committed Namespace/UID/resourceVersion, with full-width,
wrap-safe detail values. This replaces the old separate Ownership/Manager
grid and separate identifier toggle line (no nested scrollbar, new tab,
component framework, or provider API). Keep initial evidence read-only,
its original empty states, provider authority, protected Release flow and
all 14 CSRF/HTMX forms intact. Tests and local browser review pending;
all admission/CI/CD gates remain HOLD.

**Tenant Release Step 2 — provider handoff resource evidence (#1085; historical first pass):**
Render the four-stage Release wizard's second step as one clear structured
resource list rather than dense provider text rows. A compact summary uses
committed `handoff_required_count` and `handoff_components|length`; each
resource shows its exact Kind/Name, Handoff Required/Ownership Conflict/
Observed semantic label, and distinct Ownership evidence and Provider manager
facts. Exact provider Namespace, UID and resourceVersion are kept under
native keyboard-accessible `Provider identifiers` disclosures. Show the
original not-collected and no-handoff messages distinctly, with no false
ready/approved state. This is committed Release preflight evidence only;
Kubernetes/Capsule remains authoritative, and provider handoff/Release never
occurs from merely viewing this list.

The `release_preflight._release_blockers` copy for an adopted Namespace with
a linked Resource Profile now explicitly states the need for approved
provider allocation handoff and verified read-back; its admission guard
is unchanged. All 14 original CSRF/HTMX governance forms and step URLs,
independent approval, native provider verification, styling and global OOB
toast remain unchanged. All CI/CD gates and local human Visual QA remain HOLD.

**Tenant Overview — integrated authority and lifecycle (#1081 follow-up; current UX):**
On the same compact Overview surface, retain exact Provider and
Reconciliation Authority facts but remove their redundant full-size
**Provider Authority** accordion. The Reconciliation field owns the prior
`#tenant-provider-authority` deep-link anchor. Move the precise
Kubernetes/Capsule source-of-truth statement out of the large
**Authority Boundary** callout into a small neutral Overview note. Place
the existing Decommission/Retry and blocker preflight in one collapsed
**Lifecycle controls** row at the bottom of Overview, retaining
`#tenant-lifecycle-actions`, the lifecycle section auto-open state,
permission guards, exact POST/CSRF/HTMX fields and native destructive
confirmation modal. Release/Handback/Attachment and global toast behavior
remain unchanged; there are still 14 original form authorities.
Hero subtitle: “Manage Tenant governance, provider authority, and lifecycle
with committed evidence.” No new provider read, grant or mutation contract.
DevContainer visual QA and all CI/CD gates remain HOLD.

**Tenant Overview — compact committed record (#1081; historical foundation, superseded standalone boundary placement):**
DevContainer feedback supersedes the former #1081 two-subpanel + Record
History band layout. Reuse one existing bordered Violet KAORI surface with
a **small Identity & Governance header**; show exact wrapped/monospace Tenant
ID on one line/row, then a responsive 4/2/1-column plain facts grid:
Cluster, Provider, Ownership, Lifecycle, Reconciliation Authority, Generation,
Registered, Last Updated. Keep canonical semantic lifecycle status and
`Not recorded` date fallbacks, with the small historical Namespace footnote
only if applicable. Put the full Description in a single inline-label bottom
row, safe for long text/newlines and without whitespace indentation artifacts.
Do not repeat #1079's KPI cards, reintroduce Quick Links, or introduce a new
UI system/provider request. Preserve all 14 forms, Release wizard and the
standalone Authority Boundary note. DevContainer Visual QA / CI/CD HOLD.

**Tenant Governance Scope — canonical shared posture card (#1079; current UI):**
Match the existing Tenant Overview `Governance Scope → Tenant Estate`
layout using `section_intro`, `operational_section_card.render` and
`resource_posture_grid.render(columns=4)`. The single header panel
is titled **Tenant Governance**; its four shared posture cells read
**Active Namespaces, Environments, Reconciliation Authority and Lifecycle**
from committed Tenant evidence. This replaces the two independent
Resource Coverage/Governance Authority cards from #1077, not the
provider-authoritative boundary note or any governance action.
Do not mix fleet-wide Tenant/Credential/Finding counts into one-Tenant
detail. The shared component owns responsive separators, metrics/icon
layout and light/dark styles. Runtime browser Visual QA and quality gates
remain pending.

**Governance Scope and Release Review refresh (#1077; historical workflow authority; scope presentation superseded by #1079):**
The four separate Tenant KPI tiles are replaced by a grouped
**Governance Scope** (Resource Coverage and Governance Authority) composed
only of committed Namespace/Environment, reconciliation and lifecycle
data. A separate neutral **Authority Boundary** info box explains that
KAORI presents committed evidence while Kubernetes/Capsule remains
provider-authoritative; the historical Namespace count remains available.

Release Governance is **always visible**, with an icon header rather than
numbered outer disclosure. The four existing Release wizard steps remain
URL-addressable; the Review Scope step presents a short readiness
summary, original Review Release action and an optional exact
**View recorded conditions** list. This reduces initial text density
without deleting blocker evidence. Two redundant instructional footnotes
were removed from the interface without changing any authority gate.
Other governance sections remain conditional expandables. Same 14
CSRF/HTMX actions, reviewed handoff, committed audit and toast; no new
provider mutations. Browser Visual QA and execution/security gates
remain pending.

**Tenant Overview and Release wizard (#1075; historical revision):**
Keep the existing KAORI two-column Violet Hero/context card, but shorten its
subtitle to "Manage Tenant governance and lifecycle." Historically, replace the old
identity table + Description/Quick Links with distinct **Identity & Origin**
and **Governance State** surfaces (now superseded by #1081). No Quick Links; source all factual values
from committed Tenant and Cluster records, with guarded timestamp and
historical Namespace display.

For ready governed Tenants, Release Governance offers a real four-stage
`release_step` URL workflow rather than immediately displaying every form:
1. Review Scope (preflight/blockers), 2. Provider Scope (inventory),
3. Approval & Handoff (independent plan, consent, guarded execution),
4. Verify & Finalize (evidence read-back and Released commit). Only the
selected step renders. Links are navigation only, not admission: original
service-side plan freshness, separate reviewer, CAS and provider read-back
remain authoritative. Next/Previous and full reload preserve the Registry
context; HTMX POST keeps the active stage through `tenant_release_step`
and displays the normal global OOB toast. Work Inbox opens the Approval
stage directly. Unsupported stage values fall back safely to Scope.
No extra provider requests on ordinary GET or new mutation endpoints.
All gates and real cluster/Visual UAT remain HOLD.

**Tenant Details approved visual composition (#1073; Hero/accordion foundation; Overview/Release layout superseded by #1075):**
Use existing full-size Violet two-column Hero with shared `page_hero.context_card`
for a contextual Tenant Details right-side panel, two committed metrics,
lifecycle status and the full-width Back to Registry. Under it show four
responsive summary cards and a two-column Tenant Overview with identity,
description, audit-lineage note and links to existing KAORI registry/services.
Use five native keyboard-accessible expandable governance sections instead
of a long wall of forms or secondary Content Tabs. Release opens with a
four-stage preview but keeps the detailed independent approval, provider
handoff and finalizer controls folded until requested. Independent Work
Inbox links expand Release immediately. All 14 existing forms carry
`tenant_detail_section`, their prior CSRF, exact resource identity and
Registry state. After POST the active permitted section reopens and the
global OOB toast remains visible; Decommission alone retains its short
destructive confirmation modal. Normal detail GET is committed-only.
Earlier stacked/modal/tabbed layouts were rejected during Human Visual QA.
Runtime Visual QA/security gates remain pending; no staging release implied.

**Tenant Management single-page correction (#1071, superseded historical design):**
The user rejected both the oversized dashboard (#1067) and the secondary
Content Tabs workflow (#1069). The current detail is one naturally scrolling
page with the exact shared KAORI Violet Hero sizing, layout, intro/title,
description and metadata classes. It has a single Back to filtered Registry
action, the normal Tenants active navigation and canonical global breadcrumb.
A concise Tenant Overview is followed by clearly described, full-width
governance sections: Release (four divided phases with readable blocker and
inventory evidence), Platform Admin Handback, Capsule Attachment, Provider
Authority, and Lifecycle. Sections appear only where applicable and
authorized. No custom Hero overrides, nested modal framing, second tab row,
sticky sidebar, oversized KPI cards or internal inventory scrolling.

All 14 existing governance POST forms, CSRF, provider authority, independent
review, exact Tenant identity, and Registry filters remain unchanged. The
entire detail including Hero is refreshed by HTMX and emits the existing OOB
Operational Toast; the non-JS POST returns to the same page. The Work Inbox
link scrolls directly to the Release Governance section. Only short
Decommission confirmation remains modal. No provider or permission rules
were changed. Browser Visual QA and gate admission remain pending.

**Dedicated Tenant Management (#1065):** a Registry row's single
`Manage/View` action navigates to `/kubernetes/tenant/tenants/<tenant-id>/manage`,
a full-width, responsive, committed-state Tenant detail page. It retains
Registry search/filters/pagination on the **Back to Registry** link and
provides in-page navigation for provider ownership, Release governance,
Capsule attachment, Native handback/Re-adopt and lifecycle actions. It does
not expand below the table or open the removed long native Tenant Management
dialog. Independent approvers from Work Inbox deep-link to the same detail
page instead of reopening a top-layer dialog. Every form keeps its existing
authoritative backend endpoint, CSRF token, permission gate and audit
metadata; both progressive HTMX swaps and ordinary POST redirects return
to the same Tenant detail rather than a Registry modal. Normal HTMX
feedback continues using the existing OOB Operational Toast, which stays
visible because the daily management page is not in the browser's modal
top layer. Decommission retains its separate concise destructive confirmation
modal. Normal detail GET performs no Kubernetes provider request.

`Tenant Setup` combines the create form with a non-collapsible governance flow so the operator sees the required order: Tenant → Namespace → Membership → Access Grant → Credential. Important boundaries use icon-backed tiles plus a persistent warning row. Dense field guidance uses the shared `components/info_tip.html` hover/focus pattern instead of repeating helper paragraphs under controls.

Tenant Setup supports two direct-create provider paths while retaining one provider-neutral UI. **Native Kubernetes** creates the KAORI Tenant boundary without a first-class Kubernetes Tenant object; Namespace resources are introduced later by Namespace Provisioning. **Capsule** performs its live supported-CRD/capability and admission preflight when **Add Tenant** is submitted, requires both an initial Owner Kind and Owner Subject, dry-runs the exact Tenant CR, then creates the authoritative Capsule Tenant CR before committing KAORI provider evidence. Existing Capsule Tenant CRs are never overwritten and continue through **Discovery → Adoption**.

`Memberships` separates three peer actions (add user, create group, add group membership) from scalable registries. Successful administration mutations progressively refresh only the Tenant Workspace through HTMX rather than forcing a full-page navigation/scroll reset. Membership and Tenant Group data each use canonical filtered/paginated tables instead of fixed recent-item lists.

`Access Grants` keeps one full-width multi-column form above the canonical Access Grant Registry. The registry owns all committed/effective RBAC evidence, filters, pagination, and Inspect/Reconcile/Revoke actions.

`Credentials` presents Human and CI/CD issuance as symmetric peer forms. Credential Lifecycle is a canonical registry table with filters, pagination, validity, reconciliation state, lifecycle actions, and protected material-generation actions. Its action column uses labeled **Generate** and **Renew** controls when eligible; Suspended credentials expose **Resume** as the primary action, while Expired credentials expose **Renew**. Secondary **Suspend/Resume** and **Revoke** actions are in a labeled **More** native dialog outside the scrolling table, so the controls remain accessible on narrow viewports. Revoked credentials and read-only users have no actionable mutation controls; generation requires Active/Renewal Due, Ready reconciliation and a suitable target namespace. Destructive revocation is described explicitly before the final submit. Desktop layout follows the canonical table contract without unnecessary horizontal scrolling; narrow viewports may still use controlled table overflow. Routine registry/detail surfaces never render secret material. Explicit material generation opens a non-cacheable one-time view; KAORI does not persist the returned token or kubeconfig body.

`Namespace Access` is a derived non-secret read model presented as a canonical registry with Tenant/Environment/Credential filters and pagination.

All tabs reuse the Analytics-derived `components/content_tabs.html` server-link mode. Every tab retains a real URL fallback while HTMX replaces only the Tenant Workspace. Mutation routes return operators to the relevant section.

Tenant identity is immutable after creation in the normal operator workflow.

- **Create** — create the Tenant ownership boundary and initial environment.
- **Read** — Tenant Registry is the committed-state source for operator reads.
- **Update** — no inline Tenant identity update is exposed. Name/slug identity, cluster placement, provider authority, and reconciliation authority are intentionally locked.
- **Lifecycle removal** — #735 owns governed teardown. Tenant detail exposes asynchronous **Decommission** and preserves one ordered lifecycle: freeze new mutations → revoke access state → retire memberships/groups → remove admitted managed resources/namespaces → retire reservation/exposure state → provider verification → commit `decommissioned`.
- **Provider verification** — a successful provider `DELETE` request is not completion. Native Namespace teardown observes Kubernetes until absence and never strips finalizers automatically. Capsule teardown likewise commits completion only after the authoritative Capsule Tenant CR is verified absent.
- **Capsule authority** — baseline Capsule teardown is admitted only for **KAORI-created, Managed, healthy Capsule Tenant CRs with zero active namespace/access/credential/managed-resource residue**. The adapter validates KAORI ownership labels, Tenant generation, and provider UID before deleting the Capsule CR, then verifies absence. Adopted/foreign Capsule objects, degraded Capsule state, active namespaces, or other unsupported provider residue remain fail-closed; KAORI never falls back to Native deletion.
- **Historical identity** — decommission retains the historical Tenant row, evidence, memberships, grants, credentials, and correlation lineage. Re-creating the same cluster+slug creates the next Tenant generation rather than overwriting history.
- **Name and namespace reuse** — the same Tenant slug may exist independently on different clusters. After a Tenant is fully Decommissioned, the same cluster+slug may be recreated as the next Tenant generation. A previously managed namespace name may likewise be reused on the same cluster only after the earlier namespace generation is provider-verified Deprovisioned; active duplicates remain fail-closed.
- **Structural change** — when immutable identity or placement must change, use governed teardown + recreation rather than mutating the Tenant in place.

#734 still prohibits a database-only lifecycle flag change from being presented as provider decommission; the final lifecycle transition now occurs only after the #735 provider verification path succeeds.

### Provider Discovery and Adoption

#736 owns the two-way Tenant Registry path. Discovery is an explicit live-provider exception to normal committed-state reads: it reads Native Kubernetes namespaces and Capsule Tenant CRs on the Discovery request, shows provider status, correlates objects already governed by KAORI, and classifies candidates as **Managed**, **Discovered**, or **Blocked**. It does not wait for the Overview inventory worker sync. Discovery itself never mutates provider state.

Discovery intentionally keeps the registry pass lightweight. The registry request enumerates provider candidates only; it does **not** inspect per-candidate ResourceQuota, LimitRange, Capsule allocation authority, GlobalResourceQuota, or Capsule CRD capability state. **Review Adoption** lazy-loads one deep live Adoption Preflight through HTMX for the selected candidate. The preflight request builds detailed allocation/capability evidence only for that candidate. **Adopt & Manage** performs its own fresh provider read and fail-closed conflict/authority revalidation; preflight output is never trusted as mutation authority.

Manual provider deletion is treated as drift, not implicit Tenant deletion. After a fresh Kubernetes Inventory collection, `kubernetes.tenant.sync` marks a previously Ready managed/adopted Namespace as **Drifted** only when the inventory cutoff is at least as new as the Namespace's last KAORI-side provider evidence. The observation path never recreates or deletes resources automatically. **Operations → Drift & Reconcile** exposes corrective provider actions only through the admitted authority and explicit operator intent.

Explicit adoption is a separate human-confirmed mutation over KAORI committed state. The Adoption Preflight shows provider identity, live status, provider authority, current ownership, proposed KAORI mapping, governance checks, and the observed allocation baseline. Under the #777 human-reviewed contract, adoption uses a **provider-equivalent managed takeover**: observe first, materialize the supported values into committed KAORI control state, write the same effective values only through the authoritative provider path, then require provider read-back before control becomes Managed.

Native namespace adoption keeps Namespace lifecycle ownership **Adopted**. It captures ResourceQuota, Container LimitRange, and PVC Min/Max evidence, materializes the supported allocation contract, runs capacity admission, reconciles equivalent values through the Native authority, and records `allocation_control_state=kaori_managed` only after verified read-back. Namespace lifecycle ownership stays Adopted; allocation governance is an independent control dimension.

Capsule adoption keeps Capsule as execution authority. Admitted shared allocation can enter KAORI Managed control through the capability-gated Capsule path. Capsule-generated per-Namespace Container/PVC policy without an approved source-write contract is imported as `provider_mirrored_policy` and refreshed from provider authority so controller-owned values do not create false drift. Ambiguous, unsupported, stale, or capability-missing controls fail adoption closed rather than entering a partial managed state.

Observation evidence still records `provenance=adopted_observed` and `provider_mutation_performed=false` before takeover. Successful managed takeover records the authoritative mutation/read-back evidence separately. Adoption never silently converts provider principals into KAORI Membership/Access Grants and never bypasses provider authority.

### Managed Adoption and Legacy Allocation Governance Cutover

#777 is the current contract for new human-confirmed adoption. Existing **Adopted / Observed** records created under the earlier #768 behavior remain valid historical state and continue to use the #769 explicit allocation-control transition when an operator chooses to govern them:

```text
Adopted Namespace
└── allocation: Adopted / Observed
      ↓ explicit governed takeover
    KAORI Managed allocation
```

The takeover is available only when allocation authority is proven and supported. It compares current observed state with the intended Resource Profile, runs #654 capacity admission, revalidates provider UID/resourceVersion and ownership, performs only the authoritative provider mutation, then requires provider read-back before committing managed allocation state.

For Native Kubernetes, KAORI adopts control of the single authoritative ResourceQuota / Container LimitRange without taking Namespace lifecycle ownership. Existing legacy resource names are preserved when safely identifiable. Missing allocation resources may be materialized using the canonical KAORI resource names. Foreign-manager resources, multiple competing sources, unsupported LimitRange semantics, stale provider evidence, or read-back mismatch fail closed.

For Capsule, #771 admits one explicit shared allocation path: exactly one authoritative `GlobalResourceQuota` with healthy Capsule reconciliation authority, served v1beta2 API, and committed `shared_global_quota=available` capability evidence. The cutover uses the existing #124 CustomObjects executor, preserves the provider selectors and identity, performs shared Tenant-level capacity admission, verifies UID/resourceVersion before mutation, and requires provider read-back before the allocation becomes **KAORI Managed**. The shared quota is counted once for the Tenant rather than once per correlated Namespace. `Tenant.spec.resourceQuotas` and ambiguous/unsupported Capsule authority remain **Control Unavailable**. KAORI never bypasses Capsule authority with a direct Native quota write.

After successful cutover, normal governed allocation changes can operate on that allocation contract while the Namespace itself remains `ownership_status=adopted`. A provider failure before verification preserves the prior allocation-control state and records failure evidence for later drift/reconciliation review.

Tenant workspace mutations that are progressively enhanced with HTMX render operational feedback as an out-of-band KAORI toast in the same response. Success and failure feedback therefore appears immediately without requiring a full-page reload; persisted Notification Deck evidence remains synchronized through the standard toast notification-refresh contract.

The former monolithic UAT-only Members & Access and Credential Management partials are retired. Final UX does not expose `Functional UAT Surface` copy or render all administration forms simultaneously.

## Access and credential boundary

KAORI application RBAC (`tenant.view`, `tenant.manage`) is separate from Tenant Kubernetes Membership and Access Grant authorization.

The routine UI may show non-secret access metadata such as:

- Tenant/environment/namespace and cluster identity;
- Access Profile/version;
- approved access method;
- ServiceAccount name;
- lifecycle/reconciliation state;
- renewal/review and validity times;
- rotate/suspend/resume/revoke actions.

Routine Tenant inventory, registry, detail, report, Activity, and Namespace Access surfaces must never render bearer tokens, generated kubeconfig content, certificate/private-key material, or registry Secret material.

Explicit credential delivery is the bounded exception. An authorized operator may request one-time material from an Active/Ready credential and target Namespace. KAORI uses Kubernetes TokenRequest-backed ServiceAccount material, returns it only in a non-cacheable one-time response, records issuance metadata without plaintext secret content, and does not persist the token or generated kubeconfig body.

Material lifetime is independent from the longer credential entitlement/review lifecycle. Current KAORI policy offers operator-selectable lifetimes bounded by target environment: **Development up to 24 hours**, **Staging up to 8 hours**, and **Production up to 1 hour**. Kubernetes remains authoritative for the actual expiration timestamp and may return a shorter lifetime than requested.

Human access issuance uses the admitted #115 service and binds an individually owned reconciled User Access Grant to a non-secret JumpServer reference. The one-time Human action mints a ServiceAccount token for manual placement into the referenced JumpServer credential until direct JumpServer integration exists. CI/CD issuance uses the admitted #116 Deployer service and creates a namespace-scoped machine principal/grant/credential lineage. Its one-time action returns both kubeconfig YAML and a Base64 representation suitable for short-lived GitHub Actions UAT; long-running recurring delivery should later obtain fresh material at runtime rather than treating the governance entitlement as a static bearer-token lifetime.

Credential UI copy presents **Human Access Credential** and **Workload Deployment Credential** as separate capabilities; the issuance cards, registry delivery display, and material-request dialogs avoid using a single provider or CI/CD product as the generic feature name. **Access Account Reference** is presentation-only: it continues to submit the non-secret `jumpserver_reference` field and currently supports manual JumpServer token delivery under #115. Deployer issuance continues to submit the existing `github-actions-helm` purpose and short-lived kubeconfig delivery under #116. The registry displays a capability label without repeating vendor names; the authoritative delivery method remains preserved in the committed credential record and audit evidence. General wording must not be interpreted as support for additional access gateways, pipeline providers, or different credential mechanisms. Generated one-time material/result instructions are owned by #961. The result is a focused **transactional delivery page**, not a second Tenant inventory or administration workspace: it uses the existing Violet KAORI `page_hero` components with a short **Access Material** title and delivery context, while preserving its independent one-time response outside the ordinary Tenant onboarding gate. Navigation selects **Tenants** and displays the **Access Material** breadcrumb; other Tenant Heroes remain unchanged. The approved delivery context remains one full-width four-fact strip, followed by the warning before any exposed material. Context facts use a compact 14px value and 12px supporting-text hierarchy with responsive one/two/four-column layout; the long ServiceAccount identifier stays a single truncated line, exposing its complete value in the title and through the already-loaded KAORI clipboard control. This is presentation-only and does not change the canonical shared Resource Posture Grid or provider evidence. Human token or kubeconfig and Base64 appear in full-width canonical `one_time_secret.material_block()` surfaces, never as parallel sidebars. The three delivery steps use a horizontal row at desktop widths (stacked on smaller screens), and only Deployer material shows the full-width ephemeral kubeconfig command example. The right Hero panel ends with the standard **Back to Credentials** action; the compact footer keeps **distinct** entitlement validity and provider-issued material expiry without a duplicate navigation button. The Human token and Deployment kubeconfig result surfaces now use capability-first labels and manual-vs-automated delivery instructions rather than presenting JumpServer, GitHub Actions or Helm as universal requirements. Deployer results show automated-delivery steps and a temporary kubeconfig example with restrictive permissions, Kubernetes authorization verification, and file cleanup. Administrative/approved individual kubeconfig results instead show governed manual-use steps, never pipeline-only instructions. The result page reads entitlement validity from the committed access-package evidence rather than incorrectly repeating the short-lived token expiry. Actual Human delivery remains the existing manual JumpServer reference contract and automated delivery remains an exported ephemeral Kubernetes kubeconfig; this wording does not authorize additional provider integrations.

## Intelligence and reporting

Tenant does not own a second Intelligence engine or export subsystem.

- Tenant Governance findings are selected from the canonical Intelligence Recommendations authority using `kubernetes.tenant.*` rule keys.
- PDF, XLSX, and CSV publication is routed through the canonical Reports publication lifecycle from #655.
- Missing/stale evidence remains explicit; absence of provider/capacity evidence is never converted into a healthy or zero value.

## Final UAT boundary

Native-provider acceptance is mandatory. Final UAT must exercise, as applicable:

1. Expand/collapse the Tenant parent and verify Overview, Tenants, Resource Profiles, Namespace Provisioning, and Operations active states on desktop/mobile.
2. Tenant/environment creation.
3. Resource Profile and governed namespace provisioning.
4. Membership and Access Grant creation/revocation.
5. Human JumpServer credential issuance and lifecycle.
6. CI/CD Deployer identity issuance.
7. Namespace Access metadata without secret exposure.
8. Managed-resource, policy, provider-state, Activity, and Kubernetes audit evidence inspection.
9. Tenant Governance findings and capacity admission evidence.
10. Representative Tenant Governance PDF/XLSX/CSV generation and human artifact review.
11. Native Tenant decommission end-to-end: freeze mutations, revoke credentials/grants/memberships, remove managed state, observe each namespace absent (including a controlled Terminating/finalizer blocker case), verify final provider cleanup, and recreate the same cluster+slug as a new generation while historical evidence remains queryable.
12. Baseline Capsule decommission: create a KAORI-managed Capsule Tenant with no namespace/access/provider residue, request Decommission, verify the authoritative Capsule Tenant CR is deleted by Capsule authority and observed absent, then confirm the historical KAORI Tenant reaches Decommissioned. Also prove adopted/degraded/residue-bearing Capsule cases remain blocked.
13. Managed Namespace provider-loss recovery: delete a KAORI-managed Namespace directly in Kubernetes, confirm Discovery shows **Provider Missing**, collect fresh Inventory + run Tenant sync to commit **Drifted**, verify sync itself does not recreate anything, then use **Operations → Drift & Reconcile → Reconcile** to restore Namespace + ResourceQuota + LimitRange from committed intent.
14. Legacy Native allocation governance cutover: discover/adopt an existing Namespace with provider-owned ResourceQuota / LimitRange, verify **Adopted Baseline · Observed** preserves source UID/resourceVersion and has no KAORI desired hash, select a governed Resource Profile, prove capacity/ownership preflight, mutate through Native authority, read back the effective allocation, and only then verify allocation control becomes **KAORI Managed** while Namespace lifecycle ownership remains **Adopted**. Repeat with stale/out-of-band provider evidence and prove cutover fails closed without changing KAORI desired intent.
15. Legacy Capsule allocation cutover boundary: adopt a compatible Capsule Tenant and verify allocation authority is identified from admitted Capsule/native evidence. When no admitted Capsule mutation path exists, the UI remains **Control Unavailable** and KAORI performs no Native quota bypass.
16. Native managed-allocation drift: after a Native allocation is **KAORI Managed**, change ResourceQuota and/or Container LimitRange directly in Kubernetes while KAORI is not performing the mutation. Run Tenant Sync and verify the Namespace becomes **Drifted**, the last KAORI intent and current provider observation are both retained, dimension-level differences are visible, and sync performs no corrective provider write.
17. Bidirectional allocation recovery: use the reference legacy Tenant/project **API** with existing owner/principal **APE** after allocation control is KAORI Managed. Change the live allocation manually during a simulated KAORI outage, run Tenant Sync, then verify **Reapply KAORI Intent** uses the current live provider allocation as the capacity-preflight current state, rechecks provider freshness before mutation, writes through Native authority, and clears drift only after read-back verification. Repeat the scenario and verify **Accept Provider State** performs policy/capacity/ownership validation, performs no redundant provider write, commits the live values as new desired/effective intent with provenance, and clears drift. Change the provider again between sync and either action and prove the action fails closed as stale.
18. Capsule GlobalResourceQuota governance: adopt the reference **API / APE** Capsule Tenant with exactly one authoritative `GlobalResourceQuota`, healthy Capsule authority, served `capsule.clastix.io/v1beta2`, and committed `shared_global_quota=available`. Verify the shared quota is counted once across correlated Namespaces, Cut Over Governance mutates only the authoritative GlobalResourceQuota, provider UID/resourceVersion and selector/tenant correlation remain preserved, and provider read-back is required before the shared allocation becomes **KAORI Managed**.
19. Capsule shared-allocation drift: after GlobalResourceQuota governance is managed, change the GlobalResourceQuota directly during a simulated KAORI outage, run Tenant Sync, and verify committed **Drifted** evidence retains KAORI intent plus provider observation. Prove **Reapply KAORI Intent** and **Accept Provider State** both use Capsule authority, apply shared-capacity admission, reject stale provider observations, and never write namespaced Native ResourceQuota as a substitute.
20. Capsule GlobalResourceQuota unsupported-authority boundary: repeat adoption with multiple/ambiguous GlobalResourceQuota sources, degraded `shared_global_quota`, unsupported selectors/dimensions, or an unsupported served API version. Verify the allocation remains **Control Unavailable**, no provider mutation occurs, and the reason is explicit.
21. Legacy Capsule Tenant quota — **estimasi** case: discover/adopt an existing Capsule Tenant whose authoritative allocation is `Tenant.spec.resourceQuotas` with no proven Namespace correlation and `scope=Tenant`. Verify Adoption Preflight is decision-first: **Adoption Decision**, **Adoption Impact**, **Allocation Overview**, **Namespace Coverage**, and **Technical Evidence** make the read-only boundary explicit. The primary action is **Adopt as Observed** and must state **No provider mutation**. **Observed · Read Only** is shown only when the live served Tenant CRD schema proves `spec.resourceQuotas` and the capability is available. Adopt without provider mutation, then perform explicit governance cutover, capacity admission, Tenant CR resourceVersion check, patch only `spec.resourceQuotas`, provider read-back, and confirm allocation becomes **KAORI Managed** while Tenant ownership remains **Adopted**.
22. Legacy Capsule Tenant quota — **partner** case: adopt a Tenant with correlated Namespace `partner-pgnpartner-development`, authoritative `Tenant.spec.resourceQuotas`, and a Capsule-generated `PersistentVolumeClaim` LimitRange. Verify KAORI maps the PVC LimitRange as a known **PVC Storage Constraint** with Namespace, LimitRange identity, provider UID/resourceVersion, and supported storage min/max evidence when present. It must appear under **Provider Constraints** as **Observed · Preserved**, must not be reported as a raw unsupported `type=PersistentVolumeClaim`, must not become Tenant-quota authority, and must remain untouched while the admitted Tenant quota is cut over and later changed through KAORI.
23. Capsule Tenant quota bidirectional recovery: after #773 allocation control is **KAORI Managed**, change `Tenant.spec.resourceQuotas` directly during a simulated KAORI outage. Run Tenant Sync and prove it performs no write, commits **Drifted** evidence with desired/provider values plus Tenant UID/resourceVersion, then exercise **Reapply KAORI Intent** and **Accept Provider State** separately. Reapply must use fresh live allocation for capacity admission and require provider read-back; Accept must perform no provider write and commit the live quota/scope with `provenance=accepted_provider_state`. Change the Tenant CR again between Sync and either action and prove stale resourceVersion/hash fails closed.
24. Capsule Tenant quota safety boundaries: prove non-empty `scopes` / `scopeSelector`, unsupported authoritative hard dimensions, ambiguous duplicated quota dimensions, competing allocation authority, degraded Capsule, missing `spec.resourceQuotas` CRD schema, and incompatible API versions remain **Control Unavailable**. No path may fall back to namespaced Native ResourceQuota mutation.
25. Discovery performance boundary: open, filter, and paginate **Tenant Discovery** and verify the registry performs candidate enumeration only; ResourceQuota/LimitRange, Capsule allocation authority, GlobalResourceQuota, and Capsule CRD capability inspection must not run per visible row. Click **Review Adoption** and verify exactly that selected candidate receives the deep live HTMX preflight, with a visible fail-closed error state if revalidation fails. Submit **Adopt as Observed** and verify adoption performs a new live provider/conflict revalidation instead of trusting the preflight response.
26. Offline committed-read boundary: complete at least one Tenant sync, record the committed snapshot cutoff/coverage, then make the Kubernetes API unreachable. Open **Tenants**, **Resource Profiles**, **Namespace Provisioning**, and **Operations** and verify committed KAORI content still renders immediately. **Tenant Collection Snapshot** must retain the last committed evidence, any explicit Live Provider Connectivity probe (via its existing supported endpoint) must report its own reachability state, independent of the committed snapshot; child pages must have no probe panel or action, Resource Profile/capacity committed evidence must remain visible for registered clusters, and provider-backed mutations must continue to fail closed. Repeat with no successful Tenant sync and prove **Not Collected** is distinct from provider connectivity failure.
27. Light/dark, responsive, loading/empty/error/degraded, keyboard/focus, and normal KAORI not-found behavior for unsupported Tenant URLs.

Capsule UAT is capability-conditional and must record the exact compatible Capsule evidence when available. Fixture-only Capsule state is not acceptance evidence.

Promotion to `main` is outside this issue. Accepted Tenant work remains in `kaori/staging` until the governed release/promotion flow.
