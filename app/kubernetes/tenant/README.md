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

Operations task views stay inside the page so the sidebar remains exactly two interactive levels. Only the five approved Tenant destinations are supported; superseded workspace routes are not retained.

## Evidence and provider authority

Normal Tenant workspace reads are composed from committed KAORI state. Live provider calls remain inside the owning mutation/reconciliation adapters.

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

`Tenant Setup` combines the create form with a non-collapsible governance flow so the operator sees the required order: Tenant → Namespace → Membership → Access Grant → Credential. Important boundaries use icon-backed tiles plus a persistent warning row. Dense field guidance uses the shared `components/info_tip.html` hover/focus pattern instead of repeating helper paragraphs under controls.

`Memberships` separates three peer actions (add user, create group, add group membership) from scalable registries. Successful administration mutations progressively refresh only the Tenant Workspace through HTMX rather than forcing a full-page navigation/scroll reset. Membership and Tenant Group data each use canonical filtered/paginated tables instead of fixed recent-item lists.

`Access Grants` keeps one full-width multi-column form above the canonical Access Grant Registry. The registry owns all committed/effective RBAC evidence, filters, pagination, and Inspect/Reconcile/Revoke actions.

`Credentials` presents Human and CI/CD issuance as symmetric peer forms. Credential Lifecycle is a canonical registry table with filters, pagination, validity, reconciliation state, and lifecycle actions. Desktop layout uses a compact fixed-width column contract so normal KAORI desktop widths do not require horizontal scrolling; narrow viewports may still use controlled table overflow. Secret material is never rendered.

`Namespace Access` is a derived non-secret read model presented as a canonical registry with Tenant/Environment/Credential filters and pagination.

All tabs reuse the Analytics-derived `components/content_tabs.html` server-link mode. Every tab retains a real URL fallback while HTMX replaces only the Tenant Workspace. Mutation routes return operators to the relevant section.

Tenant identity is immutable after creation in the normal operator workflow.

- **Create** — create the Tenant ownership boundary and initial environment.
- **Read** — Tenant Registry is the committed-state source for operator reads.
- **Update** — no inline Tenant identity update is exposed. Name/slug identity, cluster placement, provider authority, and reconciliation authority are intentionally locked.
- **Lifecycle removal** — #735 owns governed teardown. The current review candidate exposes an asynchronous **Decommission** action from Tenant Registry and executes the Native sequence: freeze new Tenant mutations → revoke credentials → revoke Access Grants → retire memberships/groups → remove admitted managed resources → deprovision KAORI-managed namespaces → retire reservation/exposure state → verify Native provider absence → commit `decommissioned`.
- **Provider verification** — a successful Kubernetes `DELETE` request is not completion. KAORI observes the Namespace until Kubernetes returns absence; `Terminating`, timeout, and remaining finalizers are committed as blockers and leave the Tenant frozen for explicit retry. KAORI never strips Namespace finalizers automatically in this path.
- **Capsule authority** — a Capsule-authoritative Tenant fails closed unless an admitted Capsule teardown adapter owns the deletion. The current candidate deliberately does **not** bypass Capsule with direct Native deletion; Capsule E2E teardown remains an acceptance dependency for #735 when Capsule authority is qualified.
- **Historical identity** — decommission retains the historical Tenant row, evidence, memberships, grants, credentials, and correlation lineage. Re-creating the same cluster+slug creates the next Tenant generation rather than overwriting history.
- **Structural change** — when immutable identity or placement must change, use governed teardown + recreation rather than mutating the Tenant in place.

#734 still prohibits a database-only lifecycle flag change from being presented as provider decommission; the final lifecycle transition now occurs only after the #735 provider verification path succeeds.

### Provider Discovery and Adoption

#736 owns the two-way Tenant Registry path. The first admitted review slice is **live and read-only**: KAORI reads Native Kubernetes namespaces and Capsule Tenant CRs, shows their live provider status, correlates objects already governed by KAORI, and classifies unowned candidates as Managed, Adoptable, or Blocked. Discovery never mutates provider state. Explicit governed adoption remains a separate mutation step under #736.

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

Routine Tenant pages must never render bearer tokens, generated kubeconfig content, certificate/private-key material, or registry Secret material.

Human access issuance uses the admitted #115 service and binds an individually owned reconciled User Access Grant to a non-secret JumpServer reference. CI/CD issuance uses the admitted #116 Deployer service and creates a namespace-scoped machine principal/grant/credential lineage.

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
12. Light/dark, responsive, loading/empty/error/degraded, keyboard/focus, and normal KAORI not-found behavior for unsupported Tenant URLs.

Capsule UAT is capability-conditional and must record the exact compatible Capsule evidence when available. Fixture-only Capsule state is not acceptance evidence.

Promotion to `main` is outside this issue. Accepted Tenant work remains in `kaori/staging` until the governed release/promotion flow.
