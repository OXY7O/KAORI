# OpenBao — shared Secrets & PKI provider (#5200/#5201)

The accepted direction is one OpenBao provider for both bundled platform-owned
and optional external managed instances. Ownership is not inferred from an
endpoint or name. The local Dev Container implementation is registered in the
Integration Kernel; independent operational authority remains pending.

The read-only `OpenBaoClient` and existing `VaultClient` share
`providers/kv2_http.py`, `kv2_transport.py` and `kv2_metadata.py`. Existing
Vault imports remain compatibility exports. OpenBao uses its own
`INTEGRATION_OPENBAO_ALLOWED_ORIGINS` and `INTEGRATION_OPENBAO_CA_BUNDLE`
settings; never fall back to Vault's allowlist or CA setting. HTTPS, bounded
metadata traversal, no proxies/netrc/redirects, AppRole and transient tokens
follow the existing transport contract. Both internal and external OpenBao
use this exact client, with independently scoped identities. No generic
credential read/write API is exposed by this increment.

OpenBao documents the compatible [AppRole API](https://openbao.org/docs/auth/approle/),
[token header](https://openbao.org/docs/auth/token/) and
[KV v2 engine](https://openbao.org/docs/secrets/kv/kv-v2/). This is an offline
protocol extraction, not proof of full compatibility, actual deployment
identity, supported version, authentication policy or readiness. Qualify
the real pinned release, health semantics, exact provider identity and
negative cases before registration. A successful compatible response alone
must not register OpenBao as HashiCorp Vault or admit a trust anchor.

#5202 owns bundled private deployment, independent bootstrap/unseal,
storage selection, recovery and benchmark; #5203 owns canonical internal
and external registration, readiness and governed credential UI. #5204
converges exact typed credential evidence and worker admission. Sensitive
provider administration remains independent. No deployment or secret
material use is introduced by #5201's initial increment.

## Initial operator CLI (#5202)

`flask secret-store-status` in canonical `app/commands/` uses deployment-owned
`KAORI_INTERNAL_SECRET_STORE_PROVIDER=openbao`,
`KAORI_INTERNAL_SECRET_STORE_ENDPOINT` and the same OpenBao origin/CA policy.
The command is capability-named; unsupported providers are denied rather
than silently falling back. Provider-specific adapters retain their names.
It requires no AppRole credential and prints only sanitized initialization,
seal and health status; it is not admission or a bootstrap writer. It is
available once this PR is admitted. Native CLI remains independent of Flask
for actual init/unseal/recovery. Post-unseal governed bootstrap and verify
commands remain separately gated under #5202.

## Strict pre-bootstrap health verification (#5202)

`flask verify-secret-store` requires the approved private service origin
`https://secret-store:8200`, explicit OpenBao CA configuration and the
existing OpenBao-only allowlist. A successful response must be HTTP 200,
contain exact boolean initialized/unsealed/non-standby flags, and report
the selected version 2.7.3. The exact [OpenBao v2.7.3 server health response](https://github.com/openbao/openbao/blob/v2.7.3/internal/http/sys_health.go)
does not contain `performance_standby` (unlike the compatibility API client
struct). Its absence is valid; if supplied, only boolean false is accepted.
Missing required, malformed or contradictory fields fail closed, without
affecting existing Vault observation behavior.
No authentication token, secret material, provider mutation or registry
write is involved. This is a health gate only, not proof of provider identity,
OCI provenance, storage TLS, policy, audit, AppRole or recovery readiness.
The actual bootstrap writer remains pending review of exact policy and mount
contracts; no automatic initialization, unseal or root credential access.

## Governed bootstrap inspection (#5202)

`flask bootstrap-secret-store --plan` is the first non-mutating bootstrap
increment. It reuses the strict health gate and prompts without echo for a
short-lived, independently issued non-root operator inspection token. Never
provide a root token; the command rejects a root policy or non-expiring token
after lookup-self. No token arguments, general application ENV, persistence
or output. Use independently controlled native provider administration to
issue a narrowly scoped inspection identity with lookup-self and only the
required read authority for sys/audit, sys/mounts and sys/auth (including
endpoint-specific sudo only where required by upstream). Expiry/revocation
remain the operator's responsibility. A successful lookup does not prove
the full effective token policy is least privilege.

The plan observes the configured kaori-operator file audit device and
expected file path without raw logging, then counts KV v2 and AppRole
mounts. It never prints provider response bodies, names, paths, token
metadata or credential material. An observed audit configuration is not
proof of actual audit delivery. Counts do not qualify a particular mount,
AppRole or policy, and zero counts are valid inspection evidence before
bootstrap. Missing audit, malformed responses or denied reads block the plan.
Without --plan the command refuses execution. No provider writes, database
registration, root custody, init/unseal, privilege grant or actual bootstrap
apply. Exact mount and component policy names remain subject to #5206/#5203/
#5204 review; no arbitrary provider paths or new authorization model.

## Provider-qualified credential evidence (#5204)

The shared offline `providers/credential_version_proof.py` defines a new
versioned signed SSH credential claim binding provider key, deployment
reference, exact issuer revision, canonical SecretIdentity UUID and
representation ID, plus existing instance/namespace/mount/path digest,
version and creation time. Legacy Vault schema and canonical signed bytes
remain unchanged; signatures cannot transfer between formats/providers.
A valid signature is not an access grant or proof of current issuer status.
The caller must independently resolve the admitted issuer revision and
public key, current version, scope, operation, worker and audit evidence.
No signing key generation, provider retrieval, runtime activation or
privilege is introduced; exact mount names remain under separate review.

## Local pre-registration qualification (#5203 / #2227)

The same read-only provider transport can inspect an internal deployment or
an explicitly selected external deployment. Run `flask qualify-openbao --help`
in an isolated Dev Container with explicit `APP_ENV=development`. Use the
deployment-owned internal endpoint (omit `--endpoint`) or an approved external
HTTPS origin (`--ownership external --endpoint ...`). Supply the expected
native cluster UUID obtained independently, and the exact operator-approved KV
v2, AppRole and audit mount segments. Do not invent or apply mount names from a
proposal. The internal audit device must be the existing `kaori-operator` file
audit configuration. Both ownership modes use the same implementation and the
selected OpenBao v2.7.3 release; other versions are not qualified by this slice.

A transient inspection token is prompted without echo. It must be non-root,
expiring within one hour, and independently issued with only the read authority
required by lookup-self, sys/mounts, sys/auth and sys/audit. Never pass the token
as an argument or environment variable. Exact mount and audit metadata are
checked against the approved names. The cluster UUID and active version are
rechecked after inspection. The emitted digest identifies a sanitized observation;
it is not a signed deployment receipt, authorization, or persisted admission
evidence. It does not prove complete ACL containment, AppRole login, audit delivery,
provider provenance, or worker credential compatibility.

The provider selector permits local registration after this implementation;
registration is distinct from operational qualification.
No runtime registration, database write, provider modification, secret retrieval,
ENV migration or credential activation is performed. Qualify the disposable
deployment, preserve the evidence in the issue, and obtain the separate
independent approval before changing the provider lifecycle or bootstrap policy.

## Local provider integration (#5203)

OpenBao has a separate provider record and migration, canonical IntegrationInstance
identity, distinct openbao_http_v1 adapter, explicit internal/external ownership,
unique cluster and endpoint, and encrypted AppRole SecretID. Vault records are
unchanged. Local activation requires explicit APP_ENV=development in both the
process and Flask config. The provider matrix makes the implementation available;
outside this local context registration and adapter execution are denied.

External: Integrations → Secrets Management → Secrets & PKI → Choose Provider →
OpenBao. Enter the independently verified cluster UUID and approved HTTPS origin,
AppRole mount, RoleID and SecretID. Verify and Register performs a fresh pinned
2.7.3 active-health and bounded non-root AppRole lookup before committing the
canonical connection and mandatory audit. SecretID is never rendered back.
Use the existing local pre-registration CLI to qualify exact audit and mount
metadata independently; connection registration does not attest those policies.

Internal: use deployment-owned KAORI_INTERNAL_SECRET_STORE_PROVIDER=openbao
and KAORI_INTERNAL_SECRET_STORE_ENDPOINT=https://secret-store:8200, with the
OpenBao-specific CA and allowlist. In the isolated Dev Container run
`flask register-internal-openbao --help`. The CLI obtains the AppRole SecretID
without echo, checks the configured endpoint and operator-pinned cluster, and
uses the same registration service. It creates one bundled connection, never
registers it as external, and refuses duplicates without destructive replacement.

The connection detail reads committed state, provides the canonical validation
worker action and runtime health refresh, and displays independent credential
authority as pending. Validation confirms connection evidence, never grants
ready status; scheduled health does not authenticate or retrieve secret data.
No generic client.build, credential onboarding, secret read/write, issuer
activation, worker material delivery, live policy change or production activation
is admitted. OpenBao-specific runtime history uses the canonical identity to
avoid cross-provider record-ID collisions. Local tests, migration rehearsal,
real provider UAT and official admission remain mandatory before promotion.

## Local metadata inventory (#5203 / #5204)

The local operator may collect one independently approved disposable KV v2
mount on an exact registered OpenBao connection. Set
`KAORI_LOCAL_OPENBAO_INVENTORY_PROVIDER_ID` to its canonical integration ID
and `KAORI_LOCAL_OPENBAO_INVENTORY_MOUNT` to the independently approved
mount, with the existing explicit development mode and provider-specific
TLS/CA/allowlist. Run `flask collect-openbao-inventory --help`. Supply the
short-lived non-root metadata token at the hidden prompt; its policy must be
limited to lookup-self, sys/mounts and LIST/GET on the approved metadata
mount, never KV data, Transit signing or administration. No mount/policy is
created. The scope, pinned native cluster UUID, exact KV v2 engine, token and
local registration are checked before/after the bounded metadata-only scan.
The commit requalifies the exact connection under lock and uses the existing
atomic SecretIdentity, SecretProviderRepresentation, SecretVersionObservation
and collection-state reconciliation, plus mandatory Activity Audit.
A failed scan retains history as stale/failed if the exact source remains
eligible; no partial snapshot is committed. OpenBao Detail shows counts and
timestamps only. Credential type, signed version proof, independent host
trust and worker use remain separate; metadata does not mark the integration
ready. No global Secret Detail exposure or provider access from GET.


### Exact issuer administration in local review (#5204)

OpenBao connection validation intentionally remains degraded until credential authority
is separately qualified. The existing issuer administration service can now qualify
a connected local OpenBao source on the independently configured inventory mount
without falsely promoting overall provider readiness. It requires the canonical
provider record, exact signed deployment receipt (including endpoint and cluster
identity), explicit current Access issuer scope and provider-native Transit inspection.
The canonical source is checked before native inspection and again in the locked
write transaction. Revocation remains available even when the source is disabled.
This does not qualify a credential type, activate automation credential-use grants,
or allow SSH/worker execution. Independent Access review, PostgreSQL and native
provider UAT remain required.
