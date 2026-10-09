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

## Tenant Operations — Drift & Reconcile navigation (#960)

The `Tenant → Operations → Drift & Reconcile` page uses the existing URL-owned KAORI Content Tabs:
`drift_view=allocation` (default) and `drift_view=operations`. Each inner view shows **two primary paginated registries**:
- **Allocation Drift**: Capsule Tenant Quota Drift and Capsule Shared Allocation Drift.
- **Operational Reconcile**: Namespace & Allocation Drift and Access Reconciliation. The additional **Provider Authority** registry remains available behind a native, collapsed `View Provider Authority` disclosure to avoid crowding the primary workspace; it is not removed or copied.

The outer `tab=drift-reconcile` remains canonical. All five original registry owners retain their independent page-size/filter/query parameter namespaces, canonical empty pagination footers, provider-authoritative evidence and explicit human recovery actions. Inner tab changes reuse the shared server/HTMX tab component; no client-side parallel state controller or background provider mutation is introduced. Query state keeps the selected `drift_view` on paging, filtering and clearing. The provider-authority disclosure remains additional read-only context.

Local human acceptance must exercise both inner views under empty and populated datasets, independent Rows/page controls, HTMX and browser back/forward, light/dark/responsive. This documentation is not staging/UAT acceptance evidence.
