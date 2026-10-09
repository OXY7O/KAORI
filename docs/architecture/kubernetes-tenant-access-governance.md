# Kubernetes Tenant Access Governance

Issue #114 owns the provider-neutral Tenant membership, Access Profile, and Access Grant contract. Issue #690 clarifies the identity-group, scope, revocation, and operator-guidance semantics of that contract.

## Authority boundary

KAORI application RBAC and Tenant Kubernetes RBAC are separate authorization layers.

- KAORI application permissions such as `tenant.view` and `tenant.manage` control who may operate the Tenant Management product.
- Tenant memberships and Access Grants control what a governed principal may do inside selected Kubernetes tenant scope.
- A Tenant Access Grant never grants KAORI application permissions.
- Kubernetes authentication establishes the user/group identity presented to the API server.
- Native Kubernetes remains authoritative for effective Role/RoleBinding enforcement.
- An external IdP/authenticator remains authoritative for membership of an externally asserted identity group.
- Credential creation, token delivery, JumpServer access, and GitHub Actions credential material remain owned by #115 and #116.

KAORI application login/SSO and Kubernetes authentication are separate identity/authorization domains unless an explicitly supported integration maps them. Logging in to KAORI through an SSO provider does not by itself make the same user or group identity available to Kubernetes.

## Canonical terminology

Use these terms consistently in implementation, documentation, and operator-facing copy:

- **User Principal** — one authenticated user subject that Kubernetes can recognize.
- **Identity Group** — a group identity asserted by the Kubernetes authentication layer or an approved connected IdP/authenticator. The identity source is authoritative for who belongs to that group.
- **Tenant Group** — KAORI registration/binding of one Kubernetes Group subject to one Tenant. A Tenant Group is not a KAORI-owned list of users in Tenant Management v1.
- **Tenant Membership** — registers one User Principal or Tenant Group as an active principal of one Tenant.
- **Access Profile** — a versioned least-privilege contract such as Viewer, Operator, Tenant Admin, or Deployer.
- **Access Grant** — assigns one Access Profile to one active Tenant Membership at exactly one scope.
- **Tenant Scope** — all managed/adopted namespaces under the selected Tenant.
- **Environment Scope** — all managed/adopted namespaces under one selected Tenant Environment.
- **Namespace Scope** — exactly one managed/adopted Tenant Namespace.

Do not use `Group` alone when the context could be confused with a KAORI-local user collection. Prefer `Identity Group`, `Tenant Group`, or `Kubernetes Group subject` according to the specific layer being discussed.

## Canonical access model

```text
Kubernetes authentication / IdP
  -> User Principal or Identity Group
      -> KAORI Tenant Membership
          -> Access Grant
              -> Scope (Tenant / Environment / Namespace)
              -> Versioned Access Profile
              -> Native Role + RoleBinding evidence
```

A membership freezes the Kubernetes subject name used by the current provider translation. Membership and grant lifecycle are independent so revoking one grant does not require deleting or revoking the principal's Tenant Membership.

### Group identity ownership

Kubernetes RBAC does not store the users that belong to a Group. During authentication, the API server receives a username plus zero or more group names. A RoleBinding whose subject is `kind: Group` authorizes requests when one of those authenticated group names matches the RoleBinding subject name.

Therefore:

- a Tenant Group `subject_name` must match a group identity that the Kubernetes authentication path can actually assert;
- adding or removing people from the underlying Identity Group happens in the authoritative IdP/authenticator, not in KAORI Tenant Management v1;
- KAORI owns the Tenant registration/binding, Access Grant, reconciliation evidence, governance state, and audit trail;
- creating a Tenant Group record does not create that group in an IdP;
- a generated/local-looking Tenant Group subject is effective only when the Kubernetes authentication path is configured to assert that exact group name.

Example:

```text
Authoritative IdP
Identity Group: platform-developers
Members: Alice, Bob, Doni
          |
          | authentication asserts group "platform-developers"
          v
Kubernetes API
          |
          | RoleBinding subject kind=Group, name=platform-developers
          v
KAORI Tenant access intent
Payment Platform -> platform-developers -> Operator -> Development
```

KAORI does not maintain the Alice/Bob/Doni membership list in this v1 flow. If KAORI later owns local group membership, that requires a separate identity-projection/authentication contract capable of making those group memberships authoritative to Kubernetes; a database-only group list is insufficient.

## Tenant Group lifecycle

A Tenant Group is KAORI's registration/binding of one Kubernetes Group subject to one Tenant. It does not copy or manage the external IdP membership list.

The normal operator lifecycle is:

- **Edit** corrects the display name or Kubernetes Group Subject while retaining the stable Tenant Group slug and correlation lineage.
- A Kubernetes Group Subject change is security-relevant: KAORI updates the bound Group Membership subject and reconciles every active dependent Access Grant to the new subject.
- If provider reconciliation cannot complete, the new subject remains committed desired state and the affected grant surfaces reconciliation attention for explicit recovery.
- **Retire** replaces routine hard delete. Retire is allowed only after active Membership is revoked and previous Access Grant cleanup is provider-verified.
- **Reactivate** returns a retired Tenant Group to future Membership selection.
- Routine Tenant UI does not hard-delete Tenant Group records that may participate in membership, grant, or audit history.
- Editing or retiring a Tenant Group in KAORI never edits or deletes the authoritative external IdP/Identity Group.

