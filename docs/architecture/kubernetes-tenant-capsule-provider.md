# Kubernetes Tenant Capsule Provider

Issue #121 implements Capsule as an optional capability-aware provider over the same canonical KAORI Tenant domain. Native Kubernetes remains the baseline provider; Capsule is a capability unlock rather than a hard dependency.

## Supported discovery contract

KAORI recognizes the Capsule API group `capsule.clastix.io` and the currently supported Tenant API versions `v1beta2` and `v1beta1`. Discovery records the served Tenant CRD versions and the reported Capsule application version when available.

CRD discovery covers the Tenant controller and explicit advanced resource types such as TenantResource, GlobalTenantResource, GlobalResourceQuota, ResourcePool, and ResourcePoolClaim. CRD presence alone does not prove non-CRD surfaces such as Capsule Proxy or admission health; those require explicit probe evidence.

## Capability states

Capsule is not modeled as a boolean. The provider reports capability evidence for:

- Tenant controller and supported CRD version;
- admission enforcement;
- Capsule Proxy;
- shared/global quota;
- resource pools/claims;
- TenantResource / GlobalTenantResource replication.

Only `available` capabilities may authorize security-sensitive mutations. Degraded or unavailable capabilities fail closed.

## Authority and degradation

KAORI preserves a single reconciliation authority for every Tenant capability. A Tenant using Capsule remains Capsule-owned while healthy and enters **Capsule Degraded** when required capability evidence is incomplete or unhealthy.

There is **no automatic fallback** from Capsule Degraded to Native Kubernetes. Existing materialized Kubernetes resources may continue to work, but KAORI does not silently relax Capsule-governed policy or let Native and Capsule reconcile the same capability concurrently.

## Native Recovery

A controlled **Native Recovery** is an explicit governance workflow:

1. commit a snapshot of effective Capsule governance;
2. verify which protections have enforceable Native equivalents;
3. materialize those Native Namespace, quota, LimitRange, RBAC, credential, and managed-resource protections;
4. verify effective Native enforcement;
5. transfer authority only after verification;
6. retain Activity evidence for the provider transition.

During Native Recovery, Capsule remains the reconciliation authority until the final verification succeeds. The transition to `native_kubernetes` is therefore reviewable, auditable, and fail-closed.

Advanced Capsule-only feature execution remains owned by #124. #121 provides discovery, provider safety, degradation, and recovery authority only.
