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
contain exact boolean active/initialized/unsealed/non-standby flags, and
report the selected version 2.7.3. Missing, malformed or contradictory
fields fail closed, without affecting existing Vault observation behavior.
No authentication token, secret material, provider mutation or registry
write is involved. This is a health gate only, not proof of provider identity,
OCI provenance, storage TLS, policy, audit, AppRole or recovery readiness.
The actual bootstrap writer remains pending review of exact policy and mount
contracts; no automatic initialization, unseal or root credential access.
