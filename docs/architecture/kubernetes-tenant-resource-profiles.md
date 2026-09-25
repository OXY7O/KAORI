# Tenant Resource Profiles and Namespace Provisioning

Issue #113 owns the first managed Tenant mutation slice: administrator-driven namespace creation plus ResourceQuota and LimitRange intent/evidence.

## Ownership boundary

- Tenant Management owns committed tenancy intent, Resource Profile assignment, provisioning state, and reconciliation evidence.
- Kubernetes Inventory remains observational authority for collected namespace/resource state.
- This slice implements only the Native Kubernetes namespace/quota/limit baseline needed by #113.
- #120 remains authority for the broader Native Kubernetes Tenant capability/enforcement contract.
- Capsule-specific shared/global quota and advanced enforcement remain out of scope.

## Resource Profile contract

A profile is persisted as one of `small`, `standard`, `large`, or `custom` and stores only supported Kubernetes quota keys plus Container LimitRange defaults. Profile class is taxonomy, not an implicit hard-coded quota size: operational quota values are explicit persisted intent and must be supplied/approved by the operator or future policy authority.

Supported baseline quota keys:

- `requests.cpu`, `limits.cpu`
- `requests.memory`, `limits.memory`
- `pods`
- `persistentvolumeclaims`
- `requests.storage`
- `services`
- `configmaps`
- `secrets`

## Provisioning safety

Namespace names use the Kubernetes DNS-label contract. Native reconciliation materializes exactly three managed resources for this slice: Namespace, `kaori-tenant-quota`, and `kaori-tenant-limits`.

KAORI labels managed resources with `app.kubernetes.io/managed-by=kaori`. Existing resources that declare another manager are not silently overwritten. Provider errors and contract mismatches leave explicit failed or drifted provisioning evidence rather than a false Ready state.

The committed desired contract and verified effective contract are independently hashed. Ready requires hash equality after provider read-back.
