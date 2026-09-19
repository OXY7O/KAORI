# Compatibility Framework

Compatibility translates upstream product versions and observed provider behavior into stable KAORI contracts without coupling runtime logic to every release number.

## Four authority layers

```text
Upstream product + detected version
        ↓
Version qualification mapping
        ↓
General capability contract
        ↓
Observed provider capabilities
        ↓
Consumer binding readiness
```

### General contract profile

A general profile names the API/protocol/capability generation KAORI implements.

Current examples:

- `kubernetes-core-v1`;
- `prometheus-http-core-v1`;
- `alertmanager-api-v2-contract-v1`;
- `s3-object-storage-v1`.

Multiple product versions can map to the same general profile. Prometheus and Thanos Query intentionally share the Prometheus HTTP core contract while preserving independent provider identities.

### Version qualification

A qualification row records:

- product identity;
- version/release range;
- general contract profile;
- KAORI support posture;
- upstream lifecycle context;
- any extra product-specific mandatory capability.

Adding a newly verified provider release should normally change qualification data instead of creating route/service/reader branches.

### Upstream lifecycle

Upstream lifecycle is useful operator context but is not a runtime readiness decision. A version can be current upstream and still be unverified by KAORI, or legacy upstream while still carrying an explicit KAORI legacy-qualified posture.

### Observed capability and readiness

Compatibility expectation and runtime evidence are distinct. A qualified version can still be blocked when mandatory APIs, RBAC, TLS, credentials, or consumer signals fail.

An unqualified future version may be **Degraded / Unverified** when all mandatory general-contract probes pass. KAORI must not call that version fully compatible until qualification evidence is promoted.

## Provider examples

### Kubernetes

Kubernetes uses the general `kubernetes-core-v1` contract. Version qualification provides lifecycle/support context; live API resource discovery and feature-level SelfSubjectAccessReview evidence decide actual feature readiness.

### Alertmanager

KAORI uses `alertmanager-api-v2-contract-v1`. Do not call this contract “Alertmanager v1”: Alertmanager API v1 is a historical/deprecated API name and would be ambiguous. API v2 status, alerts, and silences are mandatory provider capabilities.

### Prometheus and Thanos Query

Both providers can map to `prometheus-http-core-v1`. Product identity remains independent, so Thanos can retain historical-query semantics and additional identity checks without forking the core query contract.

### S3-compatible Object Storage / MinIO

`s3-object-storage-v1` owns basic S3 reachability and bucket discovery. MinIO product/release qualification is supporting evidence. A newer MinIO release must not be blocked by its release string alone when the mandatory S3 contract succeeds; it remains Unverified / Degraded until qualification evidence is added.

## Registry rule

Provider compatibility logic belongs in source-controlled definitions and profile resolvers. Routes, pages, analytics, reports, and consumers must not scatter hard-coded version comparisons.

Unknown future versions must never be silently treated as fully compatible, and qualification must never bypass mandatory live capability checks.
