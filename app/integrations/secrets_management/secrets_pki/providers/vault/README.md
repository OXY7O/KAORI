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


## HV-02 safe KV v2 metadata collector — source-contract slice (#2586)

`kv2_inventory.py` provides a **bounded, in-memory, metadata-only collector** for
one explicitly selected Vault KV v2 mount. It authenticates through the
existing AppRole client, calls only Vault `LIST /v1/<mount>/metadata[/prefix]`
and `GET /v1/<mount>/metadata/<secret-path>`, and normalizes an allowlist
of version/creation/deletion/destroy facts. It deliberately excludes custom
metadata, secret values, KV `data` endpoints, raw provider errors, tokens
and any unknown fields.

The AppRole policy needs the specific KV v2 mount's `metadata` list/read
rights. The caller must supply the approved mount name; the collector does
not enumerate all system mounts or claim KV v1 equivalence. This contract is
limited to **200 secret records**, **200 entries per list response**,
**100 version records per secret**, and **8 directory levels**. Any denied
request, missing metadata, malformed list or size/depth breach raises a
sanitized error and must never be treated as an empty successful collection.
Path segments are strictly normalized and percent-encoded before sending;
unsupported path characters are an explicit capability limitation.

**Current readiness:** API/normalization plus a provider-neutral committed
metadata schema and transactionally guarded reconciliation service have been
authored under HV-02. ORM models are in `app/models/secrets_pki.py`; migration
`20261022_secrets_pki_inventory` adds Secret identity/representation/version
and per-mount collection state. `app/integrations/secrets_management/secrets_pki/commit_inventory.py`
persists a complete observed generation, retains historical versions and
marks missing representations `not_observed` rather than deleting them.
An unexpectedly empty scan cannot replace a previously nonempty snapshot.
Sensitive Vault paths are scoped metadata; a digest indexes the provider path,
**not a Secret value**. Historical evidence restricts deletion of its parent
integration registration.

The source contract now dispatches through canonical **Jobs & Executions**:
registered `secrets_pki.inventory.sync`, default schedule **disabled**, manual
execution requiring `jobs.execute` and `integrations.manage`, scheduled
policy editing requiring both `jobs.configure` and `integrations.manage`, inventory
worker registration/preflight, bounded per-instance approved mount scope,
canonical `JobExecutionContext` progress and sanitized partial/failure
outcomes. The provider registration form exposes an explicit comma-separated
KV v2 mount allowlist (maximum eight); empty means **no inventory eligible**.
Changed mount configuration invalidates existing Full Validation. Workers
read configured scope and AppRole SecretID from secure server-side state,
not Redis task arguments. Collection error marks scoped collection
`stale`/`failed` while preserving the last complete committed evidence.

It is **not yet exposed through the provider-neutral Secrets & PKI Inventory
workspace**; sensitive reference listing/search/exports remain unimplemented
until the #2597/#2591 scoped RBAC and UI review. Real Vault and Postgres
upgrade/downgrade acceptance is not yet available.
 Do not expose it as
`Available`, call it from an HTTP read route, or persist its unredacted
in-memory objects in Celery results, logs, notifications or exports. Next
bounded slices of HV-02 must implement resource-scoped inventory read projections,
security and negative-path tests, and real-Vault UAT. Focused tests are `tests/integrations/test_vault_kv2_inventory.py` and
`tests/integrations/test_vault_kv2_committed_inventory.py`; pytest/ruff,
Alembic, actual Vault and security gates remain unverified until run.


### HV-02 focused checks (not yet attested)

```bash
python -m pytest tests/integrations/test_vault_provider.py tests/integrations/test_vault_kv2_inventory.py tests/integrations/test_vault_kv2_committed_inventory.py tests/integrations/test_vault_inventory_job_contract.py -q
python -m ruff check app/models/secrets_pki.py app/integrations/secrets_management/secrets_pki tests/integrations/test_vault_kv2_*.py tests/integrations/test_vault_inventory_job_contract.py
```

DevContainer sequence: apply Alembic migrations using the repository's standard
initialization; register an approved Vault AppRole; specify only explicitly
authorized KV v2 mounts; Test Connection then Full Validation; start/restart
the `inventory` worker; open Jobs & Executions → Secrets & PKI Inventory Sync,
run manually and review source-state freshness. The Vault API may return 403
when list/read permissions on metadata are not granted. A successful provider
health check does not imply inventory permissions. Do not claim a passing
migration, worker check or Vault UAT until actually observed.

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
