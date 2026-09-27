# Kubernetes Tenant Advanced Capsule Capabilities

Issue #124 unlocks advanced Capsule-only features through the existing provider-neutral Tenant domain after #121 established discovery, degradation, and authority safety.

## Capability authority

Every advanced operation requires the specific discovered capability to be `available` in committed Capsule evidence. A healthy Tenant controller alone is not enough. When Capsule is degraded, a capability is unavailable, or the served API does not include `capsule.clastix.io/v1beta2`, mutation paths fail closed.

KAORI keeps a single reconciliation authority. Native mode does not emulate Capsule-only semantics and no advanced operation automatically falls back to Native Kubernetes.

## Executable advanced resources

KAORI uses the existing Kubernetes integration and CustomObjects API for resources whose Capsule API contract is explicit:

- `GlobalResourceQuota` — cluster scoped; gated by `shared_global_quota`;
- `ResourcePool` — cluster scoped and `ResourcePoolClaim` — namespaced; gated by `resource_pools`;
- `TenantResource` — namespaced and `GlobalTenantResource` — cluster scoped; gated by `replication`.

Tenant-level controls patch only approved `Tenant.spec` fields:

- cordon/deletion protection: `cordoned`, `preventDeletion`;
- namespace controls: `forceTenantPrefix`, `namespaceOptions`;
- resource policy: `containerRegistries`, `priorityClasses`, `storageClasses`, and `rules` for supported registry/Ingress/Service enforcement.

Proxy remains a discovered read-only capability and is not treated as an independent KAORI authority.

## Cross-namespace credentials

Cross-namespace credential scope is evidence-only in this workstream: the specific Capsule capability must be available and the requested namespace set must be a subset of explicitly approved namespaces. Secret or kubeconfig material is never persisted in the advanced intent.

self-service namespace creation remains disabled because #124 does not expose an executable self-service resource kind. Discovery may report the provider capability, but a separate approval is still required before product workflow can enable it.

## Evidence and lifecycle

Advanced intent records store desired/effective non-secret specification, hashes, provider API version, capability key, status, correlation ID, and reconciliation evidence. Create, reconcile, drift, disable/delete, and Tenant-spec reset actions produce Activity Audit evidence with `secret_material_persisted=false`.

Live staging UAT is capability-conditional. The final Tenant UAT must record the exact Capsule version and discovered capabilities; absent or degraded features remain unavailable rather than being inferred from fixtures.
