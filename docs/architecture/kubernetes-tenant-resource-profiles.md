# Tenant Resource Profiles and Namespace Provisioning

Issue #113 owns the first managed Tenant mutation slice: administrator-driven namespace creation plus ResourceQuota and LimitRange intent/evidence. Fast Track review #777 extends the Resource Profile operator-control contract without reopening the completed #113 baseline.

## Ownership boundary

- Tenant Management owns committed tenancy intent, Resource Profile assignment, provisioning state, and reconciliation evidence.
- Kubernetes Inventory remains observational authority for collected namespace/resource state.
- This slice implements only the Native Kubernetes namespace/quota/limit baseline needed by #113.
- #120 remains authority for the broader Native Kubernetes Tenant capability/enforcement contract.
- #654 owns Tenant Allocation Budget arithmetic, aggregate commitment, capacity state, and allocation allow/block decisions.
- The original #113 baseline remains Native Kubernetes. Later bounded authorities #771 and #773 extend the same allocation lifecycle to admitted Capsule GlobalResourceQuota and legacy Tenant.spec.resourceQuotas paths without changing #113 ownership.

## Resource Profile contract

KAORI exposes five operator-facing Resource Profile classes:

- **Small** (`small`) — built-in, KAORI-owned, versioned, and fixed.
- **Medium** (`standard`) — built-in, KAORI-owned, versioned, and fixed. The persisted `standard` key is intentionally retained for backward compatibility.
- **Large** (`large`) — built-in, KAORI-owned, versioned, and fixed.
- **Extra Large** (`extra_large`) — built-in, KAORI-owned, versioned, and fixed.
- **Custom** (`custom`) — operator-managed and editable within the supported validation contract.

Built-in numeric values are server-authoritative; caller-supplied numeric overrides are ignored. Each supported quota or Container LimitRange dimension also has an explicit **Managed by KAORI** control. Checked means KAORI owns and materializes that dimension using the fixed preset value. Unchecked means the dimension is omitted from the committed profile/effective allocation and KAORI does not claim control over it.

The managed-dimension selection is therefore an **ownership mask**, not an inline preset override. A built-in profile can control only the dimensions required by an operator while preserving stable preset semantics.

When different numeric values are required, the operator must use a Custom profile. Custom may start empty or be **based on** Small, Medium, Large, or Extra Large. KAORI records the base preset class/version as lineage evidence while the resulting Custom values remain independently editable.

Blank/null or unmanaged supported quota/LimitRange dimensions mean **KAORI does not configure that dimension**. Zero remains a distinct explicit value and must not be conflated with missing/unmanaged state.

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

| Resource | Small | Medium | Large | Extra Large |
| --- | ---: | ---: | ---: | ---: |
| CPU requests | `1` | `2` | `4` | `8` |
| CPU limits | `2` | `4` | `8` | `16` |
| Memory requests | `2Gi` | `4Gi` | `8Gi` | `16Gi` |
| Memory limits | `4Gi` | `8Gi` | `16Gi` | `32Gi` |
| Pods | `10` | `20` | `40` | `80` |
| PVCs | `5` | `10` | `20` | `40` |
| Storage requests | `50Gi` | `100Gi` | `200Gi` | `400Gi` |
| Services | `5` | `10` | `20` | `40` |
| ConfigMaps | `25` | `50` | `100` | `200` |
| Secrets | `25` | `50` | `100` | `200` |
| Default CPU request | `100m` | `100m` | `250m` | `500m` |
| Default CPU limit | `250m` | `500m` | `1` | `2` |
| Default memory request | `128Mi` | `128Mi` | `256Mi` | `512Mi` |
| Default memory limit | `256Mi` | `512Mi` | `1Gi` | `2Gi` |

Changing these values is a governed product change and requires a new preset version. Existing namespace allocations do not silently inherit a later preset version.

## Resource Profile control-state UX

Resource Profile mutability is visible before an operator opens the detail dialog:

- **KAORI Preset · Locked** — Small, Medium, Large, and Extra Large are code-owned/versioned baselines. Registry action is **View**. Numeric values are immutable; Managed toggles select the KAORI-owned subset.
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

