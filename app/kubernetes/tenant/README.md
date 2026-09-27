# Kubernetes Tenant Management

Issue #61 is the parent product authority. Issue #125 owns the integrated Tenant workspace and final end-to-end UAT composition over the bounded implementation authorities #112–#124, #654, and #655.

## Product boundary

KAORI exposes one `Kubernetes → Tenant` sidebar destination. Tenant is a capability/domain; Native Kubernetes and Capsule are provider implementations behind the same canonical Tenant model.

The integrated workspace uses internal surfaces:

- **Management** — governed mutations for Tenant, Resource Profile, namespace allocation/provisioning, membership/access, human access credentials, CI/CD deployer credentials, and credential lifecycle.
- **Inventory** — committed Tenant, namespace, credential, managed-resource, policy, provider-authority, and Kubernetes audit-correlation evidence.
- **Analytics** — committed capacity/admission evidence, Tenant Governance Intelligence findings, and canonical Reports entry points.

These are content-level workspace destinations. They do not create provider-specific sidebar branches and do not override the locked sidebar authority in `docs/design/components/SIDEBAR_NAVIGATION.md`.

## Evidence and provider authority

Normal Tenant workspace reads are composed from committed KAORI state. Live provider calls remain inside the owning mutation/reconciliation adapters.

- Native Kubernetes is the mandatory baseline provider.
- Capsule is capability-aware and optional.
- Degraded/unavailable Capsule capabilities fail closed.
- Provider state and reconciliation authority are explicit committed evidence.
- Capsule-only advanced mutations require admitted compatible capability evidence.
- Native Recovery remains an explicit governed authority transfer, never an automatic fallback.

## Access and credential boundary

KAORI application RBAC (`tenant.view`, `tenant.manage`) is separate from Tenant Kubernetes Membership and Access Grant authorization.

The routine UI may show non-secret access metadata such as:

- Tenant/environment/namespace and cluster identity;
- Access Profile/version;
- approved access method;
- ServiceAccount name;
- lifecycle/reconciliation state;
- renewal/review and validity times;
- rotate/suspend/resume/revoke actions.

Routine Tenant pages must never render bearer tokens, generated kubeconfig content, certificate/private-key material, or registry Secret material.

Human access issuance uses the admitted #115 service and binds an individually owned reconciled User Access Grant to a non-secret JumpServer reference. CI/CD issuance uses the admitted #116 Deployer service and creates a namespace-scoped machine principal/grant/credential lineage.

## Intelligence and reporting

Tenant does not own a second Intelligence engine or export subsystem.

- Tenant Governance findings are selected from the canonical Intelligence Recommendations authority using `kubernetes.tenant.*` rule keys.
- PDF, XLSX, and CSV publication is routed through the canonical Reports publication lifecycle from #655.
- Missing/stale evidence remains explicit; absence of provider/capacity evidence is never converted into a healthy or zero value.

## Final UAT boundary

Native-provider acceptance is mandatory. Final UAT must exercise, as applicable:

1. Tenant/environment creation.
2. Resource Profile and governed namespace provisioning.
3. Membership and Access Grant creation/revocation.
4. Human JumpServer credential issuance and lifecycle.
5. CI/CD Deployer identity issuance.
6. Namespace Access metadata without secret exposure.
7. Managed-resource, policy, provider-state, Activity, and Kubernetes audit evidence inspection.
8. Tenant Governance findings and capacity admission evidence.
9. Representative Tenant Governance PDF/XLSX/CSV generation and human artifact review.

Capsule UAT is capability-conditional and must record the exact compatible Capsule evidence when available. Fixture-only Capsule state is not acceptance evidence.

Promotion to `main` is outside this issue. Accepted Tenant work remains in `kaori/staging` until the governed release/promotion flow.
