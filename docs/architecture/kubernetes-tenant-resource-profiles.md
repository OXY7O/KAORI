# Tenant Resource Profiles and Namespace Provisioning

Issue #113 owns the first managed Tenant mutation slice: administrator-driven namespace creation plus ResourceQuota and LimitRange intent/evidence.

## Ownership boundary

- Tenant Management owns committed tenancy intent, Resource Profile assignment, provisioning state, and reconciliation evidence.
- Kubernetes Inventory remains observational authority for collected namespace/resource state.
- This slice implements only the Native Kubernetes namespace/quota/limit baseline needed by #113.
- #120 remains authority for the broader Native Kubernetes Tenant capability/enforcement contract.
- #654 owns Tenant Allocation Budget arithmetic, aggregate commitment, capacity state, and allocation allow/block decisions.
- Capsule-specific shared/global quota and advanced enforcement remain out of scope.

## Resource Profile contract

KAORI exposes four Resource Profile classes:

- `small` — built-in, KAORI-owned, versioned, and locked in normal operator workflows.
- `standard` — built-in, KAORI-owned, versioned, and locked in normal operator workflows.
- `large` — built-in, KAORI-owned, versioned, and locked in normal operator workflows.
- `custom` — operator-managed and editable within the supported validation contract.

Small, Standard, and Large are canonical presets. Their ResourceQuota and Container LimitRange values are server-authoritative; caller-supplied field overrides are ignored for those classes.

When different values are required, the operator must use a Custom profile. Custom may start empty or be **based on** Small, Standard, or Large. KAORI records the base preset class/version as lineage evidence while the resulting Custom values remain independently editable.

Blank/null supported quota or LimitRange dimensions mean **no Tenant limit configured for that dimension**. Blank is distinct from zero.

Supported baseline quota keys:

- `requests.cpu`, `limits.cpu`
- `requests.memory`, `limits.memory`
- `pods`
- `persistentvolumeclaims`
- `requests.storage`
- `services`
- `configmaps`
- `secrets`

### Built-in preset values — version 1

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

Changing these values is a governed product change and requires a new preset version. Existing namespace allocations do not silently inherit a later preset version.

## Effective allocation evidence

A managed namespace records:

- source Resource Profile identifier;
- source Resource Profile version;
- committed quota snapshot;
- committed Container LimitRange snapshot;
- whether the selected profile is Custom;
- desired/effective hashes and provider read-back evidence.

For a built-in profile, namespace provisioning snapshots the canonical preset values; per-namespace inline overrides are not accepted.

For a Custom profile, namespace provisioning snapshots the committed Custom profile values. If the Custom profile was based on a built-in preset, the Resource Profile also retains the base preset class/version lineage.

Later Resource Profile or built-in preset changes do not implicitly mutate namespace allocation intent. Existing namespace allocations change only through an explicit governed mutation that shows current versus proposed values, passes validation and #654 capacity preflight, then reconciles provider state.

## Provisioning safety

Namespace names use the Kubernetes DNS-label contract. Native reconciliation always manages the Namespace. It materializes `kaori-tenant-quota` and/or `kaori-tenant-limits` only when the committed allocation contains corresponding limits; an explicitly unbounded contract removes KAORI-owned quota/limit objects rather than inventing zero values.

KAORI labels managed resources with `app.kubernetes.io/managed-by=kaori`. Existing resources that declare another manager are not silently overwritten. Provider errors and contract mismatches leave explicit failed or drifted provisioning evidence rather than a false Ready state.

The committed desired contract and verified effective contract are independently hashed. Ready requires hash equality after provider read-back.
