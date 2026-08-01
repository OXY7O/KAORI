# Analytics and Inventory Hero Alignment

Kubernetes Inventory Overview is the reference composition for Kubernetes Analytics heroes.

Every Kubernetes Analytics page must use the same hero grammar:

1. Domain intro, description, and compact metadata on the left.
2. A posture panel on the right with one semantic status and no more than two domain metrics.
3. A full-width `Manage Clusters` action at the bottom of the posture panel.
4. Posture explanation is compact helper copy beneath the posture value; it must not replace or compete with the action slot.
5. Dependency-blocked states retain the same `Manage Clusters` action so the operator always has a consistent recovery path.

The data remains domain-specific. Utilization shows pressure, Capacity shows headroom, Storage shows filesystem/PVC evidence, Workload shows governance signals, Forecast shows projections, Top Consumers shows pressure/actionability, and Alerts shows critical/source evidence.
