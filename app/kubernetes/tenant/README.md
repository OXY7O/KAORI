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

### Resource Profile lifecycle

Resource Profile administration preserves the approved #113 allocation authority:

- **Small / Standard / Large** are KAORI-owned locked presets. Normal operator workflows do not edit or delete them. Their preset name + version is a stable contract identity; mutating a built-in in place would make historical Namespace snapshots, Capacity Decisions, audit evidence, and cross-environment reproduction ambiguous.
- When a preset is close but not exact, create a **Custom** profile from that Base Preset. KAORI retains the base preset class/version as lineage while the Custom contract owns its independent future versions.
- **Custom** profiles are operator-managed. Edit may change name, description, enabled state, quota, and Container LimitRange values.
- A Custom allocation-contract change increments the profile version. Existing Namespace allocations keep their already committed source version and frozen effective allocation snapshot until an explicit governed allocation change.
- **Hard Delete** is limited to Custom profiles with **zero Namespace references and zero Capacity Decision references**. Both active and historical references count as dependencies so deletion cannot break committed allocation/audit lineage.
- Disable is available through Custom Edit to stop future selection without removing the profile record.

Namespace Provisioning and Operations follow the same KAORI page hierarchy established by Tenant and Resource Profiles: **Snapshot → Estate → Workspace → focused Content Tabs**. Namespace Provisioning separates Provision Namespace, Allocation Change, and Capacity Decisions while the Namespace Registry uses canonical filters and default-five pagination. Operations separates Provisioning, Runs & Evidence, Drift & Reconcile, and Activity without creating third-level sidebar destinations.

Operations task views stay inside the page so the sidebar remains exactly two interactive levels. Only the five approved Tenant destinations are supported; superseded workspace routes are not retained.

## Evidence and provider authority

Normal Tenant workspace reads are composed from committed KAORI state. Live provider calls remain inside the owning mutation/reconciliation adapters, plus the explicitly live Tenant connection/discovery surfaces described below.

### Native Kubernetes prerequisite rendering

Native Kubernetes remains the mandatory baseline for Tenant workflows. When no Ready Native Kubernetes cluster is available, Tenant uses the same **general Kubernetes prerequisite grammar** as Dashboard, Inventory, Operations, and Governance: the Hero keeps stable page identity and metadata, its right side renders `components/cluster/_hero_blocked_context.html` without a duplicate action, and the shared `components/cluster/_onboarding_banner.html` immediately below owns the canonical remediation sequence `Open Cluster Integrations → Register Cluster → Run Sync`. Page-specific Tenant operational content remains terminal/hidden beneath that blocker. Once a Ready Native Kubernetes cluster exists, the normal Overview, Tenants, Resource Profiles, Namespace Provisioning, or Operations content is rendered unchanged.

This is a presentation boundary only. It does not add a live provider read, mutate Kubernetes state, or replace the existing committed-state authority.

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

Non-Overview Tenant pages use a shared **Tenant Collection Snapshot** directly below the page Hero. This is not the Overview worker-generated snapshot and has no cadence. It performs a short live Kubernetes API reachability probe on the page request. Tenant administration HTMX mutations also return an out-of-band refresh of this connection bar, so the displayed connection status can change immediately after a provider-backed operation. If the page stays idle, no polling or worker schedule runs; the displayed timestamp remains the last page/operation check.

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

Tenant Setup supports two direct-create provider paths while retaining one provider-neutral UI. **Native Kubernetes** creates the KAORI Tenant boundary without a first-class Kubernetes Tenant object; Namespace resources are introduced later by Namespace Provisioning. **Capsule** performs its live supported-CRD/capability and admission preflight when **Add Tenant** is submitted, requires both an initial Owner Kind and Owner Subject, dry-runs the exact Tenant CR, then creates the authoritative Capsule Tenant CR before committing KAORI provider evidence. Existing Capsule Tenant CRs are never overwritten and continue through **Discovery → Adoption**.

`Memberships` separates three peer actions (add user, create group, add group membership) from scalable registries. Successful administration mutations progressively refresh only the Tenant Workspace through HTMX rather than forcing a full-page navigation/scroll reset. Membership and Tenant Group data each use canonical filtered/paginated tables instead of fixed recent-item lists.

`Access Grants` keeps one full-width multi-column form above the canonical Access Grant Registry. The registry owns all committed/effective RBAC evidence, filters, pagination, and Inspect/Reconcile/Revoke actions.

`Credentials` presents Human and CI/CD issuance as symmetric peer forms. Credential Lifecycle is a canonical registry table with filters, pagination, validity, reconciliation state, lifecycle actions, and protected material-generation actions. Desktop layout uses a compact fixed-width column contract so normal KAORI desktop widths do not require horizontal scrolling; narrow viewports may still use controlled table overflow. Routine registry/detail surfaces never render secret material. Explicit material generation opens a non-cacheable one-time view; KAORI does not persist the returned token or kubeconfig body.

