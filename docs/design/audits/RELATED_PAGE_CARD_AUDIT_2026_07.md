# Related Page Card Audit — July 2026

## Scope

The audit reviewed cross-page workflow relationships in:

- Roles & Access
- Kubernetes Integrations
- Prometheus Integrations
- Alertmanager Integrations
- Integrations Overview

The goal was to distinguish meaningful workflow relationships from ordinary navigation shortcuts and establish a reusable component based on the Permission Catalog card used by Roles & Access.

## Findings

The Roles & Access page already communicated an important relationship: roles assign permission keys, while Permission Catalog remains the authoritative registry. However, the card was implemented with page-local markup.

The three provider integration pages also have direct downstream KAORI workspaces, but those relationships were not surfaced consistently:

| Current Workspace | Related Workspace | Relationship |
|---|---|---|
| Kubernetes Integrations | Kubernetes Inventory | Validated connections supply normalized resource inventory. |
| Prometheus Integrations | Kubernetes Analytics | Eligible metrics sources power analytics and forecasting workflows. |
| Alertmanager Integrations | Alert Intelligence | Eligible alert sources power correlation and operational review. |

Integrations Overview was not given a Related Page Card because it is itself the navigation and portfolio summary for provider workspaces. Adding another destination card there would duplicate its primary purpose.

## Implementation

A shared macro was added:

```text
app/templates/components/related_page_card.html
```

The Roles & Access Permission Catalog card was migrated to the component.

The component was then applied to:

```text
app/templates/integrations/kubernetes.html
app/templates/integrations/prometheus.html
app/templates/integrations/alertmanager.html
```

Each provider page now places the Related Page Card directly beside its integration context block at the desktop `xl` breakpoint and stacks it below on smaller screens.

## Standardized Relationships

### Roles & Access → Permission Catalog

Clarifies that roles package code-backed permission keys while Permission Catalog remains the authoritative registry.

### Kubernetes Integrations → Kubernetes Inventory

Clarifies that Kubernetes remains authoritative for live resources while KAORI presents normalized inventory, operational context, and history.

### Prometheus Integrations → Kubernetes Analytics

Clarifies that Prometheus remains authoritative for collection and query execution while KAORI applies governed source resolution and operational interpretation.

### Alertmanager Integrations → Alert Intelligence

Clarifies that Alertmanager remains authoritative for routing, grouping, inhibition, silences, and delivery while KAORI provides correlation, prioritization, and review.

## Compliance Result

- Shared Related Page Card component: implemented
- Roles & Access local card markup: migrated
- Kubernetes Integrations relationship: implemented
- Prometheus Integrations relationship: implemented
- Alertmanager Integrations relationship: implemented
- Integrations Overview duplication: intentionally avoided
- Documentation and automated guardrail: implemented
