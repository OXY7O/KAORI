# OpenBao — shared Secrets & PKI provider (#5200/#5201)

The accepted direction is one OpenBao provider for both bundled platform-owned
and optional external managed instances. Ownership is not inferred from an
endpoint or name. This package is not yet registered in the runtime catalog.

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
