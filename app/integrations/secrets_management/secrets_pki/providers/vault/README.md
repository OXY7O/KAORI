# HashiCorp Vault — Secrets & PKI provider (HV-01 / #2585)

## Authority

Integrations → Secrets Management → Secrets & PKI → HashiCorp Vault → Instance.

Vault controls Secret values, native ACLs, authentication, issuers and PKI keys.
KAORI owns approved integration registration, AppRole credential encryption,
bounded read-only observation, canonical capability/readiness evidence and job/audit history.
The **separate** operational Secrets & PKI Dashboard, safe KV v2 inventory,
consumer correlation, PKI evidence, Metrics/Alert Source bindings, Analytics, and
Intelligence are implemented under HV-02–HV-15. They are NOT implied by this foundation.

## Secure setup

In both DevContainer web and validation/runtime worker environment:

```bash
INTEGRATION_CREDENTIAL_KEY=<existing approved Fernet encryption key>
INTEGRATION_VAULT_ALLOWED_ORIGINS=https://vault.internal.example:8200
INTEGRATION_VAULT_CA_BUNDLE=/etc/ssl/approved/vault-root-ca.pem  # optional if system trusted
```

Do not commit real values or CA private material. The origins list contains exact HTTPS
origins and is fail-closed when missing. HTTPS verification is always enabled, proxy/netrc
inheritance and redirects are disabled, and a short request timeout is enforced.
Approved origins alone are not DNS pinning; environment egress rules and DNS
restrictions must independently constrain outbound Vault access.

Use a non-root, least-privilege AppRole for the KAORI integration. A reusable
appropriately scoped SecretID is necessary for Test Connection and subsequent worker
Full Validation; an AppRole configured with a one-use SecretID will be consumed at
first login. Rotate the AppRole SecretID through the approved operational process.
Vault client tokens live in worker process memory for the probe and are not persisted
in IntegrationInstance, JobExecution, runtime snapshots, or logs.

Test Connection checks Vault health, AppRole login and lookup-self. It does not
mark the provider ready. Full Validation uses the versioned KAORI compatibility policy snapshot (2026-09-19): v2.1.x is current-qualified; v2.2+ requires a separately approved refreshed profile and is explicitly degraded/unverified rather than silently reported as ready.\n\nFull Validation is queued through the existing
integration-validation worker; it checks the token and optional sys/mounts
metadata capability. A missing sys/mounts permission is an independently
qualified capability gap, not proof that Vault API is unavailable. Runtime Refresh
uses sys/health only and distinguishes active, standby, performance standby,
sealed, uninitialized, DR secondary, and unavailable states.

No Secret value, KV v2 data endpoint, private key, token issue/revoke or policy
write is permitted through HV-01.

## DevContainer review

After pulling `kaori/review/staging-uat` once changes are integrated,
follow `docs/operations/devcontainer-postgres-first-run.md`. Its privileged
`db-bootstrap` service owns the migration and runtime-grant admission. Never
run Alembic through application `DATABASE_URL` or on an unreviewed database.

`INTEGRATION_VAULT_ALLOWED_ORIGINS` is blank in the tracked `.env.example`.
Add the exact approved origin and retain the existing credential key in the ignored
local `.env` before starting web and workers:


```bash
# Follow the repository's standard .env / development database initialization.
# From Windows PowerShell on the host: only after reviewing the local
# schema upgrade and confirming the intended database target.
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only

# Inside DevContainer: check provider foundation without live Vault requests.
python -m pytest tests/integrations/test_vault_provider.py -q
python -m ruff check app/models/vault.py app/integrations/secrets_management tests/integrations/test_vault_provider.py
```

Open Integrations → Secrets Management → Secrets & PKI → HashiCorp Vault;
register an approved Vault connection, then exercise Test Connection,
Full Validation, Runtime Refresh and edit/readiness behavior. Verify actual
PostgreSQL/Alembic migration, browser light/dark and responsive flow, worker
queues, least-privilege 403 response and CA/SSRF negatives. These focused steps
do not substitute Developer Check, Full Admission, staging UAT or human acceptance.

If no real Vault instance is configured, do not claim connectivity, inventory,
Analytics or Intelligence has passed UAT.


## HV-03 public PKI issuer evidence — initial source contract (#2587)

`pki_public_evidence.py` implements a bounded, *in-memory* observation
contract for a single explicitly provided Vault PKI mount. Based on the
official HashiCorp PKI HTTP API, its only allowed operations are:

- `LIST /v1/<pki-mount>/issuers` (issuer identifiers and safe labels)
- `GET /v1/<pki-mount>/issuer/<UUID>/json` (public issuer cert and chain)

The AppRole identity is authenticated through the existing scoped Vault client.
The collection permits a maximum of 24 issuers, eight chain certificates per
issuer and 32 DNS SANs. It parses X.509 public certificates in memory, then
projects *only* SHA-256 certificate fingerprint, public serial, subject/issuer,
validity, basic CA constraint, self-issued name posture and DNS SAN. The
response's unknown fields, key identifiers, `private_key`, provider tokens and
raw certificates are never committed by this source contract or placed in
Celery payloads. `self_issued` is not proof of valid self-signature.
Trust and revocation remain `not_evaluated`; CRLs and trust stores have their
own future qualified evidence and policy semantics.

**Compatibility:** Multi-issuer discovery is supported in Vault 1.11+.
For older or unsupported mounts, 403/404 and malformed responses fail closed
with a sanitized error; they do not degrade core Vault API readiness and must
not be reported as zero issuers. Listing **issued leaf certificates** via
`LIST /certs` is intentionally excluded because that is a separate authenticated,
incomplete-by-design enumeration capability (e.g., certificates issued with
`no_store=true` are absent). Privileged `GET /issuer/<id>`, key exports,
issuance, revocation, and key management are strictly out of scope.

**Not yet implemented:** approved PKI mount configuration, canonical issuer
and immutable issued-certificate persistence, per-mount collection/freshness
state, JobExecution worker, role/scope-safe PKI or Certificate UI and real-Vault
UAT. This code is source-contract preparation only; do not advertise PKI
Inventory as Available. Use the dedicated test file
`tests/integrations/test_vault_pki_public_evidence.py` in existing QA gates.
See https://developer.hashicorp.com/vault/api-docs/secret/pki for provider
source API behavior.
