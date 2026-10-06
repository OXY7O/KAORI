# KAORI Platform Operations Final Lock v1.3 Audit — 2026-08-08

## Review outcome

The Secret Reveal review found three correctness/operational issues and several density refinements:

- kubeconfig availability participated in readiness but was not visible as a prerequisite;
- failed Kubernetes namespace lookups were converted into `Missing`, creating false operational evidence;
- search/filter/pagination could repeatedly trigger live namespace-list requests;
- top Protection Posture could remain stale after no-reload mutations;
- large Violet guidance surfaces competed with the operator controls;
- namespace policy row actions did not distinguish unchanged from unsaved state.

## Frozen decisions

- Cluster Credential is explicit, read-only readiness evidence.
- Live namespace evidence is tri-state: Available, Missing, Unknown.
- `Missing` is emitted only from a successful namespace snapshot.
- Initial tab load, cluster switch, and explicit Refresh own namespace-list refresh; filter and pagination reuse the snapshot.
- Policy enablement still performs fresh live namespace verification independently from the snapshot.
- Protection Posture is synchronized through HTMX OOB updates after readiness/policy saves and cluster switches.
- Kubernetes Boundary and Activation Boundary use clear KAORI surfaces.
- Protection Boundary is rendered as a compact authorization flow.
- Namespace table labels are `Live Namespace` and `Set Policy`.
- Save remains explicit and becomes primary only when the row is dirty.
- Shared operational toast + durable activity behavior remains unchanged for immediate configuration mutations.
