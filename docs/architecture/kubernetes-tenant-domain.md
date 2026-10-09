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
