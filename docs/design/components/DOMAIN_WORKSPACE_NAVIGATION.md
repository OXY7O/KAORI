# KAORI Domain Workspace Navigation Standard v1.0

**Status:** Locked workspace-navigation contract  
**Foundation authority:** #747  
**Implementation authority:** #748

## Purpose

Domain Workspace Navigation is the second navigation layer after the global sidebar.

It answers:

> **Which major capability inside the selected workspace do I want?**

It replaces the old pattern of expressing capabilities as nested global-sidebar menus.

## Navigation Layers

```text
Level 1 — Global Sidebar
Section -> Workspace

Level 2 — Domain Workspace Navigation
Workspace -> Capability

Level 3 — Capability Content Navigation
Capability -> Detailed peer view
```

"Level 3" here is page/content navigation, not global-sidebar nesting.

## Shared Component Ownership

Domain Workspace Navigation uses the existing **Tab Style 1 — Integrated Workspace Tabs**:

- component: `app/templates/components/workspace_tabs.html`;
- server-owned mode: `workspace_tabs.render_navigation()`;
- semantic key: `integrated-workspace-server`.

No new tab family is introduced.

Detailed capability views continue to use:

- Content Tabs for four-plus subordinate peer content views;
- Compact Segmented Tabs for two/three local modes;
- Framed Workspace Tabs only when a framed parent surface is semantically required.

## Default Composition

Canonical application composition:

```text
Navbar / Breadcrumb
↓
Flat Domain Workspace Navigation
↓
Capability Content Navigation when the capability owns multiple routes
↓
Owning Page Hero / Page Identity
↓
Operational content
```

Domain Workspace Navigation is a **secondary navigation strip**, not a second page header. It uses the existing Integrated Workspace Tabs directly and therefore must not add an outer card, rounded shell, background, shadow, duplicated `WORKSPACE` label, or repeated workspace title around the tab component.

The Hero remains the page's visual identity anchor. Its eyebrow/title pair follows Hero v1.9 semantics: the eyebrow communicates workspace/domain context and the H1 communicates the current destination, for example `INTELLIGENCE → Overview`, not `INFRASTRUCTURE INTELLIGENCE → Intelligence Overview`.

Multi-route capability detail uses server-owned Content Tabs. A page must not copy the retired global-sidebar submenu markup into local templates.

## Current Implemented Workspaces

### Kubernetes

```text
Overview · Inventory · Operations · Governance · Tenant · Analytics
```

Permission-filtered using existing domain authorities.

Detailed views remain local and are rendered through shared server-owned Content Tabs where they are route-level peers:

- Inventory -> Overview / Topology / Nodes / Namespaces / Workloads / Pods / Services / Ingresses / Storage / Configuration;
- Operations -> ConfigMaps / Secrets;
- Governance -> Overview / TLS Certificates;
- Tenant -> Overview / Tenants / Resource Profiles / Namespace Provisioning / Operations;
- Analytics Overview keeps its existing summary Content Tabs (Usage / Capacity / Workload / Storage / Consumers / Forecast / Alerts / Actions / Guidance) and their explicit drill-down CTAs. Deep-analysis routes use the route-level peer navigation Overview / Usage / Capacity / Workloads / Storage / Consumers / Forecast / Alerts & Anomalies. The Overview must not render both tabsets at once.

### Object Storage

```text
Overview · Inventory · Analytics
```

Detailed route-level navigation is local:

- Inventory -> Overview / Systems / Buckets & Containers;
- Analytics -> Overview / Capacity & Usage / Performance / Forecast / Top Consumers / Alerts & Anomalies.

Future Operations/Governance may extend this workspace without changing global navigation.

### Intelligence

```text
Overview · Recommendations · Alert Intelligence · Rule Catalog · Automation Control
```

### Reports

```text
Overview · Generate · Generated · Templates · Storage · Schedules
```

### Operations Center

```text
Overview · Jobs · Data Lifecycle · Kubernetes Admin
```

