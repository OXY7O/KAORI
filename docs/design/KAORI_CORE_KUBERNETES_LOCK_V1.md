# KAORI Core Kubernetes Lock v1

Status: Final Lock v1
Date: 2026-08-08

## Locked Scope

This lock freezes the six core user-facing KAORI workspaces below:

1. Welcome
2. Kubernetes Dashboard
3. Kubernetes Inventory
4. Kubernetes Analytics
5. Kubernetes Operations
6. Kubernetes Governance

Integrations has its own independent final lock in `KAORI_INTEGRATIONS_LOCK_V1.md` and is not redefined here.

## Frozen Shared UI Contract

- KAORI Violet remains the identity and interaction color. Semantic colors represent operational state only.
- Light mode and dark mode use shared semantic tokens; page-local raw palette/hex styling is not allowed.
- Visible headings, tabs, filter labels, form labels, table headers, modal titles, and actions use Title Case.
- Canonical tables use shared table primitives, left-aligned data, right-aligned action columns, and resource-aware pagination.
- Default table page size is 5. Allowed choices are 5 / 10 / 25 / 50.
- Compact state labels use the shared rectangular `rounded-md` contract and semantic-dot indicators where state is repeated.
- Loading feedback is owned by shared KAORI loading components and real async/HTMX state where applicable; page-local fake timers are not accepted.
- Modal/drawer behavior is owned by shared components and shared JavaScript. Page-local modal shells are not introduced without a documented exception.
- Toast feedback and countdown behavior remain script-owned and reusable.
- No silent increase of UI-style debt is allowed inside the locked scope.

## Welcome

Welcome remains the product entry workspace. It must keep shared Hero ownership, consistent KAORI typography, contextual Violet domain grouping, and links that route into canonical workspaces rather than compatibility pages.

## Kubernetes Dashboard

The Kubernetes Dashboard remains a committed-snapshot operational overview. Its composition is governed by the Operational Dashboard standard. Snapshot freshness, health, capacity, alerts, forecast risk, top consumers, and recommended actions remain separate evidence summaries. The removed `snapshot_builder.py` compatibility path must not return.

## Kubernetes Inventory

Inventory remains committed-snapshot first. Overview, Nodes, Namespaces, Configuration, Workloads, Pods, Services, Ingresses, Storage, and Topology use canonical page workspaces. Legacy `_inventory_scope.html` wrappers remain removed. Topology stays canvas-first and controls/details remain on-demand drawers at every breakpoint.

## Kubernetes Analytics

Analytics keeps one shared visual-role system and shared analysis surfaces. Overview, Utilization, Capacity, Storage, Workload, Forecast, Top Consumers, and Alerts & Anomalies remain committed-worker evidence workspaces. Long technical detail belongs in detail surfaces/modals rather than dense primary tables. Quantitative magnitude uses KAORI Violet; semantic state uses semantic colors.

## Kubernetes Operations

ConfigMap and Secret management remain guarded live Kubernetes operations. Validation evidence remains persistent before mutation. Operational feedback uses the shared toast/notification delivery path. Secret reveal remains permission/allow-list gated and must not leak sensitive values into audit/notification persistence.

## Kubernetes Governance

TLS Certificate Governance keeps snapshot-backed registry evidence and controlled live rotation. Certificate/private-key validation, resource-version mutation, auditability, and governed notification delivery remain mandatory. Obsolete TLS feedback and inventory wrappers remain removed.

## Legacy / Dead-Code Policy

The final lock preserves the canonical cleanup registry in `scripts/cleanup_obsolete_files.sh`. Removed compatibility wrappers, obsolete dashboard builders, obsolete Analytics JavaScript, old Operations wrappers, old Governance feedback fragments, and old Inventory topology/bootstrap/scope wrappers must not be reintroduced.

## Verification

Run:

```bash
python scripts/verify_core_kubernetes_final_lock.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_core_workspace_legacy_cleanup.py
python scripts/verify_core_workspace_code_health.py
python scripts/verify_operational_dashboard_standard.py
python scripts/verify_tls_certificate_governance_standard.py
python scripts/verify_dark_mode_standard.py
```

Domain contract suites remain additional release gates.

## Change Policy

Any structural visual change after this lock requires documentation, audit rationale, verifier/contract changes, and regression evidence in the same commit. Minor defects may be fixed without reopening the design baseline when they preserve this contract.
