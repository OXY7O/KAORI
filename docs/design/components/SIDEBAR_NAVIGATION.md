# KAORI Sidebar Navigation Standard v2.0

**Status:** Locked application-shell navigation contract  
**Foundation authority:** #747  
**Implementation authority:** #748

## Purpose

The global sidebar is KAORI's workspace selector. It answers one question:

> **Which major KAORI workspace/domain am I entering?**

It does not expose every capability, page, provider, or resource.

The canonical navigation hierarchy is:

```text
Global Sidebar
  Section -> Workspace

Domain Workspace Navigation
  Workspace -> Capability

Capability / Content Navigation
  Capability -> Detailed view
```

A third level in the global sidebar is prohibited.

## Architecture Rule

Sidebar ownership follows the KAORI architecture principle:

> **capability/domain first, provider second, instance third**

Therefore:

- providers/vendors do not become global sidebar roots;
- provider domains and providers belong inside **Integrations**;
- provider instances/resources belong in context selectors, registries, tables, drawers, and detail pages;
- a new provider must not require global-sidebar restructuring;
- a new detailed view extends its owning workspace rather than adding another sidebar nesting level.

## Visual Geometry

The accepted Violet application-shell geometry remains unchanged from v1.7:

| Element | Contract |
| --- | --- |
| Expanded desktop width | 250 px |
| Collapsed desktop width | 78 px |
| Mobile drawer | off-canvas, nearly full-width on compact phones |
| Root workspace target | minimum 44 px |
| Root label | 16 px / semibold |
| Section label | 12 px / extra-bold uppercase |
| Root icon container | 32 px |
| Active state | canonical Violet surface + active icon treatment |
| Dark mode | neutral-first sidebar surface with restrained Violet emphasis |

Canonical root-link utility ownership remains:

```text
sidebar-parent-link
min-h-11 rounded-lg px-2.5 py-2 text-base font-semibold leading-6
sidebar-parent-active / sidebar-item-idle
sidebar-parent-active-icon / sidebar-item-idle-icon
```

The v2 change is **information architecture**, not a visual rebrand.

## Runtime Section Order

Runtime sections render only when they contain at least one authorized implemented workspace.

Canonical reserved order:

1. Main
2. Infrastructure
3. Operations
4. Assurance
5. Insights
6. Platform
7. Administration

Empty future sections are not rendered.

### Current implemented runtime

```text
MAIN
└── Welcome

INFRASTRUCTURE
├── Kubernetes
└── Object Storage

INSIGHTS
├── Intelligence
└── Reports

PLATFORM
├── Operations Center
└── Integrations

ADMINISTRATION
├── Access
└── Settings
```

### Reserved future ownership

```text
MAIN
└── Operational Overview

INFRASTRUCTURE
├── Compute
└── Network

OPERATIONS
├── Services
└── Reliability

ASSURANCE
├── Backup & Recovery
├── Security Posture
├── Policy & Compliance
└── Secrets & PKI

INSIGHTS
└── FinOps

PLATFORM
└── Automation
```

Reserved ownership does not authorize placeholder navigation. A workspace appears only after a real route, authorization contract, and bounded implementation exist.

## Permission Contract

A root workspace is visible only when at least one child capability is authorized.

The root link resolves to the **first authorized capability**, not blindly to an overview the user cannot access.

Examples:

- Kubernetes Governance-only user -> Governance target;
- Kubernetes ConfigMap-only user -> Operations -> ConfigMaps target;
- Reports generate-only user -> Generate target;
- identity-provider-only administrator -> Access overview through the existing Access authorization contract.

Global navigation must never expose a destination that immediately fails authorization solely because a different child permission was selected as the root target.

## Active-State Contract

Exactly one root workspace may own `aria-current="page"`.

Active ownership follows route/domain semantics:

- Kubernetes owns Dashboard/Inventory/Operations/Governance/Tenant/Kubernetes Analytics;
- Object Storage owns Object Storage Dashboard/Inventory/Object Storage Analytics;
- Intelligence owns Intelligence, Alert Intelligence, and Automation Control;
- Operations Center owns Jobs and Platform Operations;
- Integrations owns integration-domain/provider/connection routes;
- Access owns user/identity-provider/role/permission/audit administration;
- Settings owns general/account settings.

## Mobile / Responsive

The mobile drawer uses the **same Section -> Workspace taxonomy** as desktop.

Requirements:

- no mobile-only information architecture;
- no nested global submenus;
- selecting a workspace closes the drawer;
- drawer state must not mutate persisted desktop collapse state;
- workspace labels are always visible in the mobile drawer;
- page-level horizontal scroll is prohibited.

## Breadcrumb Contract

Breadcrumb root vocabulary matches the visible global workspace:

```text
KAORI / Kubernetes / Inventory / Nodes
KAORI / Kubernetes / Analytics / Capacity
KAORI / Object Storage / Inventory / Buckets
KAORI / Object Storage / Analytics / Forecast
KAORI / Intelligence / Recommendations
KAORI / Operations Center / Jobs
KAORI / Access / Identity Providers
```

Legacy mixed roots such as `Analytics / Kubernetes` or `Inventory / Nodes` are not canonical.

## Provider Boundary

Never add these as global root workspaces merely because a provider is integrated:

- Harbor
- GitHub
- Ansible
- Prometheus
- Alertmanager
- MinIO
- Vault / OpenBao
- VMware
- Proxmox
- Cilium
- NetBox

They remain provider identities inside the owning capability/domain.

## Implementation Ownership

Runtime sidebar model: `app/common/workspace_navigation.py`  
Renderer: `app/templates/components/navigation/sidebar.html`  
Workspace navigation renderer: `app/templates/components/workspace_tabs.html`  
Breadcrumb authority: `app/common/navigation.py`

Legacy submenu templates may remain temporarily during migration but must not be included by the global sidebar after v2 adoption.

## Playwright / Visual QA

Reuse the existing #543 / #224 authority.

At minimum validate:

- expanded desktop sidebar;
- collapsed desktop sidebar;
- mobile drawer;
- current root-section order;
- absence of legacy global Storage/Analytics/Kubernetes-capability sections;
- active root workspace;
- permission filtering;
- Kubernetes/Object Storage workspace navigation;
- light/dark;
- all canonical viewports;
- no document overflow.

Baseline changes remain review-controlled and are not accepted merely because the DOM contract changed.

## Enforcement and Change Control

Executable authority:

- `scripts/verify_sidebar_navigation_standard.py`
- `tests/contracts/design/test_sidebar_navigation_standard_contract.py`
- Playwright UI coverage in `tests/ui/test_representative_interactions.py`

Any change to section ownership, workspace identity, visual geometry, responsive behavior, or the Section -> Workspace rule requires an explicit issue and design review.
