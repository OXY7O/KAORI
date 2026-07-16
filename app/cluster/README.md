# Kubernetes Cluster Compatibility

Cluster Management owns Kubernetes API connectivity, runtime identity, lifecycle posture, and inventory synchronization.

- API compatibility profile: `kubernetes-api-v1`
- Kubernetes runtime version: stored separately
- Lifecycle status: `current`, `legacy`, or `unknown`
- Feature readiness: validated from live API discovery and RBAC

KAORI intentionally does not create one profile per Kubernetes minor release. The API contract stays readable and stable, while lifecycle and removed/deprecated API checks are maintained separately.

Kubernetes compatibility is consumed by Inventory, Operations, and Governance. Prometheus and Alertmanager compatibility remain in the Integrations domain.
