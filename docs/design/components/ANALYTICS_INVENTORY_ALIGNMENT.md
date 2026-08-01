# Analytics and Inventory Hero Alignment

Kubernetes Inventory Overview is the reference composition for Kubernetes Analytics heroes.

Every Kubernetes Analytics page must use the same hero grammar:

1. Domain intro, description, and compact metadata on the left.
2. A posture panel on the right with one semantic status and no more than two domain metrics.
3. A full-width `Manage Clusters` action at the bottom of the posture panel.
4. Posture explanation is compact helper copy beneath the posture value; it must not replace or compete with the action slot.
5. Dependency-blocked states retain the same `Manage Clusters` action so the operator always has a consistent recovery path.

The data remains domain-specific. Utilization shows pressure, Capacity shows headroom, Storage shows filesystem/PVC evidence, Workload shows governance signals, Forecast shows projections, Top Consumers shows pressure/actionability, and Alerts shows critical/source evidence.


## Compact Posture Density

Analytics posture values use the same title geometry as the Inventory context card (`context_panel_title_classes`). The posture header must not include an additional description line. Domain metrics use compact values and short helpers; long dynamic identifiers remain helper text and are truncated for presentation while the detailed workspace retains the complete value.

## Dynamic identity rule

Analytics hero metrics must not truncate or expose long technical identifiers. The hero presents a semantic context label instead, for example `Node Filesystem`, `Ready-Worker Capacity`, `Namespace Scope`, or `Selected Cluster`. Full hostnames, object names, and technical identifiers remain available in the detailed workspace.
