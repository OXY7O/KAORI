# Tenant Resource Profiles and Namespace Provisioning

Issue #113 owns the first managed Tenant mutation slice: administrator-driven namespace creation plus ResourceQuota and LimitRange intent/evidence.

## Ownership boundary

- Tenant Management owns committed tenancy intent, Resource Profile assignment, provisioning state, and reconciliation evidence.
- Kubernetes Inventory remains observational authority for collected namespace/resource state.
- This slice implements only the Native Kubernetes namespace/quota/limit baseline needed by #113.
- #120 remains authority for the broader Native Kubernetes Tenant capability/enforcement contract.
- Capsule-specific shared/global quota and advanced enforcement remain out of scope.

## Resource Profile contract

A profile is persisted as one of `small`, `standard`, `large`, or `custom` and stores only supported Kubernetes quota keys plus Container LimitRange defaults. `small`, `standard`, and `large` are KAORI-owned preset classes with server-side canonical values; the browser auto-fills those values but cannot override the service authority. `custom` is the only class that accepts operator-entered quota and LimitRange values.

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


## Preset classes

Preset classes are product policy, not provider discovery. The service layer is authoritative and ignores browser-supplied resource overrides for preset classes.

- **Small** — 1/2 CPU request/limit, 2/4 GiB memory request/limit, 10 pods, 5 PVCs, 50 GiB storage, and conservative per-container defaults.
- **Standard** — 2/4 CPU, 4/8 GiB memory, 20 pods, 10 PVCs, 100 GiB storage, and general-purpose per-container defaults.
- **Large** — 4/8 CPU, 8/16 GiB memory, 40 pods, 20 PVCs, 200 GiB storage, and higher per-container defaults.
- **Custom** — explicit operator values validated through the same safe Kubernetes quantity contract.

Changing preset values later is a governed product-policy change. Existing committed profiles retain their persisted values; they are not silently rewritten when preset defaults evolve.