#771 does not admit `Tenant.spec.resourceQuotas`; #773 is the separate bounded authority for that legacy Capsule compatibility path. KAORI never substitutes a Native ResourceQuota write for a Capsule-owned contract.

### Capsule Tenant resource-quota authority

#773 admits an unambiguous Capsule `Tenant.spec.resourceQuotas` contract into the same canonical allocation lifecycle without merging it with GlobalResourceQuota authority.

The path is capability-gated. KAORI requires a healthy Capsule authority, a supported served Tenant CR API version, and live CRD schema evidence that `spec.resourceQuotas` exists. A no-op server-side dry-run is used only on explicit human mutation/reconciliation actions to prove the admission path before the real write; normal Tenant Sync remains read-only.

`resourceQuotas.scope` retains Capsule semantics:

- `Tenant` is one shared allocation contract for capacity accounting and is counted once for the Tenant;
- `Namespace` is a per-Namespace template and capacity accounting multiplies the governed request vector by the currently correlated Namespace count.

KAORI never silently changes scope during normal allocation changes. A manual scope change becomes drift and requires an explicit **Reapply KAORI Intent** or **Accept Provider State** decision.

For adopted legacy Tenants, the observed ordered `items` structure and hard-key ownership are preserved. Governed Resource Profile values update the supported `hard` dimensions in place. Non-hard quota semantics such as `scopes` / `scopeSelector`, unsupported quota keys, ambiguous duplicated dimensions, stale Tenant UID/resourceVersion evidence, or competing allocation authorities fail closed.

Namespace-side constraints that are not the selected allocation authority remain external evidence. A Capsule-generated `LimitRange` with `type=PersistentVolumeClaim` is parsed as a known **PVC Storage Constraint** rather than an opaque unsupported type: KAORI preserves the Namespace, LimitRange provider identity, UID/resourceVersion, and supported `storage` min/max/default evidence when present. This mapping is observational only and does not merge PVC size policy into `Tenant.spec.resourceQuotas`, ResourceQuota PVC count, or total `requests.storage` authority. Cutover and later Tenant-quota changes never delete or rewrite that external LimitRange.

The managed lifecycle is:

```text
Discovered
→ Adopted / Observed
→ explicit Tenant quota governance cutover
→ KAORI Managed
→ normal governed allocation changes through Tenant.spec.resourceQuotas
→ Tenant Sync observes provider state
→ Drifted on out-of-band change
→ {Reapply KAORI Intent | Accept Provider State}
```

Cutover and normal KAORI-managed changes re-read the Tenant CR, reject stale UID/resourceVersion evidence, run #654 capacity admission, patch only `spec.resourceQuotas`, and require provider read-back before committing effective state.

Tenant Sync performs no provider write. Drift evidence retains the last KAORI desired quota/scope, the current provider quota/scope, dimension-level differences, provider UID/resourceVersion, and external constraints.

**Reapply KAORI Intent** uses the fresh live provider quota as the current capacity state and the committed KAORI contract as the proposed state, then patches the authoritative Tenant CR and verifies read-back.

**Accept Provider State** treats the fresh live Tenant quota as proposed new intent, validates authority/scope/capacity, performs no redundant provider write, commits the live contract with `provenance=accepted_provider_state`, and returns allocation control to **KAORI Managed**.

Capsule now recommends newer Rules-based quota capabilities for new designs; KAORI treats `Tenant.spec.resourceQuotas` as a legacy compatibility authority for estates that already use it. #773 does not auto-migrate a legacy Tenant to another Capsule quota model because the external provider remains authoritative for that transition.

## Effective allocation evidence

A managed namespace records:

- source Resource Profile identifier;
- source Resource Profile version;
- committed quota snapshot;
- committed Container LimitRange snapshot;
- whether the selected profile is Custom;
- desired/effective hashes and provider read-back evidence.

For a built-in profile, namespace provisioning snapshots only the profile's managed dimensions, rehydrating every selected key from the canonical preset value so stored/operator input cannot mutate a fixed preset. Per-namespace inline numeric overrides are not accepted.

For a Custom profile, namespace provisioning snapshots the committed Custom profile values. If the Custom profile was based on a built-in preset, the Resource Profile also retains the base preset class/version lineage.

Later Resource Profile or built-in preset changes do not implicitly mutate namespace allocation intent. Existing namespace allocations change only through an explicit governed mutation that shows current versus proposed values, passes validation and #654 capacity preflight, then reconciles provider state.

