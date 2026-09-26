# Kubernetes Tenant Audit Correlation

Issue #122 defines the provider-neutral boundary between external Kubernetes audit evidence and KAORI Tenant governance.

KAORI is **not a raw audit-log mirror**. The Kubernetes audit source remains authoritative for the original event stream. KAORI stores only normalized correlation evidence needed to answer who/what identity acted, which Tenant scope was affected, which governed credential or Access Grant can be attributed, what Kubernetes resource/verb was involved, when it occurred, and whether the API operation succeeded.

## Normalized evidence

Committed observations contain bounded fields such as audit/event id, source reference, timestamp, authenticated username, ServiceAccount identity, Kubernetes object reference, verb, response code/outcome, correlation status, and canonical Tenant identifiers.

Routine ingestion never copies `requestObject`, `responseObject`, Secret data, bearer tokens, kubeconfigs, private keys, or arbitrary request/response bodies. Normal Activity evidence follows the same secret boundary.

## Correlation

KAORI correlates managed ServiceAccounts back to canonical human, administrator, or CI/CD credential ownership where the managed Tenant credential state provides a unique mapping. User and externally asserted Group subjects may be mapped through Tenant Membership and namespace-targeted Access Grants.

Correlation status is explicit:

- `managed` — exactly one active governed identity mapping;
- `managed_revoked` — ownership is known but the mapped credential/membership/grant is no longer active;
- `unmanaged` — no canonical Tenant identity mapping exists;
- `ambiguous` — multiple plausible governed identities exist and KAORI refuses to guess.

Unknown principals remain unmanaged evidence rather than being silently assigned.

## Idempotency and retention

The normalized event uid is unique and ingestion is idempotent. Source retries therefore do not create duplicate governance evidence. Every observation has an explicit retention expiry and may be purged through the bounded retention workflow.

Malformed/unavailable audit sources are recorded as operator-visible source errors without synthesizing fake Kubernetes operations.

## JumpServer boundary

Kubernetes audit proves Kubernetes API identity/action evidence. JumpServer session and command evidence is a separate later integration; #122 only preserves the canonical identity/correlation boundary so a future JumpServer session reference can be linked without replacing Kubernetes audit authority.
