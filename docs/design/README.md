# KAORI UI Documentation

## Start Here

- `KAORI_STYLING_GUIDE.md` — practical implementation and page-review guide.
- `KAORI_DESIGN_SYSTEM.md` — authoritative global visual and interaction contract.

The Styling Guide selects the correct reusable component. The Design System and component documents define the detailed visual contract. Domain specifications may define content and behavior but may not override shared component geometry or tokens.

## Component Contracts

- `components/HERO.md`
- `components/TYPOGRAPHY.md`
- `components/COLOR_AND_SEMANTIC.md`
- `components/BUTTON.md`
- `components/TABLE_AND_LABEL.md`
- `components/TECHNICAL_VALUE.md`
- `components/PAGINATION.md`
- `components/TAB_STYLES.md`
- `components/WORKSPACE_TABS.md`
- `components/SEGMENTED_TABS.md`
- `components/VISUALIZATION_WORKSPACE.md`
- `components/TOPOLOGY_PALETTE.md`
- `components/OPERATIONAL_SECTION_CARD.md`
- `components/RESOURCE_POSTURE_GRID.md`
- `components/SNAPSHOT_CONTEXT_BAR.md`
- `components/INVENTORY_ASSET_CARD.md`
- `components/SIDE_DRAWER.md`
- `components/DETAIL_STYLES.md`
- `components/EXPANDED_INVENTORY_DETAIL.md`
- `components/OPERATIONAL_CALLOUT.md`
- `components/OPERATIONAL_FLOW_STEPS.md`
- `components/FORECAST_PROJECTION_CHART.md`
- `components/ANALYTICS_ANALYSIS_SURFACES.md`
- `components/ANALYTICS_RESOURCE_UTILIZATION.md`
- `components/ANALYTICS_STORAGE_ANALYSIS.md`
- `components/ANALYTICS_WORKLOAD_ANALYSIS.md`
- `components/ANALYTICS_RESOURCE_FORECAST.md`
- `components/ANALYTICS_TOP_CONSUMERS.md`
- `components/ANALYTICS_ALERTS_ANOMALIES.md`
- `components/ANALYTICS_PROMETHEUS_READINESS.md`
- `components/SECTION_HEADER_ACTION.md`
- `components/PEER_CONTENT_GRID.md`
- `components/RIGHT_CONTEXT_RAIL.md`
- `components/LOADING.md`
- `components/INFO_FLOW.md`
- `components/RELATED_PAGE_CARD.md`
- `components/VIEW_MORE_CONTENT.md`
- `components/SIDEBAR_NAVIGATION.md`
- `components/FORM_ACTION_BAR.md`
- `components/CONNECTION_VALIDATION_HEADER.md`
- `components/OPERATIONAL_TOGGLE.md`
- `components/CONTEXT_GUIDANCE_CARD.md`
- `components/INFORMATION_GUIDE_CARD.md`
- `components/WORKSPACE_SUMMARY_CARD.md`
- `components/WORKSPACE_LINK_CARD.md`
- `components/HEALTH_INTERPRETATION.md`
- `components/INTEGRATION_MANAGE_WORKSPACE.md`
- `components/INTEGRATIONS_WORKSPACE_STANDARD.md`
- `components/OPERATIONAL_ACTION_FEEDBACK.md`
- `components/OPERATIONAL_WORKFLOW_CARD.md`
- `components/STRUCTURED_ENTRY_EDITOR.md`
- `components/PROTECTED_VALUE_PANEL.md`

## Reusable Page Patterns

- `patterns/INVENTORY_AND_OPERATIONAL_PAGES.md`
- `patterns/WELCOME_WORKSPACE_CATALOG.md`
- `patterns/OPERATIONAL_DASHBOARD.md`
- `patterns/KUBERNETES_INVENTORY_OVERVIEW.md`
- `patterns/INVENTORY_RESOURCE_PAGE.md`
- `patterns/KUBERNETES_NODE_INVENTORY.md`
- `patterns/KUBERNETES_TOPOLOGY.md`
- `patterns/KUBERNETES_STORAGE_CONFIGURATION_INVENTORY.md`
- `patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md`

- `components/ANALYTICS_GUIDANCE_CALLOUT_STANDARD.md` — canonical icon-led How To Read, What To Do, Operational Reading, and Recommended Action presentation across Kubernetes Analytics.

## Domain Specifications

Domain-specific UI rules live under `docs/modules/` or the owning module README. They may define page content, columns, metrics, actions, and provider workflows, but they may not override global tokens or shared component geometry.

## Documentation Placement Rule

- Applies everywhere → global Design System or Styling Guide.
- Applies to one reusable component → component standard.
- Applies to several modules with the same structure → page pattern.
- Mentions a provider, object type, route, column, metric, or domain action → module specification.

## Current Baseline Audit

- `audits/ANALYTICS_GUIDANCE_CALLOUT_AUDIT_20260801.md` — full Kubernetes Analytics guidance consistency audit and disposition.

