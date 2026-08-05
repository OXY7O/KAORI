# Kubernetes Node Inventory Standard

## Status

- Standard version: **v1.1**
- Reference route: `/inventory/nodes`
- Source boundary: latest committed Kubernetes Inventory generation
- Detail presentation: **Detail Style 2 — Full Workspace Modal**

This document is the authoritative Node Inventory composition contract. Global component geometry remains owned by the referenced shared component standards.

## Purpose

Node Inventory provides a compact operational view of Kubernetes node identity, readiness, capacity evidence, scheduling constraints, connectivity, runtime, and conditions. It is a committed-snapshot inventory page, not a live node-health console.

## Canonical page composition

```text
Canonical Hero
Snapshot Context Bar
Node Resource Posture
Filtered Node Inventory Table
Full Workspace Node Detail
```

The page must use these shared owners:

- Hero: `app/templates/components/page_hero.html`
- Snapshot boundary: `app/templates/components/snapshot_context_bar.html`
- Resource posture shell: `operational_section_card.html`
- Posture metrics: `resource_posture_grid.html`
- Table/filter geometry: `table.html`
- Detail host: `resource_detail_modal.html`
- Detail primitives: `components/details/_detail_content.html`
- Technical metadata: `technical_metadata_collection.html`
- Operational guidance: `operational_callout.html`

Page-local copies of these geometries are prohibited.

## Hero contract

The Node Inventory hero contains:

- title: `Node Inventory`;
- one concise purpose statement;
- metadata: Nodes in Scope, active scope, Active Signals;
- right context: Node Fleet Posture;
- metrics: Ready and Active Signals;
- one action to Kubernetes Integrations.

The posture badge represents the overall node fleet posture, not readiness alone. A fleet with pressure, network, scheduling, or unknown readiness evidence must not display `Healthy` merely because every reported readiness value is `Ready`.

## Snapshot boundary

All list, summary, filter, and detail data comes from the latest committed inventory generation. The web request must not query Kubernetes live.

Exact collection time, selected scope, committed coverage, source, and snapshot exceptions belong in the shared Snapshot Context Bar. These values are not repeated in the hero.

## Resource posture

The Node Resource Posture section contains six metrics:

1. Total CPU
2. Total Memory
3. Ephemeral Storage
4. Cordoned Nodes
5. Nodes with Pressure
6. Network Issues

Capacity totals must preserve evidence completeness:

- missing values are not converted to zero;
- no reported values render as `Not Available`;
- partial values use Warning tone;
- complete values use Normal tone;
- supporting copy states `Reported by X of Y filtered nodes`.

Operational counters count affected nodes, not raw condition records.

## Filters

Filters are:

- Cluster
- Role
- Readiness
- Search Nodes

Requirements:

- every label is programmatically associated with its input;
- `control-plane` and `master` display as `Control Plane`;
- `NotReady` displays as `Not Ready`;
- raw canonical values remain in request parameters;
- changes reset the result page to 1;
- the owning inventory scope is the only HTMX replacement target.

## Table contract

Canonical columns:

```text
Node | Cluster | Readiness | Role | Capacity | Network | Details
```

Rules:

- default page size is 5; available sizes are 5/10/25/50;
- header cells use `scope="col"`;
- a screen-reader caption describes the current scope;
- Node identity uses the shared title-cell presentation;
- Role is metadata, not status;
- Readiness uses a semantic status indicator;
- active conditions are summarized under readiness without adding a wide extra column;
- capacity groups CPU, memory, and ephemeral storage;
- Network shows the canonical internal address and address scope;
- complete evidence is available through the Details action;
- long technical values wrap in the detail workspace, not in additional table columns.

## Node condition semantics

The compact row condition summary may include:

- Cordoned
- Memory Pressure
- Disk Pressure
- PID Pressure
- Network Unavailable

At most two labels are written in full. Additional conditions use `+N more`. No active condition uses `No active conditions`. Missing scheduling evidence is stated separately.

## Detail workspace

The full workspace detail contains:

- header identity, cluster, role, readiness;
- summary: Readiness, Scheduling, Scheduled Pods, Capacity;
- Node Identity;
- Node Capacity;
- Connectivity;
- Platform & Runtime;
- Scheduling & Conditions;
- Scheduling Taints;
- Node Labels;
- Committed Snapshot Boundary;
- state-aware Operational Context.

Detail rules:

- use `data-kaori-detail-density="adaptive-stacks"`;
- do not use fixed card heights;
- do not duplicate card badge values as the first row;
- Connectivity owns network fields only; Scheduled Pods remains in the summary;
- taints use neutral technical-value surfaces, not a collection of Violet metadata pills;
- labels use `technical_metadata_collection.html`;
- unknown readiness receives an explicit evidence-validation action, not a healthy scheduling statement;
- missing capacity or address values remain `Not Reported`/`Not Available`.

## Semantic posture

Overall fleet posture resolves in this order:

1. No records → Unknown / No Data
2. All nodes Not Ready → Critical
3. Any Not Ready or Network Unavailable → Warning / Attention
4. Any pressure or cordoned node → Warning / Attention
5. Unknown readiness evidence → Unknown / Incomplete
6. Otherwise → Normal / Healthy

Color is never the sole signal; every state includes text.

## Responsive and HTMX behavior

- Hero and snapshot context remain stable during filtering and pagination.
- Filter changes replace `#nodes-inventory-scope` so posture and table remain aligned.
- Pagination replaces only `#nodes-table-content` because posture is unchanged.
- Detail content loads on demand through the shared resource detail modal.
- Routine filtering, pagination, and detail loading must not trigger live Kubernetes requests.

## Accessibility

- filter labels use `for`/`id`;
- the filter form has an accessible name;
- table headers use column scope;
- the table has a screen-reader caption;
- icon-only detail controls keep shared `title`, `aria-label`, and focus behavior;
- semantic labels include readable state text;
- focus returns to the detail trigger when the modal closes.

## Change control checklist

Before changing Node Inventory:

- preserve committed-generation filtering;
- preserve missing-evidence semantics;
- keep the seven-column compact table;
- keep default pagination at 5;
- reuse shared Hero, Snapshot, Posture, Table, Detail, Metadata, and Callout components;
- update this standard and the alignment audit in the same change;
- run `python3 scripts/verify_node_inventory_standard.py`.
