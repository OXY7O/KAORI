# KAORI internal configuration and secret bootstrap model (#5206)

Status: design proposal under accepted #5200/#5202; no ENV migration or
configuration-source change in this delivery. Existing split environment
files, runtime target identity and deployment/recovery contracts remain
authoritative. See [server profile](../../deploy/server/secret-store/README.md).

See the [names-only configuration inventory](internal-secret-configuration-inventory.md)
for the split examples, current delivery boundary and candidate ownership review.

## Ownership and dependency order

OpenBao v2.7.3 is the bundled default secret provider, with the existing
PostgreSQL service and a separate database/role. Runtime topology and
immutable image identity remain deployment-owned. An external OpenBao or
Vault instance is optional and must never be an implicit fallback for
platform secrets. Reuse the provider-neutral SecretIdentity, version and
scope lifecycle; KAORI does not implement a competing secret engine.

| Configuration class | Existing examples (names only) | Proposed final authority |
| --- | --- | --- |
| Independent OpenBao bootstrap | OpenBao storage DSN, TLS/CA, seal and service authentication roots | Target-owned restricted files / operator-held recovery; never depend on the uninitialized service |
| Deployment identity / public configuration | KAORI_IMAGE, KAORI_COMPOSE_PROJECT, POSTGRES_DB, TRUSTED_HOSTS, KAORI_PUBLIC_BASE_URL | Reviewed deployment/app configuration, not automatically secret material |
| Application runtime secret | SECRET_KEY, INTEGRATION_CREDENTIAL_KEY, DATABASE_URL, REDIS_PASSWORD, REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, RATELIMIT_STORAGE_URI | Candidate versioned app-runtime secret scope, with independent emergency recovery; migrate in dependency order only |
| Integration / object storage secret | REPORT_S3_ACCESS_KEY_ID, REPORT_S3_SECRET_ACCESS_KEY, ARCHIVE_S3_ACCESS_KEY_ID, ARCHIVE_S3_SECRET_ACCESS_KEY, KAORI_LDAP_BIND_PASSWORD, KAORI_GOOGLE_CLIENT_SECRET, KAORI_GITHUB_CLIENT_SECRET | Versioned service-/integration-specific scopes, no cross-component wildcard |
| Privileged/bootstrap identity | ADMIN_PASSWORD, PostgreSQL admin/migrator credentials, OpenBao root token, unseal shares | Separate controlled bootstrap/recovery; never grant routine web/worker access or place the only copy inside OpenBao |
| Operational configuration | Worker concurrency, retention, schedules, feature flags | Canonical typed application config; candidate versioned settings after separate review; preserve reproducible deployment values |

These are representative variables from the example files, not a complete
inventory or migration instruction. Never dump actual environment values
into an issue, CLI report, evidence or audit. An existing encrypted
integration credential is not safe to migrate merely because its value is
encrypted: preserve decryption/key-rotation compatibility and prove recovery.

```text
Target-owned bootstrap envelope + independent recovery custody
    -> PostgreSQL storage / TLS
    -> OpenBao starts, initializes once, unseals, audit and policies ready
    -> scoped service identity acquires short-lived token
    -> authorized exact-version configuration resolution
    -> typed validation and component-specific runtime activation
    -> KAORI readiness, credential management and audit
```

## Proposed logical scope model

Use separate KV v2 mounts or reviewed exact namespaces/prefixes for
application runtime, integration credentials and automation credentials.
Mount names are to be finalized against the existing provider and #724
scope policy. Store per-consumer typed keys/versions, not a universal
environment dump. Separate read, write/rotate, bootstrap, metadata
observation and break-glass capabilities. Do not use one root token,
blanket KV data permission, or generic UI secret reveal. Native provider
administration remains independent. Bootstrap storage DSN and the only
copy of recovery material cannot live exclusively in OpenBao.

## Phased migration (future work)

1. Inventory variable names, owners, consumers, dependencies, secrecy,
   restart/rotation requirements and validation; no values captured.
2. On verified fresh staging, exercise initialization and synthetic secret
   fixtures. Prove restart, sealed/unavailable fail-closed posture,
   independent recovery and paired PostgreSQL backup/restore.
3. Review one bounded runtime consumer, exact configuration schema,
   provider access policy and immutable version/generation. Validate before
   activation; do not silently fall back to a different value on failure.
4. Separate approved cutover per component; keep legacy copy only for the
   explicitly reviewed rollback window, not indefinite dual-write or
   hidden fallback. Audit metadata, version and result only.
