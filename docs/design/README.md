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
- `components/OPERATIONAL_ACTION_FEEDBACK.md`

## Reusable Page Patterns

- `patterns/INVENTORY_AND_OPERATIONAL_PAGES.md`
- `patterns/WELCOME_WORKSPACE_CATALOG.md`
- `patterns/OPERATIONAL_DASHBOARD.md`
- `patterns/KUBERNETES_INVENTORY_OVERVIEW.md`
- `patterns/INVENTORY_RESOURCE_PAGE.md`
- `patterns/KUBERNETES_TOPOLOGY.md`
- `patterns/KUBERNETES_STORAGE_CONFIGURATION_INVENTORY.md`

## Domain Specifications

Domain-specific UI rules live under `docs/modules/` or the owning module README. They may define page content, columns, metrics, actions, and provider workflows, but they may not override global tokens or shared component geometry.

## Documentation Placement Rule

- Applies everywhere → global Design System or Styling Guide.
- Applies to one reusable component → component standard.
- Applies to several modules with the same structure → page pattern.
- Mentions a provider, object type, route, column, metric, or domain action → module specification.

## Current Baseline Audit

- `audits/KAORI_STYLING_BASELINE_AUDIT_2026_07.md`
- `audits/WELCOME_STYLING_AUDIT_2026_07.md`
- `audits/KUBERNETES_OPERATIONS_DASHBOARD_STYLING_AUDIT_2026_07.md`
- `audits/KUBERNETES_INVENTORY_OVERVIEW_STYLING_AUDIT_2026_07.md`
- `audits/KUBERNETES_NODE_INVENTORY_STYLING_AUDIT_2026_07.md`
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
