# Kubernetes Dashboard

The Kubernetes Dashboard provides the compact operational summary for registered Kubernetes clusters. It is a drill-down entry point; detailed records remain owned by Kubernetes Cluster, Inventory, Analytics, Intelligence, and Reports.

## Scope contract

- `All Clusters`: database inventory snapshots and per-cluster health rows. Detailed live Prometheus and Alertmanager blocks remain unavailable until a cluster is selected.
- `Selected Cluster`: may combine inventory snapshots, Prometheus, Alertmanager, reporting records, and Intelligence recommendations.
- Missing live data must be reported as unavailable and must never be estimated.

## Technical ownership

- Routes: `routes.py`
- Overview orchestration: `service.py`
- View models: `schema.py`
- Defensive database access: `repository.py`
- Normalization/formatting helpers: `utils.py`
- Independent section builders: `sections/`
- Templates: `templates/dashboards/kubernetes/`

## Extension rule

When adding a section:

1. define or extend the typed schema;
2. add one focused builder under `sections/`;
3. expose it through `sections/__init__.py`;
4. compose it in `service.py`;
5. add the lazy route mapping and domain template;
6. document the source, all-cluster behavior, selected-cluster behavior, and failure state.