5. After accepted operational and recovery evidence, remove legacy copies
   under a separate reviewed change. Non-secret deployment settings may
   stay declarative where that improves portability and startup.

The long-term objective is minimal host-local bootstrap and simple
operator experience, not putting every setting or its only recovery key
inside the secret backend. A protected first-run trigger can orchestrate
steps but cannot carry recovery keys or reset existing state. Native
`bao` recovery must work when Flask is unavailable.

## Acceptance boundary

No real ENV import, value migration, key generation, secret write,
provider initialization or destructive staging operation is authorized
by this model. #5206 remains open until complete inventory, reviewed
scope/consumer contracts, synthetic simulation and recovery evidence are
accepted. Real migration requires separate bounded implementation
authority and Human UAT.

The internal capability is **KAORI Internal Secret Store** (`secret-store`); the selected provider is OpenBao. Preserve stable capability-level deployment and CLI names, but keep provider-specific transport, identity, native configuration and storage format explicit. A change of provider is a governed migration, not an in-place rename or implicit fallback.

## Credential issuer candidate resolution (#5204)

The initial internal read-only resolver selects the latest persisted issuer
revision across the exact integration instance, namespace and mount before
checking provider, deployment, requested revision or lifecycle. A newer
draft/revoked/mismatched revision denies; no older active key fallback.
It uses an independent non-writing database session, checks the canonical
source state, independent approval metadata, validity window, evidence
reference shape and public-key digest. It returns only a candidate public
verification key; neither the stored evidence reference nor a valid key
proves independent custody, actual provider identity, current credential
version, actor/operation grant or execution permission. No activation,
HTTP route, worker wiring, secret material or provider request is added.
Future governed use must revalidate within the operation admission boundary;
this standalone read is not a durable authorization or concurrency lock.


### Independent credential issuer enrollment authority (#5245)

The approved design separates provider-native Transit Ed25519 key custody
from deployment recovery/attestation authority. The latter retains its
private signing key outside KAORI and the provider under enrollment.
The runtime receives only a read-only operator-managed root pin and current
signed receipts through `/run/kaori/issuer-authority`; missing or writable
authority configuration denies. Do not populate the directory from the web
UI, the provider response, general runtime ENV or synthetic CI fixtures.
No default trust pin is supplied. The deployment operator must separately
qualify mount ownership, read-only flags, native provider cluster identity,
exact scoped short-lived inspection ACL, independent approval, atomic
receipt publication/revocation and anti-rollback controls in disposable UAT.
No live mount, key creation, migration, sign or recovery operation is
introduced by the source resolver.

## First local inventory/config migration slice (#5257)

The canonical Ansible source connection and host assets remain the identity
authority. For the disposable one-control-plane/two-worker pilot, the
`automation-inventory-store` command builds a deterministic KV v2 document
containing the approved source and Kubespray versions, exact host identities,
role topology, SSH endpoints (not credentials), and explicitly selected pod
and service networks. The data is protected in an independently approved
local provider mount; this is not a runnable inventory or an authorization.

Before use, select an existing registered OpenBao or Vault connection and
independently establish its native cluster UUID, TLS trust, mount policy and
audit delivery. Configure the local process with APP_ENV=development,
KAORI_LOCAL_INVENTORY_PROVIDER_ID=<canonical IntegrationInstance ID>,
and KAORI_LOCAL_INVENTORY_KV_MOUNT=<approved disposable KV v2 mount>.
These are local UAT scope selectors, not approved production mount names.
Vault additionally requires the mount in its approved KV v2 configuration.
Use a non-root operator token with at most one hour TTL and native access
only to the exact derived data path. The token is prompted without echo.
Do not use root, a general app credential, or a production store.

`flask automation-inventory-store --help` shows the exact command.
The default is read/compare only. Explicit `--publish` creates the
content-addressed `kubespray/connection-<id>/<digest>` entry using CAS 0,
never updates/deletes a previous version, and reads it back as version 1.
The current source and inventory are rechecked before committing a sanitized
Activity Audit and reference in canonical Ansible connection metadata.
The UI shows the last observed receipt, not live currentness. A failed audit
or concurrent inventory change can leave an unreferenced immutable provider
entry; retry only after reviewing current intent and the exact native version.
This is not a distributed atomic transaction. No secret values are printed,
no ENV is migrated, no host access, credential activation or Plan execution.
Worker consumption of exact current provider versions and its approval
boundary remain separately owned by #5204/#4800/#4801.
