# KAORI Internal Secret Store — OpenBao PostgreSQL profile (#5202)

## Authority and state

#5200/#5202, #619, #5093, #4786 and integrated #5172. Maintainer selected
OpenBao v2.7.3 (latest stable as of 2026-11-25 WIB, released 2026-11-19;
[upstream release](https://github.com/openbao/openbao/releases/tag/v2.7.3)).
Use the official [OCI distribution](https://openbao.org/docs/install/) and
retain exact tag-to-digest, license, provenance and vulnerability evidence.
A tag alone is not an admitted image. This candidate overlay is not loaded
by deploy.sh, and no actual image digest, credentials, initialized database
or operational readiness are committed by this increment.

## Profile

Reuse the existing PostgreSQL service, with dedicated proposed database
`kaori_secret_store` and restricted `kaori_secret_store` role, never the KAORI app
database, migrator, runtime or PostgreSQL admin identity. Per-runtime DB
ownership, role isolation, TLS and ACL admission must precede service startup.
OpenBao stores its own encrypted records; the app must not read its tables.
The [2.7 PostgreSQL storage contract](https://openbao.org/docs/configuration/storage/postgresql/)
supports explicitly precreated tables and `BAO_PG_CONNECTION_URL`.
Use the upstream table/index schema under a separate owner/bootstrap identity,
runtime-only DML, `skip_create_table=true` and verified TLS. The existing
PostgreSQL server adapter does not yet provision this database, TLS or ACL;
do not disable SSL or reuse app credentials to make the example start.

`compose.secret-store.yml` is an explicit candidate overlay on the existing
server compose project, not a separate release engine. It requires exact
target-owned image/config/env/audit settings, no host port, no privileged
container or general app env, internal TLS listener and persistent audit
directory. The initial 1 vCPU/512 MiB limit and small DB pool are benchmark
candidates; actual memory, latency, startup and failure behavior must be
measured before admission. Validate official image UID/entrypoint,
capabilities, config/TLS mounts and audit write access on the pinned image.
This is not an HA profile; the shared PostgreSQL service is a common
failure dependency. No new storage engine/container is required.

## First-run flow and CLI ownership

1. Protected staging trigger selects exact reviewed runtime and immutable
   image; read-only target/DB inventory confirms fresh dedicated OpenBao
   state, existing KAORI data is preserved, backup/recovery owner approved.
2. Prepare restricted PostgreSQL database/schema/roles and TLS, host-owned
   mode-0600 service env; start the server and distinguish uninitialized,
   sealed, active and unavailable state. No automatic DB reset.
3. Operator performs one-time native `bao operator init` with independently
   held Shamir shares and secure root-token custody, then unseals. The
   [init](https://openbao.org/docs/commands/operator/init/) contract refuses
   reinitialization; a webhook is only an authenticated workflow trigger,
   never a public init/unseal endpoint or carrier of keys. No key/token in
   workflow logs, arguments, Git, release state or general app environment.
4. Configure declarative audit, reviewed KV v2 mount, least-privilege
   component roles/policies and initial AppRole identities. Verify root
   token retirement and operator recovery. Keep native `bao` CLI accessible
   when Flask or PostgreSQL application schema is unavailable.
5. Reuse canonical `app/commands/` for proposed `flask secret-store-status`,
   `flask bootstrap-secret-store` (post-unseal, bounded/idempotent configuration
   and built-in provider registration) and `flask verify-secret-store`. Normal
   management and credential UI remain in KAORI; actual init/unseal,
   privileged recovery and key custody stay at the provider boundary.
   The initial status command is submitted in #5205; bootstrap/verify
   remain proposed. None is admitted by this overlay.
6. Verify existing-state restart (never reinitialize), sealed/unavailable
   denial, token expiry/revocation, audit and independent recovery before
   integrating into deploy.sh. Backup the dedicated OpenBao database and
   separately protect TLS/config/audit and unseal material; coordinate a
   consistent recovery point with KAORI reference DB. No restore or wipe
   on staging based solely on its name or presumed emptiness.

## Configuration migration

[#5206 configuration bootstrap model](../../../docs/architecture/internal-secret-configuration-bootstrap.md)
owns the future migration. Current app.env, secrets.env,
deploy.env and service-scoped role files remain authoritative. The OpenBao
storage DSN, seal/unseal and service bootstrap roots cannot only reside in
the service that needs them to start. No current ENV value is migrated.

The capability name, deployment service, host-owned file paths and database/role are provider-neutral. `openbao.hcl.example`, `BAO_PG_CONNECTION_URL`, the image and native CLI are explicitly OpenBao-specific implementation details. The deployment-selected `KAORI_INTERNAL_SECRET_STORE_PROVIDER=openbao` and `KAORI_INTERNAL_SECRET_STORE_ENDPOINT=https://secret-store:8200` must be bound to the qualified runtime and its actual provider identity; configure the provider-specific approved origin and CA policy, including a certificate for `secret-store`. Missing or unsupported provider selection fails closed. A future backend replacement requires separate migration, compatibility and recovery admission; never reuse encrypted storage merely because the logical name is unchanged.
