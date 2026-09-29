# KAORI Sidebar Navigation Standard v2.1

**Status:** Locked application-shell navigation contract  
**Foundation authority:** #747  
**Implementation authority:** #748

## Purpose

The authenticated sidebar is KAORI's persistent two-level workspace navigator.

Section labels are non-interactive grouping metadata and are **not** counted as navigation levels.

```text
Section label
└── Level 1 — Workspace / Domain
    └── Level 2 — Capability
```

Detailed views below a capability belong to the page workspace, not the sidebar.

## Architecture Rule

Navigation follows the KAORI architecture principle:

> **capability/domain first, provider second, instance third**

Therefore:

- providers/vendors do not become global roots merely because they are integrated;
- provider domains/providers remain inside Integrations;
- provider instances/resources remain context selectors, registries, tables, drawers, or detail surfaces;
- sidebar level 1 identifies the workspace/domain;
- sidebar level 2 identifies the capability;
- detailed resource/view navigation is local page/workspace navigation;
- a third nested sidebar level is prohibited.

## Visual Geometry

The approved Violet sidebar geometry remains stable:

| Role | Contract |
| --- | --- |
| Expanded width | 250 px |
| Collapsed width | 78 px |
| Section label | 12 px extra-bold uppercase |
| Level-1 workspace | minimum 44 px, 16 px semibold |
| Level-1 icon surface | 32 px |
| Level-1 icon | 16 px |
| Level-2 capability | 14 px / 20 px line-height |
| Level-2 icon | 14 px |
| Level-2 indicator dot | 6 px |
| Parent radius | 8 px |
| Child radius | 8 px |

The level-1 parent remains visually stronger than its active level-2 child.

## Level-1 Workspace

Level-1 workspaces use native `details/summary` when they own multiple capabilities.

Contract:

- minimum 44 px root target;
- stable icon and Title Case label;
- active workspace uses canonical `sidebar-parent-active`;
- active parent remains open after navigation;
- chevron indicates disclosure;
- when desktop sidebar is collapsed, activating an expandable workspace first expands the sidebar and reveals level 2 rather than navigating to an arbitrary capability;
- `title` and `aria-label` remain available in collapsed mode.

A true single-destination workspace may use a direct root link with identical root geometry.

## Level-2 Capability

Capabilities are subordinate links inside the active/open workspace.

Contract:

- 14 px label;
- subtle guide line;
- 14 px stable Lucide icon;
- 6 px indicator dot;
- restrained translucent active state;
- never use the same solid Violet fill as the level-1 parent;
- one active capability may own `aria-current="page"`;
- permission filtering occurs before rendering;
- a capability link may preserve only approved stable context.

## Runtime IA

Current implemented runtime:

```text
MAIN
└── Welcome

INFRASTRUCTURE
├── Kubernetes
│   ├── Overview
│   ├── Inventory
│   ├── Operations
│   ├── Governance
│   ├── Tenant
│   └── Analytics
└── Object Storage
    ├── Overview
    ├── Inventory
    └── Analytics

INSIGHTS
├── Intelligence
│   ├── Overview
│   ├── Recommendations
│   ├── Alert Intelligence
│   ├── Rule Catalog
│   └── Automation Control
└── Reports
    ├── Overview
    ├── Generate
    ├── Generated
    ├── Templates
    ├── Storage
    └── Schedules

PLATFORM
├── Operations Center
│   ├── Overview
│   ├── Jobs
│   ├── Data Lifecycle
│   └── Kubernetes Admin
└── Integrations
    ├── Overview
    ├── Orchestration
    ├── Observability
    ├── Storage
    └── Notification Channels

ADMINISTRATION
├── Access
│   ├── Overview
│   ├── Users
│   ├── Identity Providers
│   ├── Roles
│   ├── Permissions
│   └── Activity Audit
└── Settings
    ├── General
    └── Account
```

## Reserved Future Ownership

Reserved workspaces do not render until implementation and authorization exist:

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

Future workspace capabilities are defined by #747 and may extend their parent without changing the global section architecture.

## Permission Contract

A workspace is rendered only when at least one capability is authorized.

