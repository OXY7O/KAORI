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
execution requiring `jobs.execute` and `secrets_pki.sync`, scheduled
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
until the #2591 scoped Inventory UI and full #724 source-level read authorization are reviewed. Real Vault and Postgres
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


### Secrets & PKI authorization (HV-13, #2597)

The canonical Access Permission Catalog includes `secrets_pki.view` for safe
committed operational metadata and `secrets_pki.sync` for metadata-only
JobExecution admission. Sync depends on `secrets_pki.view` and `jobs.execute`.
Viewer/Auditor cannot start scans; Operator/Editor/Admin receive governed sync.
Vault registration, AppRole configuration, approved mount changes and automatic
job-policy configuration still require `integrations.manage` (policy update
also requires `jobs.configure`). No `secrets_pki.reveal` permission or generic
plaintext/material access is introduced. Full path-level inventory read models
remain blocked on bounded server-side source scope (#724) and Vault operational
workspace acceptance (#2591); RBAC grants must not be interpreted as enabling
a Secret value reader.

## Integration landing reuse (HV-01 #2732)

The existing `Integrations → Secrets Management → Secrets & PKI → HashiCorp Vault`
landing uses the same canonical provider hero, four-metric overview and
Coverage/Connection Registry tab macros as Harbor. The registry retains
server-side pagination (default five). Counts describe Vault *API* readiness
only; the Coverage tab explains independent Inventory, Metrics Source and
Alert Source contracts without fabricated success states. The Connection
Registry retains the existing detail and registration routes. No second Vault
provider registration, policy-grant UI or resource metadata disclosure is
introduced. Human light/dark/responsive Visual QA remains required.

## Capability workspace links (HV-07 #2775)

Vault Integration instance detail uses the existing Violet shell and links to
Secrets & PKI Overview, Inventory and Lifecycle & Assurance only for a user
with independent `secrets_pki.view`. Certificate Analytics also requires
`analytics.view`. These are aggregate, capability-level routes; no Vault
instance selector, scope grant or Secret path is propagated. A manager with
only `integrations.manage` receives a safe permission-required explanation,
not an operational evidence link. Visual QA and exact-SHA UAT remain required.