The Tenant Group slug is a stable KAORI identity key and is not regenerated when the display name is corrected.

## Built-in Access Profiles

Viewer, Operator, Tenant Admin, and Deployer are code-owned versioned security contracts.

### Viewer

Read-only operational visibility for workload, service, quota/limit, ingress, autoscaling, event, and selected namespace-support resources. It excludes Secret access and all RBAC mutation.

### Operator

Viewer plus bounded workload deployment and troubleshooting operations, including logs, exec, and port-forward. It cannot mutate Tenant RBAC, Namespace, ResourceQuota, LimitRange, ServiceAccount, or cluster-scoped resources.

### Tenant Admin

Operator plus Secret lifecycle required for full application administration. Platform-security controls remain KAORI/platform-admin owned. Tenant Admin cannot mutate Role, RoleBinding, ResourceQuota, LimitRange, Namespace, ServiceAccount, or cluster-scoped resources.

### Deployer

CI/CD-focused workload mutation for Deployments/StatefulSets/DaemonSets/ReplicaSets, Jobs/CronJobs, Services, ConfigMaps, PVCs, Secrets, Ingress, and HPA. It excludes interactive exec/port-forward/log troubleshooting, RBAC administration, Namespace administration, and cluster-scoped resources.

Any later Custom Access Profile requires a separate governed design. Built-in profile permissions are not editable inline.

## Scope semantics

A grant has exactly one scope type.

Assume this Tenant layout:

```text
Payment Platform
├── Development
│   ├── payment-api-dev
│   └── payment-worker-dev
├── Staging
│   └── payment-api-staging
└── Production
    ├── payment-api-prod
    └── payment-worker-prod
```

### Namespace Scope

Namespace Scope targets exactly one managed/adopted Tenant Namespace.

Example:

```text
platform-developers
  -> Operator
  -> Namespace: payment-api-dev
```

Effective target:

```text
payment-api-dev          YES
payment-worker-dev       NO
payment-api-staging      NO
payment-api-prod         NO
payment-worker-prod      NO
```

The grant must contain one Namespace target and no Environment target. The current invariant error `Namespace-scoped Access Grant requires exactly one managed namespace` means that the operator selected Namespace Scope without exactly one valid Tenant Namespace target, or supplied a conflicting Environment target.

### Environment Scope

Environment Scope targets the managed/adopted namespaces under one Tenant Environment.

Example:

```text
platform-developers
  -> Operator
  -> Environment: Development
```

Effective scope:

```text
payment-api-dev          YES
payment-worker-dev       YES
payment-api-staging      NO
payment-api-prod         NO
payment-worker-prod      NO
```

The grant must contain one Environment target and no Namespace target. Environment is a KAORI governance grouping; it does not create a Kubernetes cluster-scoped authorization object. Native reconciliation materializes namespaced Role/RoleBinding state for the applicable target namespaces.

### Tenant Scope

Tenant Scope targets managed/adopted namespaces across all environments in one Tenant.

Example:

```text
platform-auditors
  -> Viewer
  -> Tenant: Payment Platform
```

Effective scope:

```text
Development namespaces  YES
Staging namespaces      YES
Production namespaces   YES
Other Tenants           NO
Cluster-wide resources  NO
```

Tenant Scope is not Kubernetes cluster scope. It must never be represented as ClusterRoleBinding or accidental cluster-wide privilege.

Cross-Tenant scope references fail closed.

### Scope target matrix

| Scope | Environment target | Namespace target | Meaning |
|---|---|---|---|
| Tenant | none | none | Managed/adopted namespaces across the selected Tenant |
| Environment | exactly one | none | Managed/adopted namespaces in one selected Tenant Environment |
| Namespace | none | exactly one | One managed/adopted Tenant Namespace |

## Native Kubernetes translation

Each profile version maps to one deterministic namespaced Role name. Each grant maps to one deterministic RoleBinding per target namespace.

For a User Principal, the RoleBinding subject is a Kubernetes `User` subject. For a Tenant Group, the RoleBinding subject is a Kubernetes `Group` subject whose name comes from the registered group subject.

KAORI never creates ClusterRoleBinding from this managed path. Wildcard API groups, wildcard verbs, and known platform/cluster-scoped resources are rejected by the Access Profile contract.

Provider resources declare `app.kubernetes.io/managed-by=kaori`. Existing resources owned by another controller are never silently overwritten.

## Capsule provider translation (#966)

For an adopted or managed Capsule Tenant, Capsule remains the exclusive reconciliation authority.
The provider-aware Access Grant dispatcher uses the same versioned KAORI Membership, Profile, and scope contracts.
It never patches Native Kubernetes Role/RoleBinding objects while Capsule owns the Tenant.

