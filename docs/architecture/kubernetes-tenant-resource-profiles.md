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

- `small` — built-in, KAORI-owned, versioned, locked in normal operator workflows.
- `standard` — built-in, KAORI-owned, versioned, locked in normal operator workflows.
- `large` — built-in, KAORI-owned, versioned, locked in normal operator workflows.
- `custom` — operator-managed and editable within the supported validation contract.

Small, Standard, and Large are canonical presets rather than loose taxonomy labels. Their ResourceQuota and Container LimitRange values are governed product defaults and cannot be overridden inline while retaining the built-in profile identity.

When an operator requires different values, KAORI must use a Custom profile. A Custom profile may be created from an empty baseline or **based on** a built-in preset. In the latter case, the selected preset values become the Custom profile's initial values while KAORI retains the base preset identity/version as lineage evidence.

Supported baseline quota keys:

- `requests.cpu`, `limits.cpu`
- `requests.memory`, `limits.memory`
- `pods`
- `persistentvolumeclaims`
- `requests.storage`
- `services`
- `configmaps`
- `secrets`

Blank/null supported quota fields mean no Tenant quota for that dimension. Zero is a distinct value and must not be treated as blank.

## Versioning and effective allocation

Built-in presets are versioned. A namespace records both:

1. the source Resource Profile identity/version; and
2. the effective allocation snapshot committed to that namespace.

Changing a built-in preset produces a new governed version. Existing namespaces do not silently inherit the new values and remain associated with their previously committed source version/effective snapshot until an explicit migration/reconciliation is approved.

A namespace that requires values different from Small, Standard, or Large must use a Custom profile. KAORI must not preserve a misleading built-in label for an overridden allocation.

Existing namespace allocations may change only through a governed mutation that:

- shows current versus proposed values;
- preserves source/effective allocation evidence;
- performs validation and the #654 capacity preflight before provider reconciliation;
- leaves the current committed/provider allocation unchanged when preflight is denied;
- records actionable decision/reconciliation evidence.

## Provisioning safety

Namespace names use the Kubernetes DNS-label contract. Native reconciliation materializes exactly three managed resources for this slice: Namespace, `kaori-tenant-quota`, and `kaori-tenant-limits`.

KAORI labels managed resources with `app.kubernetes.io/managed-by=kaori`. Existing resources that declare another manager are not silently overwritten. Provider errors and contract mismatches leave explicit failed or drifted provisioning evidence rather than a false Ready state.

The committed desired contract and verified effective contract are independently hashed. Ready requires hash equality after provider read-back.
