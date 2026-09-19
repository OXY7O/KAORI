# Compatibility Framework

Compatibility translates upstream product releases and observed provider behavior into stable KAORI contracts without coupling runtime logic to every release number.

## Authority model

KAORI uses five independent compatibility authorities:

```text
Annual KAORI lifecycle policy
        ↓
General capability contract
        ↓
Version qualification mapping
        ↓
Upstream lifecycle context
        ↓
Observed provider + consumer evidence
```

No single layer may silently replace another.

## Annual lifecycle policy

Compatibility support is governed by an annual policy generation.

The 2026 baseline is:

- policy key: `kaori-compatibility-policy-v1`;
- policy version: `v1`;
- policy year: `2026`;
- lookback: `5 years`;
- anchor year: `2021`;
- snapshot date: `2026-09-19`.

The annual calculation is:

```text
anchor_year = policy_year - lookback_years
lower_bound = latest stable release in anchor_year
upper_bound = latest stable release available at the annual policy snapshot
```

The lower and upper release values remain explicit source-controlled qualification evidence. The formula is the governance rule used to refresh them.

For policy v1 / 2026 the current anchors are:

| Product | 2021 anchor release | 2026 upper qualification |
|---|---|---|
| Kubernetes | v1.23 | v1.37 |
| Prometheus | v2.32 | v3.13.x |
| Alertmanager | v0.23 | v0.34.x |
| Thanos Query | v0.24 | v0.42.x |
| MinIO Community | `RELEASE.2021-12-29T06-49-06Z` | `RELEASE.2025-10-15T17-29-55Z` |

MinIO has no 2026 community release because the community repository is archived, so the upper bound remains the latest stable release available before the 2026 snapshot.

### Annual rollover

Each annual refresh creates a new lifecycle policy generation:

```text
2026 → kaori-compatibility-policy-v1 → anchor 2021
2027 → kaori-compatibility-policy-v2 → anchor 2022
2028 → kaori-compatibility-policy-v3 → anchor 2023
```

For example, the latest Kubernetes stable release in 2022 was v1.26. Therefore the 2027 policy refresh would use v1.26 as the Kubernetes lower-bound candidate and whatever stable Kubernetes release is current at the 2027 policy snapshot as the upper-bound candidate.

The annual refresh must be evidence-driven. It must not advance a product upper bound to an unreleased, release-candidate, or unvalidated build.

## Definition-driven version awareness

Runtime compatibility knowledge belongs in source-controlled definitions, not product/version branches in Python.

Each product definition declares:

- `selection_mode: automatic_detected_version`;
- the runtime `version_source`;
- the policy floor and upper qualification boundary;
- the default general contract used for future-unverified probing;
- presentation labels for the annual policy window.

Each qualification band declares:

- a version constraint;
- the general `contract_profile` for that band;
- a support posture;
- upstream lifecycle context;
- any additional mandatory capabilities introduced by that version band.

The generic resolver performs:

```text
detected runtime version
        ↓
match definition version band
        ↓
select band contract_profile
        ↓
merge core + band capability requirements
        ↓
evaluate live evidence
        ↓
derive Current / Extended / EOL / Future Unverified readiness
```

There is no operator-selected compatibility profile in the normal flow. Provider-specific version discovery supplies the detected version, and the resolver selects the matching definition band automatically.

A future breaking API generation therefore requires definition work first:

```yaml
contract_profiles:
- key: provider-core-v2
  required_capabilities:
  - new_required_api

qualifications:
- key: provider-current-v2
  version_constraint: '>=X,<Y'
  contract_profile: provider-core-v2
  support_level: current
```

The evaluator does not add `if product_version ...` branches for that transition. This is the architecture test for maintainability.

Non-semver products may use a provider-specific release comparator, but they follow the same definition → automatic match → contract → capability-evidence model. MinIO is the current date-release example.

## General contract profile

A general profile names the stable API/protocol/capability generation KAORI implements.

Current examples:

- `kubernetes-core-v1`;
- `prometheus-http-core-v1`;
- `alertmanager-api-v2-contract-v1`;
- `s3-object-storage-v1`.

General core contract versions are **not annual versions**. `core-vN` advances only for a breaking capability/API semantic change. If the annual lifecycle window shifts but the stable provider contract is unchanged, the same `core-vN` remains authoritative.

This creates two independent version axes:

```text
compatibility-policy-vN  → annual support governance
provider-core-vN         → stable API/capability contract generation
```

## Version qualification

A qualification row records:

- product identity;
- version/release range;
- general contract profile;
- KAORI support posture;
- upstream lifecycle context;
- any extra product-specific mandatory capability.

Adding a newly verified provider release should normally change qualification data instead of creating route/service/reader branches.

## Lifecycle states

A version is classified in this order:

| State | Meaning | Default readiness |
|---|---|---|
| Current | Inside the policy window and current upstream-qualified line | Ready after mandatory live evidence passes |
| Extended | Inside the KAORI five-year window but no longer current upstream | Degraded / supported with upgrade guidance |
| End of Life | Older than the annual policy lower bound | Blocked |
| Future Unverified | Newer than the annual policy upper bound | Degraded when the stable core contract still passes; never auto-qualified |
| Capability Mismatch | Mandatory contract capability is missing | Blocked |

Upstream lifecycle is useful context but is not by itself the operational readiness decision. KAORI may provide Extended support after upstream EOL, within the explicit five-year annual policy window.

## Observed capability and readiness

A qualified version can still be blocked when mandatory APIs, RBAC, TLS, credentials, metrics, labels, retention, or consumer signals fail.

A future version may be **Degraded / Unverified** when all mandatory general-contract probes pass. KAORI must not call that version fully compatible until the next qualification evidence update.

## Provider examples

### Kubernetes

Kubernetes uses `kubernetes-core-v1`.

For policy v1 / 2026:

- v1.23–v1.34: KAORI Extended;
- v1.35–v1.37: Current;
- <= v1.22: KAORI End of Life;
- >= v1.38: Future Unverified until explicitly qualified.

Live API resource discovery and feature-level SelfSubjectAccessReview evidence still decide actual feature readiness.

### Alertmanager

KAORI uses `alertmanager-api-v2-contract-v1`. Do not call this contract “Alertmanager v1”: Alertmanager API v1 is a historical/deprecated API name and would be ambiguous. API v2 status, alerts, and silences are mandatory provider capabilities.

### Prometheus and Thanos Query

Both providers map to `prometheus-http-core-v1`. Product identity remains independent, so Thanos retains historical-query semantics and additional identity checks without forking the core query contract.

### S3-compatible Object Storage / MinIO

`s3-object-storage-v1` owns basic S3 reachability and bucket discovery.

MinIO release identity is lifecycle/qualification evidence. A release older than the policy floor is End of Life. A newer unqualified release is not blocked by release string alone when mandatory S3 capability succeeds; it remains Future Unverified / Degraded until qualification evidence is promoted.

## Registry rule

Provider compatibility logic belongs in source-controlled definitions and profile resolvers. Routes, pages, analytics, reports, and consumers must not scatter hard-coded version comparisons.

Annual policy rollover should be a definition/evidence-test/document update. A rollover must not require product-version branches in runtime code. Even when the underlying core capability contract changes, the generic evaluator remains unchanged; the new core contract and its version-band mapping are added to definitions.
