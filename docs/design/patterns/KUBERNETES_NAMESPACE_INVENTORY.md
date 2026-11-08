# Kubernetes Namespace Inventory Standard

Namespace Inventory is the second canonical implementation of the Inventory Resource Page Pattern.

```text
Canonical Hero
Compact Snapshot Context Bar
Namespace Control Posture
Compact Namespace Inventory Table
Detail Style 2 — Full Workspace Modal
```

## Evidence boundary

- The page reads only the latest committed inventory generation for each cluster.
- Cluster, lifecycle, and search filters refresh the complete page workspace so the Hero, Snapshot Context, posture metrics, filter options, and table remain aligned.
- A selected cluster remains the active scope even when lifecycle or search filters return zero Namespace rows.
- Missing collection evidence is represented as `Not Reported`; it is not converted to zero or `Not Configured`.
- Object Composition must render ConfigMap and Secret counts as `Not Reported` when collection evidence is unavailable; `0` is reserved for a successfully collected empty result.

## Lifecycle semantics

- Active: Normal.
- Terminating: Info / Transitioning until duration or finalizer evidence proves it is stuck.
- Missing lifecycle state: Unknown / Review Required and filterable as `Unknown`.
- Unsupported lifecycle values remain visible as factual unknown evidence.

## Namespace control semantics

- ResourceQuota, LimitRange, NetworkPolicy, ServiceAccount, and Pod Security Admission labels are factual evidence.
- Missing configuration is neutral until evaluated by an explicit governance policy.
- ResourceQuota collection permission or API failures are committed as collection evidence and must not be interpreted as zero ResourceQuota objects.
- Pod Security Admission labels that are absent display `Not Explicitly Set`. KAORI must not claim that a cluster-level default was inherited unless that default has been collected explicitly.
- The default ServiceAccount may be `Present`, `Missing`, or `Not Reported`.

## Compact table

Columns:

```text
Namespace | Cluster | Lifecycle | Resource Controls | Security Context | Details
```

The six existing headers follow the approved Inventory proportional-width design: **Namespace 24%**, **Cluster 21%**, **Lifecycle 8%**, **Resource Controls 18%**, **Security Context 19%**, and **Details 10%**. Namespace and Cluster receive **45% of the table width together**. At narrow viewports, keep the **78rem** minimum-width table inside the existing horizontal scrolling container instead of overlapping content. The shared Namespace and Cluster identity macros retain full names in their accessible `title` attributes and accept `w-full min-w-0` so visual truncation respects the allocated column.

Resource controls group ResourceQuota and LimitRange. Security context groups NetworkPolicy and PSA Enforce using a 6rem label track for readable paired labels and values at the new widths. Age remains in the detail workspace rather than the compact table. The row detail action uses `View Details`. Filter scope, HTMX refresh, evidence authority, detail modal, and default pagination remain unchanged.

## Detail workspace

The expanded detail contains summary, identity, object composition, access and security, resource controls, Technical Metadata Collections, and Operational Context. It uses no more than three columns on large screens.

When collection evidence is incomplete, the detail provides explicit validation guidance rather than presenting a healthy posture. ResourceQuota absence is shown separately from ResourceQuota evidence that could not be collected.