`Namespace Access` is a derived non-secret read model presented as a canonical registry with Tenant/Environment/Credential filters and pagination.

All tabs reuse the Analytics-derived `components/content_tabs.html` server-link mode. Every tab retains a real URL fallback while HTMX replaces only the Tenant Workspace. Mutation routes return operators to the relevant section.

Tenant identity is immutable after creation in the normal operator workflow.

- **Create** — create the Tenant ownership boundary and initial environment.
- **Read** — Tenant Registry is the committed-state source for operator reads.
- **Update** — no inline Tenant identity update is exposed. Name/slug identity, cluster placement, provider authority, and reconciliation authority are intentionally locked.
- **Lifecycle removal** — #735 owns governed teardown. Tenant Registry exposes asynchronous **Decommission** and preserves one ordered lifecycle: freeze new mutations → revoke access state → retire memberships/groups → remove admitted managed resources/namespaces → retire reservation/exposure state → provider verification → commit `decommissioned`.
- **Provider verification** — a successful provider `DELETE` request is not completion. Native Namespace teardown observes Kubernetes until absence and never strips finalizers automatically. Capsule teardown likewise commits completion only after the authoritative Capsule Tenant CR is verified absent.
- **Capsule authority** — baseline Capsule teardown is admitted only for **KAORI-created, Managed, healthy Capsule Tenant CRs with zero active namespace/access/credential/managed-resource residue**. The adapter validates KAORI ownership labels, Tenant generation, and provider UID before deleting the Capsule CR, then verifies absence. Adopted/foreign Capsule objects, degraded Capsule state, active namespaces, or other unsupported provider residue remain fail-closed; KAORI never falls back to Native deletion.
- **Historical identity** — decommission retains the historical Tenant row, evidence, memberships, grants, credentials, and correlation lineage. Re-creating the same cluster+slug creates the next Tenant generation rather than overwriting history.
- **Name and namespace reuse** — the same Tenant slug may exist independently on different clusters. After a Tenant is fully Decommissioned, the same cluster+slug may be recreated as the next Tenant generation. A previously managed namespace name may likewise be reused on the same cluster only after the earlier namespace generation is provider-verified Deprovisioned; active duplicates remain fail-closed.
- **Structural change** — when immutable identity or placement must change, use governed teardown + recreation rather than mutating the Tenant in place.

#734 still prohibits a database-only lifecycle flag change from being presented as provider decommission; the final lifecycle transition now occurs only after the #735 provider verification path succeeds.

### Provider Discovery and Adoption

#736 owns the two-way Tenant Registry path. Discovery is an explicit live-provider exception to normal committed-state reads: it reads Native Kubernetes namespaces and Capsule Tenant CRs on the Discovery request, shows provider status, correlates objects already governed by KAORI, and classifies candidates as **Managed**, **Discovered**, or **Blocked**. It does not wait for the Overview inventory worker sync. Discovery itself never mutates provider state.

Manual provider deletion is treated as drift, not implicit Tenant deletion. After a fresh Kubernetes Inventory collection, `kubernetes.tenant.sync` marks a previously Ready managed/adopted Namespace as **Drifted** only when the inventory cutoff is at least as new as the Namespace's last KAORI-side provider evidence. The observation path never recreates or deletes resources automatically. **Operations → Drift & Reconcile** exposes explicit **Reconcile** only for KAORI-managed Native namespaces with Native reconciliation authority; it replays committed desired intent to restore/verify the Namespace, ResourceQuota, and LimitRange before returning the record to Ready. Adopted namespaces never receive this ownership-taking shortcut and remain drifted until the provider object is restored/reviewed or the Tenant is governed through teardown.

Explicit adoption is a separate human-confirmed mutation over KAORI committed state. The Adoption Preflight shows provider identity, live status, provider authority, current ownership, proposed KAORI mapping, and governance checks. Submission revalidates the live provider object and conflicts before committing an **Adopted** Tenant. Native namespace adoption references the existing Namespace without creating/patching/deleting it; Capsule adoption registers the existing Capsule Tenant while Capsule remains reconciliation authority. Adoption evidence records `provider_mutation_performed=false`.

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
14. Light/dark, responsive, loading/empty/error/degraded, keyboard/focus, and normal KAORI not-found behavior for unsupported Tenant URLs.

Capsule UAT is capability-conditional and must record the exact compatible Capsule evidence when available. Fixture-only Capsule state is not acceptance evidence.

Promotion to `main` is outside this issue. Accepted Tenant work remains in `kaori/staging` until the governed release/promotion flow.
