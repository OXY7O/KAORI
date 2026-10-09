# Kubernetes Tenant Capsule Provider

Issue #121 implements Capsule as an optional capability-aware provider over the same canonical KAORI Tenant domain. Native Kubernetes remains the baseline provider; Capsule is a capability unlock rather than a hard dependency.

## Supported discovery contract

KAORI recognizes the Capsule API group `capsule.clastix.io` and the currently supported Tenant API versions `v1beta2` and `v1beta1`. Discovery records the served Tenant CRD versions and the reported Capsule application version when available.

CRD discovery covers the Tenant controller and explicit advanced resource types such as TenantResource, GlobalTenantResource, GlobalResourceQuota, ResourcePool, and ResourcePoolClaim. CRD presence alone does not prove non-CRD surfaces such as Capsule Proxy or admission health; those require explicit probe evidence.

## Capability states

Capsule is not modeled as a boolean. The provider reports capability evidence for:

- Tenant controller and supported CRD version;
- admission enforcement;
- Capsule Proxy;
- shared/global quota;
- resource pools/claims;
- TenantResource / GlobalTenantResource replication.

Only `available` capabilities may authorize security-sensitive mutations. Degraded or unavailable capabilities fail closed.

## Cluster-scoped RBAC prerequisites

Canonical ClusterRoles for Capsule Tenant grants are shared **per Kubernetes
cluster**, not per adopted Tenant. The approved operating path is
**Integrations → Kubernetes → [Cluster] → Validation & Capabilities →
Capsule Cluster RBAC Bootstrap**: Check existing exact profiles, explicitly
approve only missing-role creation, and verify committed Audit evidence.
Native ClusterRole owner roles or broader built-in roles are never reused as
equivalents. Existing identical roles are reused without mutation; conflicting
roles stop bootstrap. Readiness is derived from the last committed Check or
Bootstrap event, never an automatic request on each page load.

This prerequisite operation requires a privileged cluster connection; it
does not run during discovery, adoption, Grant Apply, or background sync.
Manual `Prepare Roles` YAML download remains an approved fallback without
permission to bootstrap. See `docs/architecture/kubernetes-tenant-access-governance.md`.

## Access Grant reconciliation

Issue #966 adds independent Capsule Access Grant capability detection:
`access_grants_tenant` requires `Tenant.spec.additionalRoleBindings`, while
`access_grants_scoped` requires supported `Tenant.spec.rules[].namespaceSelector`
and `permissions.bindings` in the served v1beta2 CRD schema. Both remain
unavailable or degraded when version/schema evidence is missing. KAORI executes
all grant scopes through the scoped capability; unbounded
`additionalRoleBindings` automatic future-Namespace inheritance is **not** admitted.

KAORI keeps identity, scope, versioned Access Profile, audit, and desired/effective
evidence in the common Tenant domain. Capsule remains the authoritative controller
for the distributed namespaced RoleBindings, backed by exact pre-approved ClusterRoles.
No Native fallback, implicit provider takeover, ClusterRole creation, or
ClusterRoleBinding creation is admitted. See
`docs/architecture/kubernetes-tenant-access-governance.md` for scope restrictions,
role preparation, read-back, revocation, and UAT evidence.

## Authority and degradation

KAORI preserves a single reconciliation authority for every Tenant capability. A Tenant using Capsule remains Capsule-owned while healthy and enters **Capsule Degraded** when required capability evidence is incomplete or unhealthy.

There is **no automatic fallback** from Capsule Degraded to Native Kubernetes. Existing materialized Kubernetes resources may continue to work, but KAORI does not silently relax Capsule-governed policy or let Native and Capsule reconcile the same capability concurrently.

## Native Recovery

A controlled **Native Recovery** is an explicit governance workflow:

1. commit a snapshot of effective Capsule governance;
2. verify which protections have enforceable Native equivalents;
3. materialize those Native Namespace, quota, LimitRange, RBAC, credential, and managed-resource protections;
4. verify effective Native enforcement;
5. transfer authority only after verification;
6. retain Activity evidence for the provider transition.

During Native Recovery, Capsule remains the reconciliation authority until the final verification succeeds. The transition to `native_kubernetes` is therefore reviewable, auditable, and fail-closed.

Advanced Capsule-only feature execution remains owned by #124. #121 provides discovery, provider safety, degradation, and recovery authority only.