Capsule `v1beta2` supports `Tenant.spec.additionalRoleBindings` for automatic
Tenant-wide distribution, and `Tenant.spec.rules[].permissions.bindings` with
`namespaceSelector` for targeted distribution. **KAORI deliberately uses the
selector-scoped contract for all three scopes (Tenant, Environment, Namespace)**:
the implicit future-Namespace expansion of `additionalRoleBindings` would
grant access to Namespaces not yet admitted into committed KAORI Tenant state.
The exact-name selector is updated only by explicit provider reconciliation
after additional Namespace governance is committed. These fields point to **ClusterRoles**,
not KAORI's namespaced Roles. The adapter therefore requires a **pre-approved ClusterRole**
named `kaori-tenant-<profile>-v<version>` with exactly the same resource/verb/API-group
triples as the matching code-owned Access Profile. Aggregated ClusterRoles, extra permissions,
missing ClusterRoles, mismatched subjects, or foreign ownership are rejected. KAORI does not
create the ClusterRole or a ClusterRoleBinding.

Each Capsule distribution entry is correlated by `app.kubernetes.io/managed-by=kaori` and
`kaori.io/access-grant=<grant.public_id>` labels. The adapter patches only its owned
entries, using the Capsule Tenant `resourceVersion` precondition and a server-side dry run.
Capsule owners, other bindings, and unrelated Tenant rules are preserved. A concurrent or
colliding ClusterRole mapping fails closed rather than merging identities unpredictably.

For narrower scope, the provider rule uses the Kubernetes immutable
`kubernetes.io/metadata.name` Namespace label with an exact `In` list of governed names.
Before mutation, KAORI proves each target is Ready, is present in
`Capsule Tenant.status.namespaces`, and carries the authoritative
`capsule.clastix.io/tenant` label. A Tenant-wide grant is rejected if the Capsule Tenant
contains additional Namespace names not yet governed by KAORI, preventing inadvertent
privilege expansion. ServiceAccount grants are limited to Namespace scope.

The Capsule CRD discovery checks the served `v1beta2` OpenAPI schema separately for
Tenant-wide and selector-scoped grant capability. Healthy committed admission evidence and
healthy Capsule authority are prerequisites; UI enablement is advisory, with live backend
preflight as the enforcement boundary. No automatic Native fallback occurs.

Successful Capsule Tenant PATCH is **not** proof of effective access. Effective managed
RoleBindings are read from each Namespace and compared with expected ClusterRole, subject,
scope, and ownership. The result remains Drifted until the controller converges, and
failed cleanup never claims that access was revoked. Drift/inspect/reconcile use the same
committed grant lineage and store non-secret provider UID, resourceVersion, target, and
effective-evidence hashes.

### Native versus Capsule Namespace authority during adoption (#983)

Native Namespace Discovery and Adoption Preflight must refuse a Namespace that
still declares Capsule ownership through either canonical Capsule Tenant
labels (`capsule.clastix.io/tenant`, `projectcapsule.dev/tenant`) or a Capsule
Tenant ownerReference. Submit rechecks both forms of provider identity, and
the Native allocation cutover must not patch such a Namespace, even where
KAORI has no existing Tenant record. Capsule is authoritative for those
resources; the operator must use governed Capsule attachment and its exact
UID/resourceVersion/owner proof rather than silently switching adapters.

### Provider-preserving Release Governance preflight (#990)

**Review Release** in Tenant Registry is an explicit, **read-only preflight** for
externally Adopted Native/Capsule Tenants. It is not Decommission and never
performs a Kubernetes/Capsule delete, revocation, allocation write or
ownership-state transition. The action checks:

- Active KAORI Credentials, Access Grants, Memberships, managed resources,
  advanced capabilities, reservation/exposure policy.
- Namespace adoption/ownership and whether allocation remains under
  KAORI-managed Resource Profile control.
- Live provider Namespace or Capsule Tenant UID/resourceVersion, plus current
  Capsule RBAC/owner observation provenance and freshness.

It commits blocked/handoff-review evidence as an `AuditEvent`, and Tenant
Registry reads only the latest committed observation on normal requests.
A preflight result alone remains **handoff review required** with
`release_execution_available=false`: it is evidence, not a Release operation.

### Guarded Released lifecycle and Re-adopt generation (#991)

`Released` is a **separate terminal governance state** for Tenant and Namespace
histories; it never means that Kubernetes resources were deleted. An explicit,
operator-approved Release action re-reads provider identity and dependencies,
compares UID/resourceVersion to the last eligible preflight (maximum 15 minutes
old), and commits Released audit and terminal records only when evidence
remains identical. Namespace and Capsule Tenant resources are preserved.

**Fail-closed boundary:** previous adoption with KAORI-owned provider mutation,
an attached Resource Profile or any outstanding grant, credential, Group or
managed policy cannot use the observation-only Release path. Those resources
require separately admitted external owner handoff and provider read-back.
That expanded lifecycle remains open under #991; no database-only unmanage
is permitted.