## Provisioning safety

Namespace names use the Kubernetes DNS-label contract. Native reconciliation always manages the Namespace. It materializes `kaori-tenant-quota` and/or `kaori-tenant-limits` only when the committed allocation contains corresponding limits; an explicitly unbounded contract removes KAORI-owned quota/limit objects rather than inventing zero values.

KAORI labels managed resources with `app.kubernetes.io/managed-by=kaori`. Existing resources that declare another manager are not silently overwritten. Provider errors and contract mismatches leave explicit failed or drifted provisioning evidence rather than a false Ready state.

The committed desired contract and verified effective contract are independently hashed. Ready requires hash equality after provider read-back.


## Advanced profile controls

Resource Profiles persist **advanced control intent and its non-secret configuration values** in addition to allocation and Container LimitRange dimensions. This is an operator-editable reusable contract, not a status/TODO matrix and not an issue-reference UI.

The expandable Advanced Controls editor uses values that map to the already approved canonical KAORI contracts:

| Control | Persisted profile values |
| --- | --- |
| Ingress | enforcement mode (required or preflight-only) |
| Service Exposure | policy profile plus explicit ClusterIP / Ingress / NodePort / LoadBalancer / ExternalName allow/deny decisions |
| Hostname Reservation | exact/wildcard/regex match mode plus normalized hostname pattern |
| Managed TLS | platform/namespace-compatibility mode, resource name, and non-secret source reference |
| Managed Registry | image-pull/external-provider mode, resource name, and non-secret source reference |
| Capsule Namespace Controls | forceTenantPrefix intent plus namespaceOptions JSON |
| Capsule Resource Rules | container registry, PriorityClass, StorageClass lists, and Capsule rules JSON |
| Capsule Resource Pools | ResourcePool/ResourcePoolClaim kind, resource name, and desired spec JSON |
| Capsule Replication | TenantResource/GlobalTenantResource kind, resource name, and desired spec JSON |
| Capsule Tenant Cordon | cordon and deletion-protection booleans |

Secret/private-key/registry credential material is never persisted in Resource Profile JSON. The profile stores only non-secret configuration and source references.

Detailed reconciliation authority still stays in the canonical domain implementations:

- exposure/hostname values align with the existing Tenant exposure-policy and domain-reservation contracts;
- TLS/registry values align with the existing Tenant managed-resource modes;
- Capsule values align with the admitted Tenant.spec fields or advanced resource kinds already enforced by the Capsule advanced provider path.

The Resource Profile does not become a second provider model. It supplies reusable desired values to the existing canonical domains and keeps provider-specific execution capability-gated.

### Attachment evaluation

Advanced controls are evaluated when the Resource Profile is attached to a Tenant placement.

```text
profile control enabled + committed non-secret values
→ inspect Tenant provider authority
→ inspect committed provider capability evidence
→ enabled on placement OR unavailable
```

The Namespace Provisioning attachment preview shows the selected profile controls against the selected Tenant Environment. A requested control is:

- **Enabled** when the selected authoritative provider reports every required capability as available;
- **Unavailable** when the provider does not implement that control, is degraded, or required capability evidence is unavailable;
- **Off** when the Resource Profile did not enable the control.

The server re-evaluates this contract before Native Namespace provisioning. A requested but unavailable advanced control blocks the provider mutation before Namespace/ResourceQuota/LimitRange reconciliation starts. Successful provisioning records both the evaluated state and the persisted configuration snapshot in provisioning evidence.

Configuration validation is server-side. Invalid hostname patterns, unsupported managed-resource modes, malformed JSON, missing required resource names/specs, or a no-op Capsule cordon contract are rejected before commit.

KAORI never silently drops an enabled advanced control and never substitutes Native behavior for Capsule-only controls.

### Profile mutability

Small, Medium, Large, and Extra Large retain fixed numeric preset values. Their per-resource Managed ownership mask and selected advanced-control values are committed as part of the created profile contract.

Custom profiles can edit both numeric allocation intent and advanced-control values. Changing either increments the Custom profile contract version. Existing Namespace snapshots remain frozen until an explicit governed allocation/attachment workflow changes them.
