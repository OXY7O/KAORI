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

As approved on 2026-09-25:

- `small`, `standard`, and `large` are KAORI-owned **initial-fill presets**, not immutable allocation locks;
- selecting a preset fills approved starting values in the operator UI, but every supported field remains editable before commit;
- the server validates and persists the submitted values rather than replacing caller changes with preset defaults;
- blank/null quota or LimitRange dimensions mean **no Tenant limit configured for that dimension**; blank is distinct from zero;
- the reusable Resource Profile keeps its own version while each namespace stores a frozen effective allocation snapshot and the source profile version used to create it;
- later profile changes must not silently rewrite an already committed namespace allocation;
- allocation changes that require capacity admission are governed by #654 before provider reconciliation.

Supported baseline quota keys:

- `requests.cpu`, `limits.cpu`
- `requests.memory`, `limits.memory`
- `pods`
- `persistentvolumeclaims`
- `requests.storage`
- `services`
- `configmaps`
- `secrets`

### Approved initial-fill preset values

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

### Effective allocation evidence

A managed namespace records:

- source Resource Profile identifier;
- source Resource Profile version;
- committed quota snapshot;
- committed Container LimitRange snapshot;
- whether the namespace allocation is customized;
- desired/effective hashes and provider read-back evidence.

This snapshot is the allocation intent consumed by reconciliation and later by #654 capacity governance. Resource Profile edits remain reusable-profile changes; they do not implicitly mutate namespace allocation intent.

## Provisioning safety

Namespace names use the Kubernetes DNS-label contract. Native reconciliation always manages the Namespace. It materializes `kaori-tenant-quota` and/or `kaori-tenant-limits` only when the committed allocation contains corresponding limits; an explicitly unbounded contract removes KAORI-owned quota/limit objects rather than inventing zero values.

KAORI labels managed resources with `app.kubernetes.io/managed-by=kaori`. Existing resources that declare another manager are not silently overwritten. Provider errors and contract mismatches leave explicit failed or drifted provisioning evidence rather than a false Ready state.

The committed desired contract and verified effective contract are independently hashed. Ready requires hash equality after provider read-back.
