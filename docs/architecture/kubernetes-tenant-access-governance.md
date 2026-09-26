# Kubernetes Tenant Access Governance

Issue #114 owns the provider-neutral Tenant membership, Access Profile, and Access Grant contract.

## Authority boundary

KAORI application RBAC and Tenant Kubernetes RBAC are separate authorization layers.

- KAORI application permissions such as `tenant.view` and `tenant.manage` control who may operate the Tenant Management product.
- Tenant memberships and Access Grants control what a governed principal may do inside selected Kubernetes tenant scope.
- A Tenant Access Grant never grants KAORI application permissions.
- Native Kubernetes remains authoritative for effective Role/RoleBinding enforcement.
- Credential creation, token delivery, JumpServer access, and GitHub Actions credential material remain owned by #115 and #116.

## Canonical access model

```text
Tenant
  -> Membership (User or Group principal)
      -> Access Grant
          -> Scope (Tenant / Environment / Namespace)
          -> Versioned Access Profile
          -> Native Role + RoleBinding evidence
```

Group identity is explicit and Tenant-scoped. A membership freezes the Kubernetes subject name used by the current provider translation. Membership and grant lifecycle are independent so revoking one grant does not require deleting the principal.

## Built-in Access Profiles

Viewer, Operator, Tenant Admin, and Deployer are code-owned versioned security contracts.

### Viewer

Read-only operational visibility for workload, service, quota/limit, ingress, autoscaling, event, and selected namespace-support resources. It excludes Secret access and all RBAC mutation.

### Operator

Viewer plus bounded workload deployment and troubleshooting operations, including logs, exec, and port-forward. It cannot mutate Tenant RBAC, Namespace, ResourceQuota, LimitRange, ServiceAccount, or cluster-scoped resources.

### Tenant Admin

Operator plus Secret lifecycle required for full application administration. Platform-security controls remain KAORI/platform-admin owned. Tenant Admin cannot mutate Role, RoleBinding, ResourceQuota, LimitRange, Namespace, ServiceAccount, or cluster-scoped resources.

### Deployer

CI/CD-focused workload mutation for Deployments/StatefulSets/DaemonSets/ReplicaSets, Jobs/CronJobs, Services, ConfigMaps, PVCs, Secrets, Ingress, and HPA. It excludes interactive exec/port-forward/log troubleshooting, RBAC administration, Namespace administration, and cluster-scoped resources.

Any later Custom Access Profile requires a separate governed design. Built-in profile permissions are not editable inline.

## Scope semantics

A grant has exactly one scope type:

- Tenant — applies to managed/adopted namespaces under all Tenant environments;
- Environment — applies to managed/adopted namespaces under one Tenant environment;
- Namespace — applies to one managed/adopted Tenant namespace.

Cross-Tenant scope references fail closed.

## Native Kubernetes translation

Each profile version maps to one deterministic namespaced Role name. Each grant maps to one deterministic RoleBinding per target namespace.

KAORI never creates ClusterRoleBinding from this managed path. Wildcard API groups, wildcard verbs, and known platform/cluster-scoped resources are rejected by the Access Profile contract.

Provider resources declare `app.kubernetes.io/managed-by=kaori`. Existing resources owned by another controller are never silently overwritten.

## Revocation and drift

Revocation changes desired state to revoked and removes effective RoleBinding access from every current or previously reconciled target namespace. Shared profile Roles may remain because other grants can reference them.

Committed desired/effective hashes, target evidence, reconciliation state, last reconciliation timestamp, and error message remain separately observable.

States:

- Pending — committed grant has no managed namespace target yet;
- Ready — desired and effective Role/RoleBinding contracts match;
- Drifted — effective Kubernetes RBAC differs from committed intent;
- Failed — reconciliation could not safely complete;
- Revoked — no effective managed RoleBinding remains.

A failed revoke remains visibly revoked in KAORI intent while effective provider removal is marked failed/drifted; it must never be reported as successfully removed.

## Activity and downstream credentials

Create/reconcile/revoke mutations record non-secret AuditEvent evidence with the grant correlation identifier. Kubernetes audit correlation remains owned by #122.

#115 and #116 may bind governed credential principals to the Access Grant contract, but they must reuse the same profile/scope semantics rather than redefining permissions.
