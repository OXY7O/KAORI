# Kubernetes Tenant Credential Governance

Issue #115 owns governed human and individually owned Kubernetes administrator credential lifecycle.

## Authority boundary

Tenant credentials are downstream of the canonical Tenant/Environment/Namespace, Membership, and Access Grant contracts.

- #114 remains authoritative for Viewer, Operator, Tenant Admin, Deployer, scope, Role, and RoleBinding semantics.
- #115 owns human credential identity, short-lived material issuance, renewal/rotation, suspend, expiry, revoke, JumpServer delivery references, exceptional human kubeconfig generation, and individually owned administrative kubeconfigs.
- #116 owns CI/CD Deployer credential lifecycle.
- Kubernetes remains authoritative for effective authentication/authorization state.
- KAORI never stores short-lived bearer tokens or generated kubeconfig material in routine Tenant credential records.

## Ordinary human credentials

Ordinary interactive access is **JumpServer-first**.

One canonical human credential record is owned by one active KAORI user in one Tenant for one normalized purpose and is bound to one active user Access Grant. Group grants cannot be converted into a shared human ServiceAccount credential.

The Native Kubernetes implementation materializes a dedicated ServiceAccount in every namespace targeted by the Access Grant and binds that ServiceAccount to the existing versioned Access Profile Role. The Access Profile itself is not copied or redefined.

ServiceAccounts use `automountServiceAccountToken: false`. Credential material is requested on demand through Kubernetes TokenRequest and is time-bound. The default token request is at most one hour and is additionally bounded by the credential entitlement and exceptional-delivery expiry.

A non-secret JumpServer reference is persisted. First-phase JumpServer session/command ingestion remains out of scope.

## Exceptional ordinary-user kubeconfig

Direct ordinary-user kubeconfig generation is not the default delivery path.

It requires:
- explicit `exceptional_kubeconfig` delivery state;
- an active KAORI administrator approver;
- a reason;
- a bounded exception expiry that cannot outlive the credential entitlement.

The generated kubeconfig is assembled in memory from the canonical cluster endpoint/CA transport metadata plus a fresh short-lived ServiceAccount token. It is returned only to the approved delivery workflow and is not persisted to the Tenant credential, AuditEvent, Notification, or normal list/detail surfaces.

## Administrative kubeconfigs

Administrative credentials are a separate credential type and cannot reuse an ordinary Tenant Access Grant.

Each record:
- has exactly one active KAORI administrator owner;
- uses an individually named ServiceAccount;
- uses one Ready managed namespace as the credential identity anchor;
- receives one KAORI-managed ClusterRoleBinding to the Kubernetes `cluster-admin` ClusterRole;
- generates kubeconfig material only on demand with a short-lived TokenRequest.

This privileged path is intentionally distinct from #114. #114 never creates ClusterRoleBinding.

Deleting the administrative ServiceAccount and ClusterRoleBinding removes effective access and invalidates bound ServiceAccount tokens independently from other administrators.

## Lifecycle

The default 365-day value is the governed entitlement/review period, not bearer-token lifetime.

Canonical states:
- Active
- Renewal Due
- Rotating
- Suspended
- Expired
- Revoked

Renewal deletes the previous effective provider identity, retires the current generation evidence, increments the generation, creates a new provider identity, and records new non-secret effective evidence. Old and new generations are independently traceable without storing their bearer material.

Suspend, Expired, and Revoked states remove effective ServiceAccount/binding state. Resume recreates a new effective identity only while the entitlement remains valid.

If a human Access Grant, membership, or owning user becomes invalid, reconciliation fails closed by revoking the dependent credential rather than preserving a credential-only authorization bypass.

## Namespace Access Package

The non-secret Namespace Access Package contains:
- Tenant, environment, namespace;
- cluster identity and API endpoint reference;
- Access Profile and version, or explicit `cluster-admin` for the privileged administrative path;
- approved access method;
- credential status;
- ServiceAccount identity;
- JumpServer reference where applicable;
- validity/renewal timestamps;
- rotation generation;
- allowed lifecycle actions.

It never contains a token, generated kubeconfig, client private key, or other bearer material.

## Evidence and drift

Credential records persist desired/effective hashes, reconciliation status/message, non-secret target evidence, last reconciliation timestamp, correlation ID, and generation records.

KAORI-owned ServiceAccounts and bindings carry `app.kubernetes.io/managed-by=kaori`, Tenant identity, and credential identity labels. Foreign provider ownership is never silently overwritten.

Routine AuditEvent evidence records lifecycle action, owner, type, delivery method, status, generation, validity, outcome, and correlation ID. Secret material is explicitly excluded.


## CI/CD deployer credentials

Issue #116 extends the same canonical credential lifecycle for GitHub Actions and Helm deployment identities.

A CI/CD Deployer credential:
- is a `deployer_service_account` credential with `cicd_kubeconfig` delivery;
- owns a dedicated Kubernetes ServiceAccount identity per application/environment credential;
- creates a first-class ServiceAccount Tenant membership and a namespace-scoped #114 Deployer Access Grant;
- never grants the machine-only Deployer profile to a User or Group membership;
- binds one accountable KAORI owner for governance without using that human identity as the Kubernetes RBAC subject;
- keeps application name, environment, namespace, purpose, credential status, rotation generation, and Access Grant evidence committed in KAORI.

The Deployer Access Profile remains versioned by #114 and excludes interactive troubleshooting, RBAC administration, namespace administration, and cluster-scoped privileges.

### CI/CD Namespace Access Package

The non-secret CI/CD Namespace Access Package contains Tenant/environment/namespace identity, application and purpose, cluster/API endpoint, a canonical cluster transport reference for CA/TLS material, Deployer profile/version, ServiceAccount identity, credential lifecycle state, rotation generation, and allowed actions.

Bearer tokens and generated kubeconfigs are never persisted in the package, inventory, Activity evidence, reports, or routine logs.

GitHub Actions and Helm obtain a short-lived TokenRequest credential only when an approved pipeline needs it. KAORI constructs the kubeconfig in memory from the canonical Kubernetes connection plus the short-lived ServiceAccount token. The pipeline consumes the ephemeral kubeconfig and does not receive a permanent shared administrator kubeconfig.

Suspend, expiry, revoke, and rotation reuse the canonical #115 lifecycle. Removing the dedicated ServiceAccount invalidates bound ServiceAccount token material while the Deployer Access Grant remains separately auditable and revocable.
