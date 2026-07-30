# Kubernetes Namespace Inventory Pattern

Namespace Inventory is the second canonical implementation of the Inventory Resource Page Pattern.

```text
Canonical Hero
Compact Snapshot Context Bar
Namespace Control Posture
Compact Namespace Inventory Table
Detail Style 2 — Full Workspace Modal
```

## Lifecycle semantics

- Active: Normal.
- Terminating: Info / Transitioning until duration or finalizer evidence proves it is stuck.
- Unknown or unsupported: Unknown / Review Required.
- Missing configuration is neutral factual evidence until compared with an explicit governance policy.

## Compact table

Columns:

```text
Namespace | Cluster | Lifecycle | Resource Controls | Security Context | Details
```

Resource controls group ResourceQuota and LimitRange. Security context groups NetworkPolicy and PSA Enforce. The row detail action uses `View Details`.

## Inline detail

The expanded detail contains summary, identity, object composition, access and security, full-width resource controls, Technical Metadata Collections, and Operational Context. It uses no more than three columns on large screens.
