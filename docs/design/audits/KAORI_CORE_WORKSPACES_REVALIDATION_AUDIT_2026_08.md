# KAORI Core Workspaces Revalidation Audit — August 5, 2026

## Reviewed workspaces

- Welcome
- Kubernetes Operations Dashboard
- Kubernetes Inventory: Overview, Topology, Nodes, Namespaces, Workloads, Pods, Services,
  Ingresses, Configuration, and Storage
- Kubernetes Governance: TLS Certificates
- Kubernetes Operations: ConfigMaps and Secrets

## Acceptance baseline

The review applies the current KAORI Violet visual standard, committed-snapshot evidence boundary,
canonical HTMX workspace ownership, five-row default pagination, shared component ownership, and
internal no-compatibility-wrapper policy. External Kubernetes API compatibility normalization is
retained only where it is part of the documented provider contract.

## Corrections

### Topology

Resource Visibility glyphs were using translucent fill tokens as foreground colors. Domain classes
now own background, border, and text tokens together, producing readable glyphs in light and dark
mode everywhere the domain class is reused. Topology Details is widened from 22rem to 26rem. API
Server no longer selects a stacked compatibility row; it stays on one line with ellipsis and native
full-value disclosure when necessary.

### Storage Inventory

The filter grid now enters its desktop five-column layout at `lg`, with proportional widths for
Cluster, Namespace, Storage Type, Lifecycle, and Search. All labels are explicitly associated with
control IDs. Mobile and narrow-screen stacking remains responsive.

### Cross-domain ownership

Dashboard alert generation and dataset keys are now Analytics-owned. Integration recovery uses the
Job Registry rather than direct Inventory, Governance, or Analytics implementation imports. Shared
job execution presentation is Common-owned, and the Jobs workspace adds cancellation policy only.
This removes newly detected dependency cycles without broadening architecture exceptions.

### Removed legacy files

- `app/dashboards/kubernetes/snapshot_builder.py`
- `app/analytics/common/cache.py`
- `app/templates/analytics/components/_overview_surfaces.html` (replaced by the canonical `_analysis_surfaces.html`)

Both are registered in the obsolete-file cleanup and regression guards.

## Confirmed canonical behavior

- Welcome owns `/` and `/welcome` directly.
- Dashboard HTTP paths remain database-only and read committed Analytics snapshots.
- Inventory pages own one `*-page-workspace`; table pagination updates only `*-table-content`.
- Topology remains split across repository, node builder, edge builder, graph builder,
  presentation, contracts, and orchestration service.
- ConfigMap and Secret operations use the canonical live API guardrails, Notification Deck, and
  Activity Log contract.
- TLS Certificate Governance remains a committed inventory workspace with registered background
  synchronization and canonical notification delivery.

## Validation commands

```bash
python scripts/verify_source_hygiene.sh
python scripts/verify_architecture_boundaries.py
python scripts/verify_core_workspace_legacy_cleanup.py
python scripts/verify_core_workspace_code_health.py
python scripts/verify_node_inventory_standard.py
python scripts/verify_namespace_inventory_standard.py
python scripts/verify_workload_inventory_standard.py
python scripts/verify_pod_inventory_standard.py
python scripts/verify_service_inventory_standard.py
python scripts/verify_ingress_inventory_standard.py
python scripts/verify_storage_inventory_standard.py
python scripts/verify_configuration_inventory_standard.py
python scripts/verify_operational_dashboard_standard.py
python scripts/verify_configmap_management_standard.py
python scripts/verify_secret_management_standard.py
python scripts/verify_tls_certificate_governance_standard.py
npm run check-format
npm run build-css
```

Functional pytest and browser validation run in the KAORI development container with Python
requirements installed. The module reachability verifier still identifies two pre-existing,
unreferenced modules outside this review scope: `app/knowledge/remediation_workflow.py` and
`app/users/identity.py`. They were not removed because their ownership and product lifecycle require
a separate Intelligence and Identity review rather than an unrelated core-page patch.