A workspace does not navigate to an arbitrary child when the user activates its parent disclosure. Child links own navigation.

Examples:

- Governance-only Kubernetes user sees Kubernetes → Governance;
- ConfigMap-only user sees Kubernetes → Operations and the capability resolves to ConfigMaps;
- identity-provider-only administrator sees Access → Identity Providers plus any authorized overview contract;
- unauthorized siblings are omitted.

Server-side route decorators remain authoritative; sidebar filtering is discoverability, not authorization.

## Context Contract

Stable scope may survive sibling capability navigation without becoming navigation identity:

- Kubernetes capabilities may preserve `cluster_id`;
- Object Storage capabilities may preserve `system_id`.

Detailed page navigation may preserve additional bounded context such as `time_range` or Operations `namespace` where explicitly registered.

Do not propagate arbitrary page filters.

## Active-State Contract

Exactly one level-1 workspace may be active.

Within that workspace, exactly one authorized level-2 capability may own the active child state.

Example:

```text
Kubernetes              ← active level 1
  Inventory             ← active level 2
```

The page then owns its detailed active view, such as `Overview` or `Nodes`.

## Responsive / Collapse Contract

Desktop:

- expanded width 250 px;
- collapsed width 78 px;
- collapsed mode hides text/submenus;
- selecting an expandable workspace while collapsed expands the sidebar and reveals its capabilities.

Mobile:

- full readable off-canvas drawer;
- same level-1/level-2 taxonomy;
- no mobile-only information architecture;
- destination navigation closes the drawer;
- disclosure does not overwrite desktop collapse preference.

## Breadcrumb Contract

Breadcrumb hierarchy may expose the page-detail level even though that detail is not in the sidebar:

```text
KAORI / Kubernetes / Inventory / Nodes
KAORI / Kubernetes / Analytics / Capacity
KAORI / Object Storage / Inventory / Buckets
KAORI / Intelligence / Recommendations
KAORI / Integrations / Observability
```

## Provider Boundary

Do not add provider/vendor roots such as Harbor, GitHub, Ansible, Prometheus, Alertmanager, MinIO, Vault/OpenBao, VMware, Proxmox, Cilium, or NetBox simply because they are connected.

Provider navigation belongs inside the owning capability/workspace.

## Jinja Mapping Contract

Runtime navigation is supplied as Python mappings.

Renderer access must use explicit mapping syntax:

```jinja2
section['items']
item['children']
child['label']
```

Do not use mapping attribute syntax such as `section.items`; Jinja may resolve Python methods such as `dict.items()`.

## Implementation Ownership

Runtime semantic model:
`app/common/workspace_navigation.py`

Global renderer:
`app/templates/components/navigation/sidebar.html`

Detailed page navigation:
`app/templates/components/content_tabs.html` and other registered local tab components

Breadcrumb authority:
`app/common/navigation.py`

Legacy `*_menu.html` templates may remain temporarily as historical/migration files but must not be included by the v2.1 sidebar.

## Playwright / Visual QA

Reuse #543 / #224.

Required evidence:

- expanded desktop two-level hierarchy;
- collapsed desktop expansion behavior;
- mobile disclosure/destination behavior;
- active parent + subordinate active capability;
- permission filtering;
- Kubernetes/Object Storage detail Content Tabs;
- light/dark;
- all canonical viewports;
- no page-level horizontal overflow;
- no horizontal Domain Workspace strip in the app shell.

Reviewed baseline changes require human acceptance.

## Prohibited Patterns

Do not:

- render a third nested sidebar level;
- render capability peers as a second global horizontal tab row;
- give active children the same solid Violet treatment as parents;
- expose provider instances as sidebar items;
- render future placeholder workspaces;
- create a new tab family for ordinary detail navigation;
- use page filters as navigation identity;
- use Jinja mapping attribute syntax for runtime navigation mappings.

## Enforcement

Executable authority:

- `scripts/verify_sidebar_navigation_standard.py`;
- `tests/contracts/design/test_sidebar_navigation_standard_contract.py`;
- Playwright coverage in `tests/ui/test_representative_interactions.py`.

Any change to hierarchy, section ownership, geometry, responsive behavior, or provider boundary requires an explicit authority update.