Released histories remain auditable but no longer appear as active Tenant or
Namespace ownership. Re-adoption creates a new generation and correlates to
the prior Released generation only when the live immutable provider UID still
matches; name reuse after provider recreation fails closed. Decommission
remains a separate destructive lifecycle. Downgrade is refused while Released
records exist. Native/Capsule live UAT and provider ownership handoff gates
remain pending before formal admission.

### Release Handoff Inventory and provider ownership proof (#991)

**Review Release** now gathers a *bounded, read-only* handoff inventory in its
existing committed Release preflight event. For Native Kubernetes, the
normalizer inspects the live Namespace and its ResourceQuota/LimitRange
declarations through the canonical allocation observer, recording only kind,
name, UID, resourceVersion, KAORI/external ownership-marker correlation and
the effective allocation hash. The Capsule path observes Tenant CR identity, correlated Namespace
UID/resourceVersion and exact Tenant label/status correlation, along with
Capsule quota presence and ownership provenance; Capsule remains the sole
source authority for its Tenant resource. No unreviewed provider mutation
is attempted.

The existing Tenant Registry shows these handoff components under a
progressive **Handoff inventory** disclosure. An operator can see exactly
which components still need external-owner acknowledgement, which provider
markers conflict, and which objects are merely observed. A correlated
`app.kubernetes.io/managed-by=kaori` marker is *not* proof that an external
owner has accepted the resource; it is an explicit handoff blocker, not a
license to strip labels or delete provider resources.

Before executing the limited Release path, KAORI recomputes the live
provider handoff inventory and compares its deterministic SHA-256 fingerprint
with the previously committed approved preflight. A changed Namespace,
ResourceQuota, LimitRange or Capsule resourceVersion (or identity) blocks
release. Existing KAORI-managed allocation and all unresolved credentials,
Access Grants, Groups and provider-owned controls remain **Blocked**.
A future separately admitted executor must transfer ownership only after
explicit successor approval, provider read-back and audit; this inventory
deliberately does not assert that those conditions are already met.

### Dual-operator Release handoff plan and approval checkpoint (#991)

The Registry's **Governed Handoff** disclosure now captures the proposed
**successor owner reference** and **change record reference** against the last
live Review Release preflight. **Prepare Handoff** refreshes provider
identity/ownership evidence, then commits a non-secret immutable plan fingerprint
record to `AuditEvent`. A different authorized KAORI operator may
**Acknowledge Handoff**, which performs a second provider/authority preflight
and requires an unchanged cluster, generation, provider, component fingerprint
and Namespace identity. Requests expire after 15 minutes. Existing Access
Grants, credentials, Memberships, Groups, policies or provider/ownership
conflicts block acknowledgement until independently resolved.

The roles of the two operations are deliberately distinct:

- **Prepare Handoff** records *requested successor and intended change*;
  it does **not** validate that a real external owner has accepted ownership.
- **Acknowledge Handoff** records an independent KAORI operator's review;
  it is **not** an external-owner acceptance receipt, effective RBAC proof,
  provider ownership transfer or authorization to Release.
- **Provider Handoff Execution** must still be admitted in a later controlled
  workstream. It will require evidence of the successor's acceptance, current
  provider UID/resourceVersion, exact desired mutation, conditional patch,
  preserved ResourceQuota/LimitRange/Capsule values and provider read-back.
  A partially transferred resource must remain blocked and auditable.

Both current operations are **read-only on Kubernetes/Capsule** and may create
only committed KAORI audit events; the existing Release preflight and executor
stay fail-closed for previously KAORI-mutated controls. No manually entered
change reference, approval checkbox or internal plan is sufficient to set
`lifecycle_status=released`. The operational UI reads committed plan/approval
status rather than running provider reads on each page load.

### Governed Access Remediation Decisions (#985)

An operator may prepare a **Remediation Decision** after fresh committed
Capsule access observation and Access Drift Analysis. This produces a
non-mutating, auditable plan from known KAORI grant status and exact
Capsule source declaration evidence. Plans with stale evidence or grant
changes newer than the source evaluation fail closed.

Only an **active, KAORI-owned grant** that is already Drifted/Failed under a
healthy Capsule authority may be recommended for existing
**Access Grant Inspect → Reconcile**. No separate provider executor is
introduced: those established actions already perform provider preflight,
authorization and read-back. Provider-owned external entries, unknown
identity groups, orphan markers, revoked grants and privilege conflicts
require human review and cannot enter automatic remediation.

