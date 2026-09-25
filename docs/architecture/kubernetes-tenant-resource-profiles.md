# Tenant Resource Profiles and Namespace Provisioning

Issue #113 owns the first managed Tenant mutation slice: administrator-driven namespace creation plus ResourceQuota and LimitRange intent/evidence.

## Ownership boundary

- Tenant Management owns committed tenancy intent, Resource Profile assignment, provisioning state, and reconciliation evidence.
- Kubernetes Inventory remains observational authority for collected namespace/resource state.
- This slice implements only the Native Kubernetes namespace/quota/limit baseline needed by #113.
- #120 remains authority for the broader Native Kubernetes Tenant capability/enforcement contract.
- Capsule-specific shared/global quota and advanced enforcement remain out of scope.

## Resource Profile contract

A profile is persisted as one of `small`, `standard`, `large`, or `custom` and stores only supported Kubernetes quota keys plus Container LimitRange defaults. `small`, `standard`, and `large` are canonical KAORI presets: the UI auto-fills their values and the backend ignores caller-supplied resource overrides for those classes. `custom` is the only class that accepts operator-entered quota and LimitRange values. Preset values remain explicit committed KAORI intent and are changed only through a governed product update.

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


## Canonical preset values

| Class | CPU req/limit | Memory req/limit | Pods | PVCs | Storage | Services | ConfigMaps | Secrets | Container req | Container limit |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- | --- |
| Small | 1 / 2 | 2Gi / 4Gi | 10 | 5 | 50Gi | 5 | 25 | 25 | 100m / 128Mi | 250m / 256Mi |
| Standard | 2 / 4 | 4Gi / 8Gi | 20 | 10 | 100Gi | 10 | 50 | 50 | 100m / 128Mi | 500m / 512Mi |
| Large | 4 / 8 | 8Gi / 16Gi | 40 | 20 | 200Gi | 20 | 100 | 100 | 250m / 256Mi | 1000m / 1Gi |

The table is the human-readable representation of `app/kubernetes/tenant/resource_profiles.py`; the Python contract is the execution authority.
