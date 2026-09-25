# Tenant Resource Profiles and Namespace Provisioning

Issue #113 owns the first managed Tenant mutation slice: administrator-driven namespace creation plus ResourceQuota and LimitRange intent/evidence.

## Ownership boundary

- Tenant Management owns committed tenancy intent, Resource Profile assignment, provisioning state, and reconciliation evidence.
- Kubernetes Inventory remains observational authority for collected namespace/resource state.
- This slice implements only the Native Kubernetes namespace/quota/limit baseline needed by #113.
- #120 remains authority for the broader Native Kubernetes Tenant capability/enforcement contract.
- Capsule-specific shared/global quota and advanced enforcement remain out of scope.

## Resource Profile contract

A profile is persisted as one of `small`, `standard`, `large`, or `custom` and stores only supported Kubernetes quota keys plus Container LimitRange defaults.

As approved in the #113 Resource Profile preset refinement on 2026-09-25:

- `small`, `standard`, and `large` are KAORI-owned canonical presets;
- preset quota and LimitRange values are server-authoritative and caller-supplied resource overrides are ignored;
- the UI may auto-fill and lock preset values, but browser state is never the authority;
- `custom` is the only class that accepts operator-entered quota and LimitRange values;
- changes to canonical preset sizing require a governed KAORI product change rather than implicit provider defaults.

Supported baseline quota keys:

- `requests.cpu`, `limits.cpu`
- `requests.memory`, `limits.memory`
- `pods`
- `persistentvolumeclaims`
- `requests.storage`
- `services`
- `configmaps`
- `secrets`

### Canonical preset values

| Resource | Small | Standard | Large |
| --- | ---: | ---: | ---: |
| CPU requests | `1` | `2` | `4` |
| CPU limits | `2` | `4` | `8` |
| Memory requests | `2Gi` | `4Gi` | `8Gi` |
| Memory limits | `4Gi` | `8Gi` | `16Gi` |
| Pods | `10` | `20` | `40` |
| PVCs | `5` | `10` | `20` |
| Storage requests | `50Gi` | `100Gi` | `200Gi` |
| Services | `5` | `10` | `20` |
| ConfigMaps | `25` | `50` | `100` |
| Secrets | `25` | `50` | `100` |
| Default CPU request | `100m` | `100m` | `250m` |
| Default CPU limit | `250m` | `500m` | `1` |
| Default memory request | `128Mi` | `128Mi` | `256Mi` |
| Default memory limit | `256Mi` | `512Mi` | `1Gi` |

## Provisioning safety

Namespace names use the Kubernetes DNS-label contract. Native reconciliation materializes exactly three managed resources for this slice: Namespace, `kaori-tenant-quota`, and `kaori-tenant-limits`.

KAORI labels managed resources with `app.kubernetes.io/managed-by=kaori`. Existing resources that declare another manager are not silently overwritten. Provider errors and contract mismatches leave explicit failed or drifted provisioning evidence rather than a false Ready state.

The committed desired contract and verified effective contract are independently hashed. Ready requires hash equality after provider read-back.