### Integrations

```text
Overview · Orchestration · Observability · Storage · Notification Channels
```

Provider/domain-specific Framed Workspace navigation remains valid below this layer.

### Access

```text
Overview · Users · Identity Providers · Roles · Permissions · Activity Audit
```

### Settings

```text
General · Account
```

## Reserved Future Workspace Contracts

These names reserve IA ownership only. Do not render until implementation exists.

- Compute: Overview · Assets · Virtualization · Capacity · Lifecycle · Analytics
- Network: Overview · Connectivity · Flows · Dependencies · Policies · DNS · IPAM · Assets · Anomalies
- Services: Overview · Catalog · Ownership · Dependencies · Runtime · Health
- Reliability: Overview · Services & SLOs · Error Budgets · Incidents · Escalations · Postmortems · Analytics
- Backup & Recovery: Overview · Protected Assets · Protection Policies · Restore Points · Restore Tests · RPO/RTO · Recovery Readiness
- Security Posture: Overview · Findings · Supply Chain · Runtime · Secrets & PKI · Network · Exceptions
- Policy & Compliance: Overview · Policies · Violations · Exceptions · Evidence · History
- Secrets & PKI: Overview · Secrets · Certificates · PKI · Leases · Expiration · Consumers · Governance · Audit
- FinOps: Overview · Allocation · Kubernetes · Infrastructure · Storage · Efficiency · Budgets · Forecast · Recommendations · Cost Model
- Automation: Overview · Hosts · Inventories · Profiles · Patching · Plans · Runs · Schedules · Compliance

## Context Is Not Navigation

Cluster, tenant, environment, provider, instance, namespace, time range, and resource identity remain context controls.

Examples:

```text
Kubernetes / Analytics
[Cluster: prod-k8s-01] [Period: 24h]

Object Storage / Inventory
[System: minio-prod] [Environment: Production]
```

Do not create sidebar/workspace tabs for individual clusters, providers, or instances.

Stable scope identifiers may be carried across sibling navigation as URL context without becoming navigation identity. Current preserved context is intentionally bounded:

- Kubernetes workspace/capability siblings preserve `cluster_id`;
- Kubernetes deep Analytics siblings additionally preserve `time_range`;
- Kubernetes Operations siblings may preserve `namespace`;
- Object Storage workspace/capability siblings preserve `system_id`;
- Object Storage Analytics siblings additionally preserve `time_range`.

Filters that are meaningful only to one page remain page-local and are not propagated blindly.

## Permission Contract

Only authorized capabilities render.

If the current route belongs to a capability no longer visible to the current user, the navigation resolves active state to the first visible authorized capability without manufacturing access.

A workspace root must resolve to an authorized child capability.

## Responsive Contract

Integrated Workspace Tabs already own:

- minimum 44 px target height;
- horizontal overflow on narrow screens;
- stable active Violet underline/text;
- keyboard-visible focus;
- real links and server navigation;
- no page-level horizontal overflow.

Do not create a mobile-only accordion or nested drawer for capability navigation.

## Active-State Contract

Global sidebar and Domain Workspace Navigation must agree:

```text
Sidebar active: Kubernetes
Workspace active: Analytics
Breadcrumb: Kubernetes / Analytics / Capacity
Content active: Capacity
```

Each layer communicates a different scope and must not duplicate the same labels unnecessarily.

## Provider / Instance Boundary

Integrations follows:

```text
Integrations workspace
→ capability domain
→ provider
→ instance
```

Provider and instance navigation remains inside Integrations-owned workspaces, registries, or detail surfaces.

## Playwright Evidence

Canonical UI evidence must validate:

- correct workspace strip for representative routes;
- expected permission-filtered tabs;
- active-state coherence;
- horizontal safety at all canonical viewports;
- mobile drawer + workspace strip coexistence;
- no third global navigation level;
- light/dark visual consistency.

Reviewed visual baselines are updated only after human acceptance.
