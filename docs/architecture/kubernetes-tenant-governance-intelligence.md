# Kubernetes Tenant Governance Intelligence

Issue #123 adds the provider-neutral Kubernetes Tenant Governance rule family to the canonical Intelligence engine.

## Authority

Rule definitions remain in the existing Intelligence Definition Catalog and findings are produced by the same Recommendations pipeline used by other domains. Accepted-risk handling, Alert Case behavior, presentation, pagination, and downstream report consumption therefore reuse existing Intelligence governance rather than introducing a Tenant-specific rule engine.

The evaluator consumes committed Tenant evidence only:

- Tenant, Environment, Namespace, Resource Profile, Membership and Access Grant state;
- credential lifecycle and reconciliation state;
- managed TLS/registry intent and reconciliation evidence;
- provider state and provider_evidence_json;
- normalized Kubernetes audit correlation evidence from #122;
- Tenant Allocation decisions and capacity_state from #654;
- committed Tenant policy/production decision AuditEvent records.

The evaluator does not recompute Tenant Allocation Budget, does not issue a live provider request, and does not infer a provider-specific rule when the canonical evidence means the same thing for Native Kubernetes and Capsule.

## Evidence readiness

Rules with sufficient committed facts are evaluated into active Recommendations. Catalog definitions may exist before a safe evaluator signal is available; those definitions state their evidence boundary rather than guessing from utilization or provider state.

Runtime identity findings are based on normalized audit evidence. This allows KAORI to preserve attribution even when a credential is revoked, identify unknown/unmanaged principals, and distinguish human/admin access from CI/CD deployment identities.

Capacity rules consume the committed decision and capacity_state produced by #654. Utilization may be supporting context elsewhere, but Intelligence does not turn utilization alone into a Tenant allocation-admission decision.

## Operator response

Recommendations expose the canonical evidence, risk, and a concrete operator action. Existing Rule Exception / accepted-risk governance remains authoritative for documented false positives or temporary accepted conditions. No remediation automation beyond already-approved Intelligence mechanisms is introduced by #123.