- `audits/KAORI_STYLING_BASELINE_AUDIT_2026_07.md`
- `audits/WELCOME_STYLING_AUDIT_2026_07.md`
- `audits/KUBERNETES_OPERATIONS_DASHBOARD_STYLING_AUDIT_2026_07.md`
- `audits/KUBERNETES_INVENTORY_OVERVIEW_STYLING_AUDIT_2026_07.md`
- `audits/KUBERNETES_NODE_INVENTORY_STYLING_AUDIT_2026_07.md`
- `audits/KUBERNETES_NODE_INVENTORY_ALIGNMENT_AUDIT_2026_08.md`
- `audits/KUBERNETES_TOPOLOGY_STYLING_AUDIT_2026_07.md`
- `audits/PROMETHEUS_STYLE_AND_LIFECYCLE_AUDIT_2026_07.md`
- `audits/PROMETHEUS_ALERTMANAGER_ALIGNMENT_AUDIT_2026_07.md`
- `audits/PROMETHEUS_MANAGE_ALERTMANAGER_PARITY_AUDIT_2026_07.md`
- `audits/PROMETHEUS_ALERTMANAGER_HTMX_AND_REGISTRY_AUDIT_2026_07.md`

- `components/TECHNICAL_METADATA_COLLECTION.md` — dense Kubernetes key/value metadata.
- `components/RELATED_RESOURCE_COLLECTION.md` — peer related-resource evidence without timeline geometry.

- `patterns/KUBERNETES_NAMESPACE_INVENTORY.md` — canonical Namespace Inventory composition.
- `patterns/KUBERNETES_WORKLOAD_INVENTORY.md` — canonical Workload Inventory composition.

- `audits/KUBERNETES_NAMESPACE_INVENTORY_STYLING_AUDIT_2026_07.md` — Namespace Inventory audit record.
- `audits/KUBERNETES_WORKLOAD_INVENTORY_STYLING_AUDIT_2026_07.md` — Workload Inventory audit record.

## Pod Inventory

- [Container Runtime Collection](components/CONTAINER_RUNTIME_COLLECTION.md)
- [Kubernetes Pod Inventory](patterns/KUBERNETES_POD_INVENTORY.md)

## Kubernetes Network Inventory

- [Kubernetes Network Inventory Pattern](patterns/KUBERNETES_NETWORK_INVENTORY.md)
- [Service and Ingress Inventory Audit](audits/KUBERNETES_SERVICE_INGRESS_INVENTORY_STYLING_AUDIT_2026_07.md)

## Storage and Configuration Inventory

- [Expanded Inventory Detail](components/EXPANDED_INVENTORY_DETAIL.md)
- [Storage and Configuration Inventory Pattern](patterns/KUBERNETES_STORAGE_CONFIGURATION_INVENTORY.md)
- [Storage and Configuration Inventory Audit](audits/KUBERNETES_STORAGE_CONFIGURATION_INVENTORY_STYLING_AUDIT_2026_07.md)

## Inventory Detail Workspace

- `components/RESOURCE_DETAIL_MODAL.md` — Detail Style 2, URL state, focus, loading, and maximized modal geometry.
- `components/DETAIL_STYLES.md` — canonical Detail Style registry.

- `audits/KUBERNETES_INVENTORY_HERO_COPY_AUDIT_2026_07.md` — Inventory hero copy-density audit and guardrail.

## Kubernetes ConfigMap and Secret Operations

- `patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md` — live mutation, protected reveal, and delete-confirmation pattern.
- `audits/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS_STYLING_AUDIT_2026_07.md` — operation workspace and Inventory modal remediation record.

- `audits/KUBERNETES_OPERATIONS_LAYOUT_REFINEMENT_AUDIT_2026_07.md` — ConfigMap/Secret workspace density, selection, action placement, and TLS flow refinement.

- `audits/KUBERNETES_OPERATIONS_DARK_MODE_CATALOG_REFINEMENT_AUDIT_2026_07.md` — dark-mode interaction, flat workflow catalog, Secret Type selection, and delete OOB ownership.
- `components/OPERATIONAL_WORKFLOW_CARD.md` — shared flat workflow catalog shell and destination-row contract.

- `patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md` — Governance Resource Registry, certificate validity policy, host coverage, collection evidence, and Secret Operations handoff.
- `components/OPERATIONAL_POINT_FLOW.md` — compact ordered supporting flow without nested step cards.
- `audits/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE_STYLING_AUDIT_2026_07.md` — TLS Governance correctness, styling, permission, and collection-boundary decisions.

- `components/ANALYTICS_CAPACITY_ANALYSIS.md` — cluster-level Ready-worker capacity, unavailable metric, risk, and review-path contract.

## Audit Reports

- `audits/INTEGRATIONS_FULL_AUDIT_20260731.md`
- `audits/KAORI_ANALYTICS_STORAGE_AUDIT_2026_08.md` — Storage evidence, lifecycle, HTMX, and report-boundary audit.
- `audits/KAORI_ANALYTICS_WORKLOAD_AUDIT_2026_08.md` — Active-Pod, ResourceQuota-object, materialization, HTMX, and code-ownership audit.
- `audits/KAORI_ANALYTICS_FORECAST_AUDIT_2026_08.md` — Ready-worker evidence, peak projection, bounded ETA, materialization identity, chart alignment, report parity, and legacy-route audit.
- `audits/KAORI_ANALYTICS_TOP_CONSUMERS_AUDIT_2026_08.md` — Active-consumer evidence, Ready-worker denominators, exact Namespace scope, HTMX transport, report parity, and legacy-route audit.
- `audits/KAORI_ANALYTICS_ALERTS_AUDIT_2026_08.md` — Alert-source fallback, HA deduplication, active-Pod anomaly evidence, partial-source semantics, independent pagination, committed report, and Overview parity audit.
