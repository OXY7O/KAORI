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

**Current readiness:** this is the lower-level API/normalization slice only.
It is not yet connected to canonical `JobExecution`, scheduled collection,
committed storage, or the Secrets & PKI Inventory UI. Do not expose it as
`Available`, call it from an HTTP read route, or persist its unredacted
in-memory objects in Celery results, logs, notifications or exports. Next
bounded slices of HV-02 must implement durable canonical identities,
per-mount committed generation/freshness, job admission/worker ownership,
positive and negative persistence tests and real-Vault UAT. The dedicated
test file is `tests/integrations/test_vault_kv2_inventory.py`; pytest/ruff,
Alembic, actual Vault and security gates remain unverified until run.
