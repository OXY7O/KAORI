# KAORI Page Workspace Navigation Standard v1.1

**Status:** Locked detailed-view navigation contract  
**Foundation authority:** #747  
**Implementation authority:** #748

## Purpose

The global sidebar already owns workspace and capability navigation:

```text
Sidebar level 1 — Workspace / Domain
Sidebar level 2 — Capability
```

The page workspace owns only the next semantic layer:

```text
Page level 3 — Detailed View / Resource View
```

This prevents stacked global tab rows and keeps the Hero/content area focused on the current capability.

## Default Composition

```text
Navbar / Breadcrumb
↓
Level-3 Content Navigation when required
↓
Hero / Page Identity
↓
Operational Content
```

A page with no peer detailed views renders no level-3 navigation.

There is **no global Domain Workspace horizontal strip** between breadcrumb and page content.

## Shared Component Ownership

Route-level detailed peer views normally use:

- `components/content_tabs.html` — four-plus closely related detailed routes;
- `components/segmented_tabs.html` — two/three local presentation modes;
- `components/workspace_tabs.html` — integrated sections that genuinely define one page workspace, such as the Kubernetes Operations Dashboard internal sections;
- `components/framed_workspace_tabs.html` — only where an explicit framed parent workspace is semantically required.

Sidebar capability navigation does not use these components.

No new tab family is authorized.

## Current Level-3 Contracts

### Kubernetes / Inventory

```text
Overview · Topology · Nodes · Namespaces · Workloads · Pods · Services · Ingresses · Storage · Configuration
```

### Kubernetes / Operations

```text
ConfigMaps · Secrets
```

### Kubernetes / Governance

```text
Overview · TLS Certificates
```

### Kubernetes / Tenant

```text
Overview · Tenants · Resource Profiles · Namespace Provisioning · Operations
```

### Kubernetes / Analytics

Deep-analysis routes:

```text
Overview · Usage · Capacity · Workloads · Storage · Consumers · Forecast · Alerts & Anomalies
```

Kubernetes Analytics Overview already owns summary/evidence Content Tabs and therefore suppresses the separate deep-analysis route row on Overview itself. Its cards provide drill-down CTAs into the deep-analysis pages.

### Object Storage / Inventory

```text
Overview · Systems · Buckets & Containers
```

### Object Storage / Analytics

```text
Overview · Capacity & Usage · Performance · Forecast · Top Consumers · Alerts & Anomalies
```

## Context Is Not Navigation

Cluster, namespace, tenant, environment, provider, instance, system, time range, and resource identity are context.

Stable identifiers may be preserved across sibling links where explicitly registered:

- Kubernetes detailed views preserve `cluster_id`;
- Kubernetes Analytics may preserve `time_range`;
- Kubernetes Operations may preserve `namespace`;
- Object Storage detailed views preserve `system_id`;
- Object Storage Analytics may preserve `time_range`.

Page-only filters remain local.

## Hero Relationship

The Hero remains the primary content identity anchor.

Use Hero v1.9 semantics:

```text
Eyebrow = workspace/capability context
H1      = current destination
```

Examples:

```text
KUBERNETES INVENTORY → Overview
INTELLIGENCE          → Overview
OBJECT STORAGE        → Inventory Overview
```

Do not add another `WORKSPACE <name>` header around local navigation.

## Active-State Contract

The three semantic scopes agree:

```text
Sidebar level 1: Kubernetes
Sidebar level 2: Inventory
Page level 3:     Nodes
Breadcrumb:       Kubernetes / Inventory / Nodes
```

Each scope conveys different information and should not duplicate a peer row.

## Responsive Contract

Local Content Tabs own their existing horizontal-overflow behavior.

Requirements:

- no page-level horizontal overflow;
- keyboard-visible focus;
- active detail remains identifiable;
- mobile does not introduce another drawer/accordion taxonomy for level 3;
- long detail sets may horizontally scroll inside their own component.

## Playwright Evidence

Validate:

- no global Domain Workspace strip;
- correct active level-3 detail on representative Kubernetes/Object Storage pages;
- Analytics Overview duplicate-tab suppression;
- bounded context preservation;
- all canonical viewports;
- light/dark visual consistency.

Reviewed visual baselines update only after human acceptance.
