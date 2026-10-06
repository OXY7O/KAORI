# Kubernetes Namespace Inventory Alignment Audit — August 2026

## Decision

Namespace Inventory is aligned with the current KAORI committed-snapshot, evidence, and interaction standards after correcting the gaps below.

## Corrected findings

1. Cluster, lifecycle, and search filters refreshed only the inventory scope. Hero and Snapshot Context could therefore retain values from the previous filter scope.
2. A selected cluster with zero matching Namespace rows was labeled `All Clusters` because scope identity was derived from filtered result rows.
3. Namespace rows with no lifecycle phase contributed to Unknown posture but could not be selected from the lifecycle filter.
4. Missing Pod Security Admission labels were displayed as `Inherited`, although KAORI did not collect cluster-level admission defaults.
5. ResourceQuota collection evidence was not stored. A permission failure could fail the entire synchronization or make unavailable evidence indistinguishable from zero configured quotas.
6. ResourceQuota hard limits were read from observed status only, so newly configured limits could appear empty before status reconciliation.
7. Missing ServiceAccount or control evidence could still produce a normal `Snapshot Ready for Review` operational action.
8. Age was duplicated in the compact table even though the KAORI Inventory standard owns Age in the detail workspace.
9. Posture metrics used normal or brand tones when the denominator had incomplete collection evidence.

## Implemented controls

- Added the `namespaces-page-workspace` HTMX ownership boundary.
- Preserved selected-cluster identity independently from filtered Namespace rows.
- Added canonical Unknown lifecycle filtering for null or blank phase evidence.
- Replaced inferred PSA inheritance with `Not Explicitly Set`.
- Added `inventory.resourcequotas` collection evidence to the committed `ClusterInventory` generation.
- Made ResourceQuota permission and API-unavailable states non-destructive to the wider inventory synchronization.
- Read configured ResourceQuota hard limits from `spec.hard`, with observed status as fallback.
- Separated `Not Configured` from `Not Reported` in list, posture, and detail presentation.
- Added explicit control-evidence validation guidance.
- Removed Age from the compact table and retained it in Namespace Identity detail.
- Added accessibility identifiers, table caption, and column scopes.
- Registered a Namespace Inventory static verifier in the quality gate.

## Validation boundary

Static contracts validate source ownership, committed evidence semantics, collection behavior, copy accuracy, accessibility, and documentation. Runtime browser validation remains required for 14-inch layout, dark mode, HTMX focus continuity, and modal rendering against a live PostgreSQL/Kubernetes environment.

## Additional evidence correction

- Configuration object counts could incorrectly appear as zero when ConfigMap or Secret collection was unavailable. The detail workspace now renders `Not Reported`, exposes object-family evidence coverage, and excludes unreported families from the tracked-object total.
- Control Evidence now reports five domains consistently: ResourceQuota, LimitRange, NetworkPolicy, PSA label evidence, and ServiceAccount evidence.
