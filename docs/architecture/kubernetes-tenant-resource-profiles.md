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

## Resource Profile control-state UX

Resource Profile mutability is visible before an operator opens the detail dialog:

- **KAORI Preset · Locked** — Small, Standard, and Large are code-owned/versioned baselines. Registry action is **View**.
- **Custom · Editable** — operator-managed reusable allocation contract. Registry action is **Manage**.
- **Adopted Baseline · Observed** is allocation provenance, not a new built-in preset class. During #768 governed adoption, KAORI reads the live legacy ResourceQuota/LimitRange or admitted Capsule allocation evidence, commits the observed snapshot, and performs no provider mutation. It remains read-only until explicit allocation-governance cutover.
- If an observed baseline semantically matches a versioned Small/Standard/Large preset, KAORI records that preset only as lineage. The adopted Namespace still remains **Observed**, not KAORI-managed.
- A non-matching legacy allocation is preserved as a custom observed baseline snapshot without silently creating or mutating a reusable Custom Resource Profile.
- Unsupported dimensions, conflicting quota owners, ambiguous Capsule authority, or Capsule shared/global quota paths that do not yet have an admitted mutation contract are surfaced as **Control Unavailable**. Adoption may retain the provider evidence, but governed mutation fails closed.

Editing a Custom Resource Profile changes the reusable contract version only. It never silently rewrites an existing Namespace allocation snapshot.

## Adopted allocation governance cutover

Issue #769 owns the explicit transition from an observed legacy allocation to KAORI-managed allocation intent. Namespace lifecycle ownership and allocation reconciliation ownership are separate contracts:

```text
Namespace ownership: Adopted
Allocation control: Adopted / Observed → KAORI Managed
```

A successful allocation cutover does **not** relabel an adopted Namespace as KAORI-created or transfer Namespace deletion/lifecycle ownership. It authorizes KAORI to govern only the admitted allocation resources.

For the Native Kubernetes path, cutover performs:

1. read the committed Adopted / Observed allocation and provider UID/resourceVersion evidence;
2. compare the selected Resource Profile with the observed allocation;
3. run the existing #654 capacity admission;
4. re-read provider allocation and reject stale committed evidence;
5. verify ResourceQuota / LimitRange source ownership, UID, and resourceVersion before the first provider write;
6. patch the single authoritative legacy ResourceQuota / LimitRange in place, or create the canonical KAORI resource only when that resource type was absent;
7. read back the effective allocation;
8. mark `allocation_control_state=kaori_managed` only when provider read-back semantically equals the proposed contract.

The initial cutover supports at most one authoritative ResourceQuota and one Container LimitRange. Multiple legacy sources, unsupported LimitRange constraints, foreign controller ownership, stale UID/resourceVersion evidence, or ambiguous authority remain **Control Unavailable** until the operator resolves the provider state.

After successful cutover, subsequent allocation changes continue through the governed capacity/preflight and provider-verification path while Namespace `ownership_status` remains `adopted`.

Capsule is fail-closed. KAORI does not bypass Capsule by writing Native ResourceQuota when the adopted Tenant's effective allocation authority is Capsule. #771 admits exactly one shared Capsule allocation path: an unambiguous `GlobalResourceQuota` served through `capsule.clastix.io/v1beta2` while committed Capsule evidence reports `shared_global_quota=available`. The existing #124 CustomObjects executor remains the provider mutation primitive. `Tenant.spec.resourceQuotas`, multiple GlobalResourceQuota sources, unsupported selectors/dimensions, degraded Capsule, and unsupported API versions remain **Control Unavailable**.

Provider mutation failure never marks the allocation KAORI Managed. Failure evidence records the proposed contract and whether provider mutation may have started so later sync/drift reconciliation can determine the effective provider state without pretending the transaction succeeded.

## Managed allocation drift and bidirectional reconciliation

Issue #770 owns out-of-band allocation drift after an allocation contract has become **KAORI Managed**. This is intentionally separate from Namespace provider-absence drift: the Namespace may still exist and be healthy while its ResourceQuota or Container LimitRange differs from committed KAORI intent.

Tenant sync remains observation-only:

```text
KAORI Managed allocation
→ live provider observation
→ compare desired vs observed dimensions
→ commit allocation_drift evidence
→ Drifted
```

The drift evidence retains both sides of the decision:

- the last committed KAORI quota/LimitRange intent and profile/version lineage;
- the live provider quota/LimitRange snapshot and effective hash;
- provider allocation source resources, including UID/resourceVersion evidence;
- dimension-level differences;
- ownership/authority findings and explicit blocked reasons.

Sync never changes the provider and never changes KAORI desired intent merely because a difference is observed.

### Reapply KAORI Intent

**Reapply KAORI Intent** keeps the committed desired contract. Before mutation KAORI:

1. re-reads the provider and requires the live hash to still match the committed drift observation;
2. verifies allocation ownership/authority;
3. evaluates capacity using the **current live provider allocation as the current state** and the committed KAORI allocation as the proposed state;
4. performs the authoritative provider reconciliation;
5. reads back the provider allocation;
6. clears drift only after the effective provider state matches the committed KAORI contract.

The provider is read again at mutation time so a change occurring after capacity preflight still fails closed.

### Accept Provider State

**Accept Provider State** treats the currently observed provider allocation as proposed new KAORI intent. KAORI re-reads the provider, rejects stale drift evidence, validates supported dimensions and ownership, runs capacity/policy admission, and then commits the observed allocation as the new desired/effective snapshot.

Acceptance performs **no provider write merely to accept values that are already live**. The resulting evidence records `provenance=accepted_provider_state`, preserves allocation history, updates desired/effective hashes, and clears the drift evidence only after governance validation succeeds.

Both actions require a committed `Drifted` Namespace state and a Tenant lifecycle state of `Ready`. Teardown/decommission states remain blocked.

### Capsule shared allocation authority

#771 extends the same human-controlled lifecycle to the admitted Capsule `GlobalResourceQuota` path without converting shared quota into per-Namespace quota.

```text
Adopted Capsule Tenant
→ observed GlobalResourceQuota + capability evidence
→ explicit shared-allocation cutover
→ Tenant-level KAORI Managed allocation intent
→ Tenant Sync observes GlobalResourceQuota
→ Drifted when live quota differs
→ {Reapply KAORI Intent | Accept Provider State}
```

The canonical shared contract is stored as a Tenant-level `TenantAdvancedCapabilityIntent` with `allocation_governance_scope=tenant_shared`. Capacity governance counts that shared quota exactly once for the Tenant and excludes its correlated Namespace allocation snapshots from commitment arithmetic while shared authority is active. This prevents a 4 CPU / 8 GiB Tenant quota from being counted once per Namespace.

Cutover preserves the existing GlobalResourceQuota selectors and provider object identity, verifies UID/resourceVersion before mutation, changes only the governed quota contract, reuses the #124 capability-gated CustomObjects executor, and requires provider read-back before committing **KAORI Managed**.

Tenant Sync remains observation-only. GlobalResourceQuota resourceVersion changes are valid drift evidence rather than an observation error; UID replacement, capability degradation, ambiguous ownership, or unsupported authority still fail closed. **Reapply KAORI Intent** performs fresh-provider and shared-capacity checks before Capsule mutation. **Accept Provider State** performs the same governance checks but makes no redundant provider write and records whether the accepted values are customized relative to the retained Resource Profile lineage.

`Tenant.spec.resourceQuotas` is intentionally not admitted by #771 and remains **Control Unavailable**. KAORI never substitutes a Native ResourceQuota write for a Capsule-owned contract.

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
