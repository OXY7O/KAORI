# Vault Stored Certificate Evidence — HV-03 (#2587)

## Scope and authority

This is a bounded, optional read-only source contract for *stored* public
Vault PKI certificates. Vault remains authoritative for issuance, internal
certificate storage, revocation, keys and all issuance roles. KAORI commits
evidence for source-qualified operational correlation only.

The following Vault endpoints are used per **explicitly approved PKI mount**:

- authenticated `LIST /v1/<mount>/certs` — serial numbers of stored certs
- `GET /v1/<mount>/cert/<serial>` — public X.509 JSON by known serial

The source collector never calls sign, issue, revoke, tidy, key, private,
credential or certificate metadata mutation endpoints. The existing approved
Vault AppRole is required to have a least-privilege LIST `certs` capability,
separate from the existing public issuer LIST/read support.

**Provider coverage limitation:** Per HashiCorp's PKI API, `LIST /certs`
contains only certificates retained by that PKI mount and issued under
`no_store=false`. It does not include `no_store=true` issuance or imported
root/intermediate certificates and may vary across Performance Replication
clusters. It is not an estate-wide issuance register. An observed count of
zero is valid only for a successfully completed bounded listing and does not
assert no certificates were issued globally.

Official API: https://developer.hashicorp.com/vault/api-docs/secret/pki

## Separate explicit opt-in

Vault registration includes `pki_stored_certs_enabled`, a default-disabled
Boolean field. It must be explicitly enabled and saved through the existing
connection test-proof; modification resets Full Validation. Approved PKI
mounts alone are **not permission** to enumerate stored certificates.
Source/worker/transaction/readiness independently recheck this permission.
Turning the opt-in off suppresses active coverage, preserves committed
historical source data and prevents further admission.

The scan admits at most 25 Vault provider instances, four PKI mounts per
provider, and **64 stored certificate serials per mount**. Above 64 the
entire source generation fails closed *before* per-certificate GET requests.
The limit is intentional; large PKI deployments need a separate source
architecture and approved evidence budget, not hidden truncation.

## Committed state

Migration: `20261022_vault_stored_certificates` follows
`20261022_vault_pki_evidence`.

- `secrets_pki_stored_cert_observations`: immutable source/mount/serial,
  SHA-256 fingerprint of **public certificate**, X.509 validity timestamps,
  effective observation status and last-observed time
- `secrets_pki_stored_cert_collection_states`: independent mount-scoped
  success/failure/coverage/freshness and retained observed count

Only public certificate serial/fingerprint and validity are persisted. Serial spellings are canonicalized by integer value so colon-separated and leading-zero variants cannot create duplicate evidence.
Public PEM is parsed in worker memory and discarded. No private keys,
Secret values/hashes, CN/subject, SAN, DNS metadata, source credential,
provider raw response, URL or certificate Issuer name is stored.
The operating UI renders **only aggregates** with server-side capability
RBAC. It never exposes unbounded serial enumeration to viewer roles.

Reconciliation preserves evidence on source failure/partial/overbound lists,
out-of-order observations and opt-in revocation. Vanished serials are
`not_observed`, never automatically `revoked`, `expired`, `deleted`
or a reason for a central Intelligence finding. Expiry is a public fact
relative to the observation time, not proof a consumer still serves it.

## Execution and UI

Registered JobExecution: `secrets_pki.pki.stored_certs.sync`; default
**disabled/manual**; `inventory` queue; `secrets_pki.sync` and
`jobs.execute` for governed manual execution; `integrations.manage`
for policy configuration. Celery carries canonical integration instance
IDs only, without mount path, serials, PEM or tokens.

`Secrets & PKI → Inventory` and Vault admin detail display committed,
qualified status and observed counts separately from public issuer evidence.
`Not Collected`, `Not Enabled`, `Partial`, `Stale` and genuine
committed zero are distinct. No provider call occurs during normal page GET.

## DevContainer UAT and validation (not yet executed)

- Run existing `ruff`, `djlint`, `pyright`, `pytest` and Full Admission
  gates on the exact reviewed SHA.
- Use the authorized migration/bootstrap account to upgrade PostgreSQL;
  verify round-trip downgrade in a disposable DevContainer database only.
- Configure PKI mounts but keep the new opt-in off: assert the new job is
  blocked and no Vault LIST /certs is invoked.
- Opt in, pass Test Connection and Full Validation; run the default-disabled
  registered job manually through canonical Jobs & Executions with worker
  queue `inventory`. Use sample certificates with `no_store=false`.
- Verify one accepted serial and public fingerprint, >64 limit blocked,
  duplicate/invalid serial, mismatched X.509 serial, 403/404 denial,
  concurrent opt-in removal, partial/stale and historical snapshot retention.
- Negative test all serial/PEM/CN/SAN/token leaks in task results, logs,
  templates and ordinary Viewer/Auditor routes; verify responsive Violet
  light/dark UI and explicit human acceptance.

No CI PASS, real Vault provider UAT, migration execution, deployment or
certificate-delivery assurance has been attested for this slice.

## Stored public PKI certificate validity aggregate (#2683)

The Secrets & PKI Inventory workspace adds read-only UTC validity-window
counts for **currently observed, explicitly opted-in Vault stored public
certificates**: within validity, not yet valid, expired, and unknown chronology.
The derived state requires every approved PKI mount to have current ready
and complete committed observations (up to 25 instances, 100 mounts and
64 certificates per mount). Missing/denied/expired collection freshness,
source opt-out, generation mismatch or count conflict returns Not Qualified,
not zero. Historical not-observed rows do not enter counts. A committed
empty collection is a legitimate observed zero, not complete PKI coverage.

No arbitrary expiry-warning horizon, global renewal policy, CA trust,
revocation verdict, consumer adoption or endpoint serving is implied.
Serials, public fingerprints, Secret paths, SAN/CN, issuer names, PEM,
private keys, credentials and raw provider bodies are not exposed by this
aggregate. No additional Vault API call, migration, worker or permission.
Tests authored in tests/integrations/test_vault_pki_validity_posture.py;
real provider, PostgreSQL, exact-SHA CI, Visual QA and human UAT pending.
