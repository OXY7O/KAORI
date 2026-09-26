# Kubernetes Tenant Access Governance

Issue #114 owns the provider-neutral Tenant membership, Access Profile, and Access Grant contract. Issue #690 clarifies the identity-group, scope, revocation, and operator-guidance semantics of that contract.

## Authority boundary

KAORI application RBAC and Tenant Kubernetes RBAC are separate authorization layers.

- KAORI application permissions such as `tenant.view` and `tenant.manage` control who may operate the Tenant Management product.
- Tenant memberships and Access Grants control what a governed principal may do inside selected Kubernetes tenant scope.
- A Tenant Access Grant never grants KAORI application permissions.
- Kubernetes authentication establishes the user/group identity presented to the API server.
- Native Kubernetes remains authoritative for effective Role/RoleBinding enforcement.
- An external IdP/authenticator remains authoritative for membership of an externally asserted identity group.
- Credential creation, token delivery, JumpServer access, and GitHub Actions credential material remain owned by #115 and #116.

KAORI application login/SSO and Kubernetes authentication are separate identity/authorization domains unless an explicitly supported integration maps them. Logging in to KAORI through an SSO provider does not by itself make the same user or group identity available to Kubernetes.

## Canonical terminology

Use these terms consistently in implementation, documentation, and operator-facing copy:

- **User Principal** — one authenticated user subject that Kubernetes can recognize.
- **Identity Group** — a group identity asserted by the Kubernetes authentication layer or an approved connected IdP/authenticator. The identity source is authoritative for who belongs to that group.
- **Tenant Group** — KAORI registration/binding of one Kubernetes Group subject to one Tenant. A Tenant Group is not a KAORI-owned list of users in Tenant Management v1.
- **Tenant Membership** — registers one User Principal or Tenant Group as an active principal of one Tenant.
- **Access Profile** — a versioned least-privilege contract such as Viewer, Operator, Tenant Admin, or Deployer.
- **Access Grant** — assigns one Access Profile to one active Tenant Membership at exactly one scope.
- **Tenant Scope** — all managed/adopted namespaces under the selected Tenant.
- **Environment Scope** — all managed/adopted namespaces under one selected Tenant Environment.
- **Namespace Scope** — exactly one managed/adopted Tenant Namespace.

Do not use `Group` alone when the context could be confused with a KAORI-local user collection. Prefer `Identity Group`, `Tenant Group`, or `Kubernetes Group subject` according to the specific layer being discussed.

## Canonical access model

```text
Kubernetes authentication / IdP
  -> User Principal or Identity Group
      -> KAORI Tenant Membership
          -> Access Grant
              -> Scope (Tenant / Environment / Namespace)
              -> Versioned Access Profile
              -> Native Role + RoleBinding evidence
```

A membership freezes the Kubernetes subject name used by the current provider translation. Membership and grant lifecycle are independent so revoking one grant does not require deleting or revoking the principal's Tenant Membership.

### Group identity ownership

Kubernetes RBAC does not store the users that belong to a Group. During authentication, the API server receives a username plus zero or more group names. A RoleBinding whose subject is `kind: Group` authorizes requests when one of those authenticated group names matches the RoleBinding subject name.

Therefore:

- a Tenant Group `subject_name` must match a group identity that the Kubernetes authentication path can actually assert;
- adding or removing people from the underlying Identity Group happens in the authoritative IdP/authenticator, not in KAORI Tenant Management v1;
- KAORI owns the Tenant registration/binding, Access Grant, reconciliation evidence, governance state, and audit trail;
- creating a Tenant Group record does not create that group in an IdP;
- a generated/local-looking Tenant Group subject is effective only when the Kubernetes authentication path is configured to assert that exact group name.

Example:

```text
Authoritative IdP
Identity Group: platform-developers
Members: Alice, Bob, Doni
          |
          | authentication asserts group "platform-developers"
          v
Kubernetes API
          |
          | RoleBinding subject kind=Group, name=platform-developers
          v
KAORI Tenant access intent
Payment Platform -> platform-developers -> Operator -> Development
```

KAORI does not maintain the Alice/Bob/Doni membership list in this v1 flow. If KAORI later owns local group membership, that requires a separate identity-projection/authentication contract capable of making those group memberships authoritative to Kubernetes; a database-only group list is insufficient.

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

A grant has exactly one scope type.

Assume this Tenant layout:

```text
Payment Platform
├── Development
│   ├── payment-api-dev
│   └── payment-worker-dev
├── Staging
│   └── payment-api-staging
└── Production
    ├── payment-api-prod
    └── payment-worker-prod
```

### Namespace Scope

Namespace Scope targets exactly one managed/adopted Tenant Namespace.

Example:

```text
platform-developers
  -> Operator
  -> Namespace: payment-api-dev
```

Effective target:

```text
payment-api-dev          YES
payment-worker-dev       NO
payment-api-staging      NO
payment-api-prod         NO
payment-worker-prod      NO
```

The grant must contain one Namespace target and no Environment target. The current invariant error `Namespace-scoped Access Grant requires exactly one managed namespace` means that the operator selected Namespace Scope without exactly one valid Tenant Namespace target, or supplied a conflicting Environment target.

### Environment Scope

Environment Scope targets the managed/adopted namespaces under one Tenant Environment.

Example:

```text
platform-developers
  -> Operator
  -> Environment: Development
```

Effective scope:

```text
payment-api-dev          YES
payment-worker-dev       YES
payment-api-staging      NO
payment-api-prod         NO
payment-worker-prod      NO
```

The grant must contain one Environment target and no Namespace target. Environment is a KAORI governance grouping; it does not create a Kubernetes cluster-scoped authorization object. Native reconciliation materializes namespaced Role/RoleBinding state for the applicable target namespaces.

### Tenant Scope

Tenant Scope targets managed/adopted namespaces across all environments in one Tenant.

Example:

```text
platform-auditors
  -> Viewer
  -> Tenant: Payment Platform
```

Effective scope:

```text
Development namespaces  YES
Staging namespaces      YES
Production namespaces   YES
Other Tenants           NO
Cluster-wide resources  NO
```

Tenant Scope is not Kubernetes cluster scope. It must never be represented as ClusterRoleBinding or accidental cluster-wide privilege.

Cross-Tenant scope references fail closed.

### Scope target matrix

| Scope | Environment target | Namespace target | Meaning |
|---|---|---|---|
| Tenant | none | none | Managed/adopted namespaces across the selected Tenant |
| Environment | exactly one | none | Managed/adopted namespaces in one selected Tenant Environment |
| Namespace | none | exactly one | One managed/adopted Tenant Namespace |

## Native Kubernetes translation

Each profile version maps to one deterministic namespaced Role name. Each grant maps to one deterministic RoleBinding per target namespace.

For a User Principal, the RoleBinding subject is a Kubernetes `User` subject. For a Tenant Group, the RoleBinding subject is a Kubernetes `Group` subject whose name comes from the registered group subject.

KAORI never creates ClusterRoleBinding from this managed path. Wildcard API groups, wildcard verbs, and known platform/cluster-scoped resources are rejected by the Access Profile contract.

Provider resources declare `app.kubernetes.io/managed-by=kaori`. Existing resources owned by another controller are never silently overwritten.

## Revocation and re-authorization

Access Grant revocation and Tenant Membership revocation are different operations.

### Revoke Access Grant

Revoke Access Grant:

- keeps the User Principal or Tenant Group registered as an active Tenant Membership;
- changes that Access Grant's desired state to revoked;
- removes the effective managed RoleBinding from every current or previously reconciled target namespace;
- preserves the revoked grant and reconciliation evidence for audit history;
- may leave a managed Role object in place because other grants can reference the same profile Role.

A later decision to give the same active Membership access again is a new authorization decision. The current implementation creates a new Access Grant lineage instead of silently changing the old revoked grant back to active. This preserves the historical revoke event.

Example:

```text
Before
platform-developers -> Operator -> Development -> ACTIVE

Revoke Access Grant
platform-developers -> Operator -> Development -> REVOKED
RoleBinding access removed
Tenant Membership remains ACTIVE

Later approved again
platform-developers -> Operator -> Development -> NEW ACTIVE GRANT
old revoked grant remains audit evidence
```

### Revoke Tenant Membership

Revoke Tenant Membership:

- changes the Tenant Membership to revoked;
- revokes every dependent active Access Grant;
- removes their effective managed RoleBindings;
- preserves historical Membership and Access Grant evidence.

This is the stronger action because the principal is no longer an active member of the Tenant.

Current #114 implementation does not expose a supported reactivation/rejoin transition for the same User Principal or Tenant Group after Tenant Membership revocation. The existing persistence uniqueness and create guard also prevent treating the same principal as a brand-new duplicate Membership. Until an explicit reactivation contract is implemented, operators should treat Tenant Membership revocation as terminal rather than as a temporary disable action.

## Reconciliation and drift

Committed desired/effective hashes, target evidence, reconciliation state, last reconciliation timestamp, and error message remain separately observable.

States:

- Pending — committed grant has no managed namespace target yet;
- Ready — desired and effective Role/RoleBinding contracts match;
- Drifted — effective Kubernetes RBAC differs from committed intent;
- Failed — reconciliation could not safely complete;
- Revoked — no effective managed RoleBinding remains.

A failed revoke remains visibly revoked in KAORI intent while effective provider removal is marked failed/drifted; it must never be reported as successfully removed.

## Operator contextual guidance

Tenant Management must explain identity, scope, and destructive actions at the point of use. Reuse existing KAORI tooltip/help-text/error patterns; do not create a Tenant-only help system.

At minimum:

- identify whether a Membership is a User Principal or Tenant Group;
- explain that a Tenant Group references a Kubernetes Group subject and that external group membership remains owned by the configured Kubernetes authentication/IdP authority;
- show concise scope examples next to the Scope selector;
- when Scope is Tenant, hide or disable Environment and Namespace target controls;
- when Scope is Environment, require only an Environment target;
- when Scope is Namespace, require only a Namespace target;
- filter Environment/Namespace target choices to the Tenant of the selected Membership;
- explain Revoke Access Grant versus Revoke Tenant Membership before destructive confirmation;
- translate internal scope invariants into actionable operator messages, for example: `Choose one managed Namespace for Namespace Scope`;
- where integration evidence exists, distinguish a verified external group subject from an unverified/free-form subject.

Contextual guidance is explanatory only. Server-side validation and fail-closed provider reconciliation remain authoritative.

## Activity and downstream credentials

Create/reconcile/revoke mutations record non-secret AuditEvent evidence with the grant correlation identifier. Kubernetes audit correlation remains owned by #122.

#115 and #116 may bind governed credential principals to the Access Grant contract, but they must reuse the same profile/scope semantics rather than redefining permissions.