Plans do **not** automatically execute mutations or claim that provider
declarations prove effective RBAC. Future risk-based automation must use
the approved Intelligence (#123) and policy/approval authority rather than
creating a second autonomous agent or silently rewriting security policy.

### Committed Capsule access declaration drift (#984)

The **Analyze Access Drift** action uses the latest explicitly captured Capsule
External Access Inventory and compares its *declared* KAORI grant ownership
markers with committed Access Grants. It reports external owners, ungoverned
external bindings, orphaned markers, revoked grants still declared in the
Capsule Tenant CR, and active grants missing a declaration. The analysis
requires recent observation evidence, fails if grant state changed since
collection, and stores a bounded non-secret `AuditEvent` for normal UI reads.

A declaration is **not proof of effective namespaced RBAC**. Findings are
review/reconciliation leads; they do not auto-revoke, rewrite Capsule specs,
elevate access, or automatically create Groups/Memberships. Actual effective
RoleBinding inspection and provider-authoritative reconciliation remains the
existing Access Grant Inspect/Reconcile/Revoke contract. Governance Intelligence
(#123) will later consume these committed signals via its existing rule and
case lifecycle, not an independent duplicate finding registry.

### External Capsule Access observation (#981)

A governed, healthy Capsule Tenant may have pre-existing `spec.owners`,
`spec.additionalRoleBindings`, and selector-scoped
`spec.rules[].permissions.bindings` provisioned outside KAORI.
In **Tenant → Access Grants → External Capsule Access Inventory**, an authorized
operator may explicitly **Inspect External Access**. This calls the authoritative
Capsule Tenant CR only on demand, checks provider UID/resourceVersion and served
v1beta2 API, and commits a bounded, non-secret AuditEvent inventory. Routine
workspace views render only the latest five committed observations.

External principals and policies retain **Observed / Review Required**
provenance. Existing KAORI grant labels are correlated only when both
managed-by and grant public_id markers exist. No owner becomes a KAORI Tenant
Admin automatically, no external Group membership is imported from an IdP,
and no external Capsule binding is rewritten or removed as an observation
side effect. Effective grant takeover requires separately approved identity,
exact permission/profile, source-scope, and ownership equivalence proof. A
name match or provider ClusterRole name alone is insufficient.

### Attach provider-correlated Capsule Namespace to existing Tenant (#983)

The existing **Tenant Discovery → Review Adoption** surface now lists
Capsule **Namespace** candidates when an authoritative Capsule Tenant CR
is already governed by KAORI but the Namespace is not. Unlike full
Capsule Tenant adoption, this action reuses the existing Tenant and
selected Environment. No new Tenant, provider Tenant CR, Capsule RBAC,
or Namespace owner label is created.

Both live Discovery Preflight and Adoption submit reuse the same
Capsule provider correlation contract. The Namespace must have a
nonconflicting `projectcapsule.dev/tenant` or
`capsule.clastix.io/tenant` label (or Capsule Tenant owner reference)
explicitly naming the target Tenant. Membership in
`Tenant.status.namespaces` **alone is insufficient**. Tenant CR UID
must match its existing committed KAORI authority; Namespace immutable
UID and resourceVersion must match the reviewed preflight, there must
be no active owner or released-history lineage conflict, and allocation
authority must not be ambiguous/unsupported.

On successful attachment, existing Namespace quota and Container/PVC
limits are **mirrored from Capsule** as the adopted baseline using the
canonical Capsule Namespace policy-profile helper. KAORI does not
modify provider CR, Kubernetes Namespace, ResourceQuota, LimitRange,
RBAC, or implicitly broaden Tenant-level Access Grants. The original
Tenant provider provenance remains unchanged; only the new Namespace
governance generation and nonsecret attachment audit evidence are
committed. If provider identity/capacity cannot be proved, attachment
fails closed and leaves the existing Tenant untouched.

This does not replace the full Capsule Tenant discovery/adoption lane,
native Namespace attachment, or Release/Re-adopt authority. Exercise
real Capsule correlation, mixed Namespace quotas and provider churn in
nonproduction before staging promotion.

### Native Kubernetes Namespace RBAC inventory (#996)

Native Tenant access governance now has a matching **explicit read-only inspection**
path in **Tenant → Access Grants → Native Namespace RBAC Inventory**, alongside
the existing Capsule observer (#981). The operator selects a healthy governed
Native Tenant and clicks **Inspect Native RBAC**; the canonical connection
reads only its currently Ready and governed Namespace objects plus their
namespaced RoleBindings. No cluster-wide RoleBinding enumeration or Role/RoleBinding
mutation is performed.

The observer verifies committed Namespace/cluster correlation, live Namespace
UID/resourceVersion, bounds the Namespace and RoleBinding inventory, and
records the exact role reference, subject identifiers and binding UID/version
as non-secret AuditEvent evidence. KAORI labels are **only correlation hints**;
a grant public ID must also exist in the same canonical Tenant for the
`kaori_correlated` classification. Marked-but-unmatched or foreign bindings
remain `kaori_marker_unverified` or `external_observed`, not managed.
Even correlated bindings do **not** prove the referenced Role/ClusterRole
permissions or that access is effective. Do not import Users/Groups,
create Memberships, revoke external roles, or infer IdP identities.

Normal UI displays up to five *committed* observations without live provider
requests. Use **Inspect/Reconcile** on an existing KAORI Access Grant only
for its own admitted reconciliation authority; never use a foreign binding
as a managed grant without the future human-reviewed import contract.
Read-only observation requires `tenant.manage` and CSRF. Provider read
failure, UID replacement or unbounded evidence fails closed, without
claiming an inventory is complete.

### Capsule Namespace attach to existing governed Tenant (#983)

**Discovery** and **Tenant Registry** share one authoritative
`attach_discovered_capsule_namespace_committed` service, not two Kubernetes
mutation paths. Registry derives the connected cluster and Capsule Tenant
from the committed destination Environment; both entry points require
the exact Namespace UID and resourceVersion observed during Discovery.

Before KAORI commits a new Adopted Namespace generation, the service
rereads the Capsule Tenant CR and selected Namespace, validates immutable
Tenant/Namespace UID and resourceVersion, Capsule Tenant labels,
ownerReference name **and UID**, active ownership and Released lineage,
and then rereads both provider resources to detect concurrent replacement.
Missing ownerReference generation UID is treated as ambiguous ownership.
Unsupported/mixed Namespace allocation and cross-Tenant reparenting
fail closed. Existing provider-mirrored Namespace policy normalization
and canonical audit/evidence are reused.

No Namespace, Capsule Tenant, quota, RoleBinding or external group is
mutated by attachment; no KAORI grant is automatically imported or expanded.
Normal Registry rendering reads committed state; only explicit attach POST
performs fresh provider reads. Both UI entry points remain Draft pending
Developer Check, Full Admission, Visual QA and live Capsule UAT.
### Native Access Drift declaration correlation (#999)

After **Inspect Native RBAC** has committed a scoped, bounded namespaced
RoleBinding inventory (#996), **Analyze Native Access Drift** compares that
observation with KAORI's committed Access Grant declarations. It requires
evidence less than one hour old and fails if any Access Grant changed after
observation, rather than evaluating stale or contradictory state.

Current findings distinguish foreign provider RoleBindings, unverified KAORI
ownership markers, revoked grants still declared, missing active grant
declarations, and the observed Namespace or RoleRef differing from a
correlated KAORI grant's canonical scope/role. These are **declaration-level
findings**, not independently verified effective permissions or proof that a
foreign principal has/has not access. The existing Access Grant Inspect and
Reconcile actions remain the only governed provider reconciliation path.
Analysis only writes an AuditEvent with nonsecret evidence and does not
perform Native or Capsule RBAC mutation.

The resulting committed finding history is available in the existing Tenant
Access Grants workspace. Longer-term alignment with the Intelligence Rule
Catalog / Case lifecycle, human review of external IdP identities and
cross-provider runtime audit evidence remains under #999 and #122; do not
silently create a duplicate Tenant-only enforcement or alert engine.

### Existing-Tenant Namespace attachment (#983)

In **Tenant → Discovery → Review Adoption**, a newly discovered Native
Kubernetes Namespace may be attached to a *Ready Native Tenant* in the same
cluster, selecting an existing Environment. This preserves the Tenant's
existing identity and generation and uses the same adopted provider UID,
ResourceQuota/LimitRange observation, capacity admission and equivalent
allocation write/read-back as standalone Native adoption.

The backend revalidates cluster, provider authority, Namespace ownership,
Kubernetes manager label, live Namespace UID, and availability before committing
the additional Namespace record. Stale/replaced, system, terminating, already
governed or cross-cluster Namespace candidates fail closed. Capsule namespaces
cannot be reassigned to an arbitrary Tenant: Capsule remains authoritative for
Tenant/Namespace ownership.

**Access safety:** Attaching a Namespace never implicitly extends existing
Tenant/Environment Access Grants. The operator must inspect and explicitly
reconcile the newly admitted scope after successful attachment. Existing Tenant
provider provenance is preserved; the new Namespace records its own attachment
lineage and effective allocation verification.

### Kubernetes Integration · Capsule Cluster RBAC Bootstrap (#974)

ClusterRole prerequisites belong to the **Kubernetes cluster**, not to a specific
newly created or adopted Tenant. Before the first Capsule Access Grant, open
**Integrations → Kubernetes → [Cluster] → Validation & Capabilities →
Capsule Cluster RBAC Bootstrap** and run **Check RBAC**.

- Check RBAC performs a read-only, explicit live comparison of Viewer, Operator,
  Tenant Admin and Deployer ClusterRoles against `ACCESS_PROFILE_CATALOG`.
  The latest role name, version, expected permission hash, UID/resourceVersion,
  Ready/Missing/Conflict state and execution actor are committed as non-secret
  `AuditEvent` evidence. Normal page visits read this evidence without calling
  Kubernetes.
- **Bootstrap Missing Roles** is enabled only after a recent explicit Check
  reports Missing and no Conflicts. It requires `clusters.manage` and
  `integrations.manage`, a valid CSRF token and explicit acknowledgement of
  a cluster-scoped mutation. The backend repeats live preflight, checks Capsule
  v1beta2 discovery, dry-runs every missing role, creates only missing roles and
  reads back exact permissions, UID and resourceVersion.
- Existing exact ClusterRoles are **reused untouched**, regardless of which
  external administrator first created them. Existing mismatched, aggregated,
  or differently owned RBAC is never patched or replaced. Concurrent conflicts,
  insufficient Kubernetes `create`/RBAC escalation authority, partial mutations
  and read-back gaps fail closed with committed audit status.
- Kubernetes RBAC may reject creation if the KAORI connection identity lacks
  permission to create ClusterRoles with the specified resource verbs; grant
  only narrowly approved cluster provisioning access under cluster-admin
  governance. Capsule controller `bind` authority is a **separate** requirement.
- Re-run Check after bootstrap before reconciling any previously failed Capsule
  Access Grant. Second Check detects existing exact roles and Bootstrap becomes
  disabled; do not provision per Tenant.

**Tenant discovery/adoption never triggers bootstrap automatically.**
No ClusterRoleBinding or implicit Tenant grant is created. Manual YAML
Copy/Download from Grant Context → Prepare Roles remains a fallback for clusters
where KAORI is not authorized to perform this approved cluster mutation.

### Operator preparation and Capsule UAT

1. Confirm the adopted Capsule Tenant is healthy and its Namespace inventory is committed,
   including the target Namespace and Capsule ownership label.
2. Ask the cluster administrator to review the four immutable permission matrices in
   `app/kubernetes/tenant/access.py` and separately provision the approved
   `ClusterRole/kaori-tenant-viewer-v1`,
   `ClusterRole/kaori-tenant-operator-v1`,
   `ClusterRole/kaori-tenant-tenant-admin-v1`, and
   `ClusterRole/kaori-tenant-deployer-v1` as needed. **Do not** reuse Kubernetes's
   broader built-in `admin`, `edit`, or `view` roles by name.
KAORI provides a read-only manifest preparation dialog in
**Tenant Management → Access Grants → Grant Context → Prepare Roles**.
The dialog offers Copy/Download for each of the four approved versioned
ClusterRoles and for a complete multi-document YAML bundle, derived from the same
`ACCESS_PROFILE_CATALOG` used by the provider reconciliation adapter. Its
generation does **not** query Kubernetes, apply RBAC, or authorize Capsule to
bind roles. A cluster administrator must review and apply the YAML to the
approved Kubernetes context, then explicitly Reconcile and Inspect the Access
Grant.

To generate the same reviewable ClusterRole manifest from the canonical KAORI permission
catalog (without changing Kubernetes), run this inside the KAORI devcontainer:

```bash
python - <<'PY' > /tmp/kaori-capsule-access-clusterroles.json
import json
from app.kubernetes.tenant.access import ACCESS_PROFILE_CATALOG

roles = []
for (key, version), profile in sorted(ACCESS_PROFILE_CATALOG.items()):
    roles.append({
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRole",
        "metadata": {"name": f"kaori-tenant-{key.replace('_', '-')}-v{version}"},
        "rules": [
            {"apiGroups": list(rule.api_groups),
             "resources": list(rule.resources),
             "verbs": list(rule.verbs)}
            for rule in profile.rules
        ],
    })
print(json.dumps({"apiVersion": "v1", "kind": "List", "items": roles}, indent=2))
PY

# Review the output and cluster context; do not apply without cluster-admin approval.
kubectl diff -f /tmp/kaori-capsule-access-clusterroles.json
# Explicitly approved UAT cluster only:
# kubectl apply -f /tmp/kaori-capsule-access-clusterroles.json
```

3. If Capsule strict RBAC is enabled, explicitly authorize its controller to `bind`
   each approved ClusterRole using the Capsule installation/configuration authority.
   No KAORI path silently elevates Capsule controller permissions.
4. In KAORI **Access Grants**, select a Membership, the corresponding approved profile,
   Scope (Namespace is recommended for first UAT), and the target Namespace. Use Apply.
   Observe Drifted/Ready, then Inspect or Reconcile after provider convergence.
5. Verify with impersonated `kubectl auth can-i` operations that approved verbs succeed,
   forbidden verbs and cross-Tenant resources fail, and Revoke removes effective access.
   Capture the Capsule Tenant UID/resourceVersion and managed RoleBinding evidence.
6. Repeat with degraded or unsupported Capsule capability: Apply remains fail-closed.
   Do not accept this workstream as UAT PASS without live Capsule grant/revoke evidence
   and human acceptance.

The `ClusterRole` and Capsule controller `bind` preparation are cluster-admin changes
outside KAORI's automatically executed reconciliation. A missing prerequisite produces a
specific operator error; it is not silently installed.

## Revocation and re-authorization

Access Grant revocation and Tenant Membership revocation are different operations.

### Revoke Access Grant

Revoke Access Grant:

- keeps the User Principal or Tenant Group registered as an active Tenant Membership;
- changes that Access Grant's desired state to revoked;
- removes the effective managed RoleBinding from every current or previously reconciled target namespace;
- preserves the revoked grant and reconciliation evidence for audit history;
- may leave a managed Role object in place because other grants can reference the same profile Role.

A later decision to give the same active Membership access again is a new authorization decision. The current implementation creates a new Access Grant lineage instead of silently changing the old revoked grant back to active. This preserves the historical revoke event.

Example:

```text
Before
platform-developers -> Operator -> Development -> ACTIVE

Revoke Access Grant
platform-developers -> Operator -> Development -> REVOKED
RoleBinding access removed
Tenant Membership remains ACTIVE

Later approved again
platform-developers -> Operator -> Development -> NEW ACTIVE GRANT
old revoked grant remains audit evidence
```

### Revoke Tenant Membership

Revoke Tenant Membership:

- changes the Tenant Membership to revoked;
- revokes every dependent active Access Grant;
- removes their effective managed RoleBindings;
- preserves historical Membership and Access Grant evidence.

This is the stronger action because the principal is no longer an active member of the Tenant.

A revoked User Principal or Tenant Group may be explicitly **Reactivated** using the same Membership record after provider cleanup for every previous Access Grant is proven complete. Reactivation preserves the Membership correlation/audit lineage and changes only the Membership back to active. Previous Access Grants remain revoked permanently; restoring authorization requires a **new Access Grant**. KAORI must not silently reactivate old grants or create a duplicate Membership for the same principal.

Reactivation fails closed when the linked KAORI user is inactive, the linked Tenant Group is disabled, the Tenant is not Ready, or any prior grant has not reached provider-verified `Revoked` reconciliation state.

## Reconciliation and drift

Committed desired/effective hashes, target evidence, reconciliation state, last reconciliation timestamp, and error message remain separately observable.

States:

- Pending — committed grant has no managed namespace target yet;
- Ready — desired and effective Role/RoleBinding contracts match;
- Drifted — effective Kubernetes RBAC differs from committed intent;
- Failed — reconciliation could not safely complete;
- Revoked — no effective managed RoleBinding remains.

A failed revoke remains visibly revoked in KAORI intent while effective provider removal is marked failed/drifted; it must never be reported as successfully removed.

## Operator contextual guidance

Tenant Management must explain identity, scope, and destructive actions at the point of use. Reuse existing KAORI tooltip/help-text/error patterns; do not create a Tenant-only help system.

At minimum:

- identify whether a Membership is a User Principal or Tenant Group;
- explain that a Tenant Group references a Kubernetes Group subject and that external group membership remains owned by the configured Kubernetes authentication/IdP authority;
- show concise scope examples next to the Scope selector;
- when Scope is Tenant, hide or disable Environment and Namespace target controls;
- when Scope is Environment, require only an Environment target;
- when Scope is Namespace, require only a Namespace target;
- filter Environment/Namespace target choices to the Tenant of the selected Membership;
- allow Environment/Tenant scope intent to remain `Pending` when no governed namespace exists yet;
- after an explicit Native Namespace provisioning operation reaches committed Ready state, automatically reconcile active Environment/Tenant grants whose committed scope now includes that namespace;
- never infer Namespace scope automatically, and never perform this RBAC mutation from inventory/Tenant sync; sync remains observation-only;
- explain Revoke Access Grant versus Revoke Tenant Membership before destructive confirmation;
- for a revoked User/Tenant Group Membership, expose Reactivate and explain that prior grants remain revoked and a new grant is required;
- translate internal scope invariants into actionable operator messages, for example: `Choose one managed Namespace for Namespace Scope`;
- where integration evidence exists, distinguish a verified external group subject from an unverified/free-form subject.

Contextual guidance is explanatory only. Server-side validation and fail-closed provider reconciliation remain authoritative.

## Activity and downstream credentials

Create/reconcile/revoke mutations record non-secret AuditEvent evidence with the grant correlation identifier. Kubernetes audit correlation remains owned by #122.

#115 and #116 may bind governed credential principals to the Access Grant contract, but they must reuse the same profile/scope semantics rather than redefining permissions.


## Production access governance

Production is pipeline-first. A namespace whose canonical Tenant Environment is `production` uses the same #114 namespaced RBAC contracts, but KAORI adds a production mutation policy above those permissions.

- A valid namespace-scoped #116 Deployer ServiceAccount is the policy-compliant mutation authority.
- Ordinary human credentials may retain governed read visibility where their Access Grant permits it, but mutation is denied by default.
- A direct administrator mutation is technically allowed and attributable, but it is recorded as `production_direct_access` and `production_human_mutation` rather than being treated as normal pipeline delivery.
- An ordinary human production mutation requires a separately committed, namespace-bounded exception with owner, approving administrator, reason, review/expiry time, and lifecycle state.
- Production exceptions never create new RBAC. They only allow the production policy preflight to accept an already-authorized human grant for the bounded namespace/time window.
- Exception validity is short-lived: eight hours by default and no more than seven days.
- Unsupported or malformed production mutation identities fail closed.

The production policy records non-secret decision evidence for downstream Activity, audit correlation (#122), and Tenant Governance Intelligence (#123). Kubernetes remains authoritative for effective authentication/RBAC; this policy does not replace Kubernetes audit evidence for operations performed outside KAORI-managed flows.
