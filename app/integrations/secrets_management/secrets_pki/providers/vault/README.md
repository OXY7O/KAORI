# HashiCorp Vault — Secrets & PKI provider (HV-01 / #2585)

## Authority

Integrations → Secrets Management → Secrets & PKI → HashiCorp Vault → Instance.

Vault controls Secret values, native ACLs, authentication, issuers and PKI keys.
KAORI owns approved integration registration, AppRole credential encryption,
bounded read-only observation, canonical capability/readiness evidence and job/audit history.
The **separate** operational Secrets & PKI Dashboard, safe KV v2 inventory,
consumer correlation, PKI evidence, Metrics/Alert Source bindings, Analytics, and
Intelligence are implemented under HV-02–HV-15. They are NOT implied by this foundation.

## Committed PKI readiness composition

Vault provider detail keeps its existing read-only public issuer and stored-
certificate readiness summaries. The owning `app.secrets_pki` modules still
produce these committed KAORI projections; the existing Flask composition root
`app/bootstrap/blueprints.py` registers their callables per application under
`kaori_vault_pki_readiness`. Provider UI consumes that registry with the same
Vault instance and fails closed if the source readers are not registered, rather
than importing the operational Secrets & PKI implementation (issue #4148).
No live Vault request, readiness override, secret, or permission bypass is added.

## Connection input ownership

`application/types.py` owns the immutable `VaultConnectionInput` value object.
The HTTP-owned `application/forms.py` validates and maps WTForms data to this
input; the provider application service and time-limited registration proof
consume the same typed input without importing the web form module. This
preserves AppRole SecretID proof binding, encrypted credential handling, and
readiness invalidation while enforcing the canonical route → service dependency
direction. Vault provider authority, operational read models and schemas are
unchanged.

## Secure setup

In both DevContainer web and validation/runtime worker environment:

```bash
INTEGRATION_CREDENTIAL_KEY=<existing approved Fernet encryption key>
INTEGRATION_VAULT_ALLOWED_ORIGINS=https://vault.internal.example:8200
INTEGRATION_VAULT_CA_BUNDLE=/etc/ssl/approved/vault-root-ca.pem  # optional if system trusted
```

### Authentication method versus mount path

The KAORI Vault provider currently implements **AppRole authentication
only**. The Add/Edit form's AppRole Mount dropdown is **not** a choice of
authentication methods: `Default AppRole Mount (approle)` sends the
`/v1/auth/approle/login` path, while `Custom AppRole Mount`
reveals the existing single-segment, server-validated mount path
(for example `team-approle`). Both use the same RoleID and encrypted
SecretID and preserve the 10-minute Test Connection proof, Full Validation
and runtime evidence boundaries. On Edit, existing custom mounts remain
selected and plaintext SecretID is never hydrated.

A future Kubernetes workload-identity, JWT/OIDC or cloud-IAM
authentication method requires its own reviewed connection schema,
credential/token acquisition and renewal contract, least-privilege
policy, isolation/security gates and staging UAT. Do not select an
unsupported method or interpret a renamed AppRole mount as an auth-method
change.

### Vault registration identity flush and transaction recovery

The first Vault connection registration creates an `IntegrationInstance`
before the `VaultInstance` child. PostgreSQL requires the canonical
`integration_instances.name` to be **non-null at the initial INSERT**.
The service populates `name`, provider/adapter keys, environment and
enabled state before flushing for the canonical ID; only then does it
write the generated `asset_key` into `metadata_json`.

Any SQLAlchemy failure during that initial flush must be followed by
`db.session.rollback()` before the route attempts Activity Audit or another
request-scoped database operation. The existing commit error path also
rolls back. A `NotNullViolation` followed by `PendingRollbackError` in
the **Vault Register** route is an application transaction/lifecycle
defect, **not** evidence that Alembic migrations are pending. Check
`flask db current` versus `flask db heads` separately and do not
disable constraints, stamp Alembic, or clear DevContainer PostgreSQL
volumes as a workaround.

### Full Validation and committed capability evidence

Vault connection Detail uses the canonical KAORI provider-validation
lifecycle: **Run Full Validation** submits the approved operation to
the shared `integration-validation` worker; the HTMX workspace shows
the active JobExecution state and polls an instance-bound task route.
Once terminal, it refreshes committed readiness, the tab badge and
the provider posture, and emits only user-authorized feedback.
Standard non-JavaScript form submission redirects back to Validation.

The API contract has **three required** observations: health,
AppRole login, and authenticated token `lookup-self`. The fourth
observation, `GET /v1/sys/mounts`, is **optional** mount discovery.
When AppRole cannot read optional `sys/mounts`, this is represented
as limited optional coverage, not missing core API evidence or a
permission to read Secret payloads.

A historical Vault release can have complete required API evidence
while compatibility remains `degraded`. Show required core coverage
accurately (e.g., `3 / 3`) alongside separate compatibility attention.
Vault remains authoritative for runtime status, policies, tokens,
Secret contents and PKI; provider Full Validation does not prove
separately committed KV v2 / public PKI / stored certificate inventory
or grant scoped Secret access. Runtime Refresh is independent.

### Minimum permission example and capability explorer (#4849)

The Configuration tab adds a read-only, provider-owned example next to the
canonical Connection Contract. **Minimum Full Validation** requires an
approved AppRole and a token able to read `auth/token/lookup-self`; the Vault
health and AppRole-login probes do not require broad token policy grants.
Separate optional examples illustrate:

- `read` on `sys/mounts` for optional engine discovery (a denial remains
  Limited, not a core Full Validation block).
- `list` on the root of a specifically approved KV v2 `metadata` mount
  and `read`/`list` below that metadata path. Replace the example mount
  placeholder with the reviewed real mount and narrow prefixes as needed.

Never grant KV `data/*`, Vault policy writes, token administration, or PKI
issuance through the baseline. A Vault administrator must approve and attach
the policies; viewing/copying the examples does not perform Vault mutations.
Policy source of truth is Vault; KAORI retains only authorized connection,
committed validation and independent inventory evidence. Verify requested
paths against actual Vault edition, namespace, mount path and AppRole settings.

The Validation tab's four factual API contracts are a server-filtered
Capability Registry with Search Capability, Requirement, Validation Status,
five-row default and a native View More evidence dialog. The dedicated
`GET /instances/<id>/capabilities` read-only fragment uses the same
`integrations.manage` authorization as Vault detail and only persisted
instance evidence; no new provider request or Secret records are returned.
A historical degraded Vault release can still show 3/3 required APIs,
while a denied optional `sys/mounts` check remains Limited. Empty filter
results do not indicate missing provider capabilities.

### Runtime tab status and concise operator action (#4879)

The Runtime & History tab badge reflects the latest **committed runtime
health** (Healthy, Degraded, Unhealthy, or Not Observed) using the
same `runtime_state.health_status_label` as Kubernetes; it no longer
says `Jobs & Evidence`. It is not a validation-readiness or job-progress
indicator. The Runtime Decision's Next Operational Action has short
state-specific instructions for desktop readability, with natural mobile
wrapping, and distinguishes a runtime health issue from release/API
validation readiness. No new runtime observation, live provider request,
credential permission, or status transition is introduced.

### Runtime & History workspace parity (#4872)

Vault's Runtime & History follows the approved Kubernetes-style
horizontal Runtime Decision, full-width Runtime Evidence and shared
Recent Runtime Observations registry. Current decision facts, provider
contract/version/capability context and lightweight diagnostic rows
are projected from the most recent committed Vault runtime observation.
A missing observation is Not Observed; validation or registration
does not imply current health. `provider_job_status` replaces raw
runtime task identifiers, and the existing POST Refresh Runtime operation
keeps the same worker/CSRF boundary.

The shared registry uses
`integrations/partials/_runtime_history.html` and the provider-neutral
`runtime_history_view` projector. The read-only, authorized
`GET /instances/<id>/runtime/history` fragment is explicitly
Vault-connection-scoped; Search/filters are not live Vault requests.
Observation Type, Runtime Health and Validation Readiness filters,
5/10/25/50 Rows, the posture strip and native View More modal are
provided by the same shared partial as Kubernetes, including its
evidence and diagnostic drill-down. Historic observation records
remain immutable and independent of current Full Validation and
KV v2/PKI collection. Older `history_page`/`history_per_page`
GET parameters retain fallback support while canonical links use
`page`/`per_page`.

### View More evidence details and safe CLI guidance (#4860)

The existing Vault Capability Registry has a Kubernetes-parity native
**View More** modal: Capability Decision, Contract Snapshot, three-part
Validation Evidence, Operational Decision (Impact and Recommended
Action), Governance Boundary, and Verification Command. The three
evidence panels explain the selected API contract, effective identity
boundary and committed result; they are not three independently
stored Vault check outcomes. Status is derived exclusively from
the current, qualifying Full Validation data. Degraded release
compatibility can coexist with three Ready required capabilities;
optional `sys/mounts` 403/404 is Limited; absence of current
evidence is Not Observed. No Secret inventory or runtime success
is inferred from these facts.

Human Visual UAT copy-density rule (#4864): all four Vault capability
View More dialogs share a one-line desktop summary for Capability Decision,
Verification Command guidance and Identity Boundary. Their three Validation
Evidence descriptions are concise, at most two lines at desktop width, and
wrap naturally on mobile. Committed Observation has its own short,
status-specific explanation rather than reusing the summary; this avoids
overlong evidence cards while preserving Ready, optional Limited,
Required Gap and Not Observed semantics. UI text limits do not reduce
provider evidence, add Vault permissions or hide a credential.

Operator-side CLI examples for `vault status`, `vault token lookup`
and optional `vault read sys/mounts` require an independently approved
Vault CLI context and suppress response output. They cannot
reproduce the managed AppRole identity or replace KAORI worker
evidence. **No copyable AppRole login script** is rendered: RoleID,
SecretID and ephemeral tokens must stay in the governed connection
and worker. The modal never executes a Vault request or grants
additional permissions.

### Connection feedback and optional inventory scope

Vault Add/Edit uses the existing KAORI top-right Operational Toast and
Activity Audit for **Test Connection**, rejected input/proof, failed
registration/update, and successful Register/Update. Read-only
Test Connection creates audit-only feedback (no Notification Deck spam);
successful Register/Update uses the persisted event and redirects to
Vault detail. The former full-width form success banner is retired.
Feedback never embeds SecretID, Vault tokens, raw provider error payloads
or database exception messages. The 10-minute, exact-field/user-bound
Test Connection proof is still required for Register and Save.
Full Validation and Runtime Refresh remain separate asynchronous
admission/committed-evidence workflows with their own Activity Center
lifecycle; queue success is not proof of completion.

Three independent optional collection controls on the connection form:

- **Approved KV v2 Mounts empty:** no approved KV v2 metadata inventory
  target; the inventory job skips the connection, and committed
  inventory readiness indicates `not_configured`. Vault Secret values
  are never read through this collector.
- **Approved PKI Mounts empty:** no approved public issuer inventory
  target, even when core AppRole readiness succeeds. Empty does not
  mean Vault has no issuers; it means KAORI has no collection scope.
- **Collect Stored PKI Certificates OFF:** authenticated certificate
  serial listing and safe public certificate metadata collection are
  not admitted. This is **separate** from Approved PKI Mounts; turning
  the checkbox OFF suppresses active coverage but preserves earlier
  committed historical evidence. Opt-in requires an approved PKI mount
  and additional read-only LIST/read capability.

All three may remain empty/OFF for initial registration and
Full Validation. Configuring scope later requires a fresh connection
test/proof and Full Validation; the source-specific inventory/PKI
Jobs & Executions remain separate. No source setting alters the native
Vault Secret engine or issues/revokes certificates.

### Governed production provider trust

Production does **not** use the DevContainer's ignored `secrets/trust/`
mount. Under the current `deploy/server/compose.server.yml` authority,
approved Vault CA material is installed separately on the host at
`/etc/kaori/trust/vault/ca.pem` and mounted read-only into the
`web`, `validation-worker` and `runtime-worker` processes as
`/run/kaori/trust/vault/ca.pem`. The approved production Vault HTTPS
origin and `INTEGRATION_VAULT_CA_BUNDLE` stay in
`/etc/kaori/app.env`; credential material remains in the encrypted
integration connection contract. See
[Production DNS and provider trust runbook](../../../../../../docs/operations/production-provider-dns-trust.md)
for host/readiness, admission and rollback conditions. Never reuse
`host.docker.internal` or an unapproved CA in production.

### Persistent Vault CA in DevContainer (Docker Desktop Kubernetes)

The root `secrets/` directory is already ignored by `.gitignore` and
`.dockerignore` and shared as `/workspace/kaori/secrets/` through the
existing DevContainer worktree bind mount. Keep the approved **public CA** on
the **host checkout** so container recreate/rebuild does not remove it.
No extra Compose volume or CA baked into a Docker image is needed.

For the reviewed local Docker Desktop Vault (namespace `vault`, TLS secret
`vault-tls` containing `ca.crt`, HTTPS origin
`https://host.docker.internal:29820`), from WSL at the **actual repository
checkout root**:

```bash
mkdir -p secrets/trust/vault
kubectl --context docker-desktop -n vault get secret vault-tls \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > secrets/trust/vault/ca.pem
chmod 0644 secrets/trust/vault/ca.pem
git check-ignore -v secrets/trust/vault/ca.pem
openssl x509 -in secrets/trust/vault/ca.pem -noout -subject -issuer -dates
```

The current lab CA is `CN=kaori-vault-ca` with notAfter
`2027-01-08 15:30:02 UTC`; schedule renewal and CA distribution before
expiry. Never extract `tls.key`, include the private key in the repository,
or reuse this CA for LDAP unless the LDAP certificate shares the issuer.

Set in the **ignored local** `.env` (not in the tracked example defaults):

```dotenv
INTEGRATION_VAULT_ALLOWED_ORIGINS=https://host.docker.internal:29820
INTEGRATION_VAULT_CA_BUNDLE=/workspace/kaori/secrets/trust/vault/ca.pem
```

Both the Flask web process (Test Connection) and `validation-worker` /
`runtime-worker` must load the same environment and be able to read this
path and resolve/reach the approved endpoint. In the DevContainer:

```bash
test -r /workspace/kaori/secrets/trust/vault/ca.pem
openssl x509 -in /workspace/kaori/secrets/trust/vault/ca.pem -noout -dates
```

Verify HTTPS from the actual container network with its approved CA bundle
(e.g., `curl --cacert /workspace/kaori/secrets/trust/vault/ca.pem
https://host.docker.internal:29820/v1/sys/health` if curl is installed).
WSL success alone does not prove that web/workers have the same DNS or egress.
Changes to `.env` require a Flask F5 process restart or a controlled Compose
service recreate (web and validation/runtime workers) to reload environment;
the bind-mounted CA itself persists. Never remove PostgreSQL/Redis volumes.

`vault status` from WSL confirms the operator's local Vault server is
initialized and unsealed but does **not** prove KAORI AppRole identity or
worker Full Validation. The reviewed Vault `2.0.4` falls in KAORI's
`>=1.9,<2.1` **extended** qualification band, not the `v2.1.x`
current-qualified band. Provider readiness evidence remains committed by
Full Validation, independently of HTTPS reachability.

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
mark the provider ready. Full Validation uses the versioned KAORI compatibility policy snapshot (2026-09-19): v2.1.x is current-qualified; v2.2+ requires a separately approved refreshed profile and is explicitly degraded/unverified rather than silently reported as ready.

Full Validation is queued through the existing
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
