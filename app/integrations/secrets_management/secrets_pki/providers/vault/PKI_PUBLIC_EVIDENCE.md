# Vault PKI Public Issuer Evidence — HV-03

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

## HV-03 committed public issuer inventory — bounded review implementation

The Vault connection form now accepts an explicit approved PKI mount allowlist
(maximum four safe single-segment mounts); empty means **not eligible**.
Changing it invalidates provider Full Validation and must be saved through
the existing AppRole connection test/proof. The new
`20261022_vault_pki_evidence` Alembic migration adds `vault_instances.pki_mounts`
and the canonical tables:

- `secrets_pki_issuer_identities`: immutable local issuer ID and separate
  Vault source issuer UUID, active/not-observed state and source observation time
- `secrets_pki_public_certificates`: issuer-scoped SHA-256 fingerprint, serial,
  public validity and CA facts, and bounded chain fingerprint references
- `secrets_pki_pki_collection_states`: per-authorized mount state/freshness,
  committed issuer count, and sanitized error classification

**Security/persistence:** The worker may handle PEM transiently for X.509
parsing. No PEM, DN subject/issuer, SAN, issuer label, private key, key ID,
provider credential, Secret path, raw lookup payload or user token is
persisted or queued. Fingerprints are hashes of **public certificates**,
never hashes of Secret values. Issuer disappearance is `not_observed`,
not revoked/deleted. A rotated issuer certificate retains its immutable
historical fingerprint. Missing/stale mounts retain prior committed evidence,
and unexpectedly empty collection after prior nonempty results fails closed.
Trust and revocation remain **not evaluated**.

Registered `secrets_pki.pki.sync` runs through canonical Jobs & Executions
(default **Manual Only**), uses the existing `inventory` worker,
`secrets_pki.sync` + `jobs.execute` admission, and retains 1740s/1800s
worker deadlines. Celery carries only canonical integration instance IDs.
Vault reads remain restricted to `LIST /issuers` and public
`GET /issuer/<UUID>/json` on approved PKI mounts.

Operational **Inventory** and Vault Admin detail now display aggregate
approved/committed mounts, public issuer counts and freshness from committed
database state. A valid zero requires a successful real collection; no web
GET calls Vault. The pages do not claim that all issued leaf certificates
were enumerated or deployed to workloads.

**Complementary limited source:** Stored issued public certificates with explicit enumeration opt-in are defined in [PKI_STORED_CERTIFICATES.md](PKI_STORED_CERTIFICATES.md). This is not complete issuance coverage: no_store=true and imported certificates are not enumerable through Vault LIST /certs.

**Still NOT implemented:** complete issued certificate register/purpose,
PKI issuance/revocation, trust-chain evaluation, endpoint certificate
delivery, generic Lease enumeration, certificate row-level browser scope,
staging provider UAT and migration/admission proof. PKI public issuer
readiness is independent from core Vault API readiness.

### DevContainer checks (not attested)

Use existing PostgreSQL-first bootstrap and the reviewed Alembic migration
path; do not run migrations using the ordinary app DB role.

```bash
python -m pytest tests/integrations/test_vault_pki_public_evidence.py tests/integrations/test_vault_pki_committed_inventory.py tests/integrations/test_vault_pki_job_contract.py -q
python -m ruff check app/models/secrets_pki_pki.py app/integrations/secrets_management/secrets_pki app/secrets_pki/pki_presentation.py tests/integrations/test_vault_pki_*.py
python -m pyright
```

After approved migration/restart, configure PKI mounts and a least-privilege
AppRole, run Full Validation, verify the `inventory` worker advertises the
new task, and execute `secrets_pki.pki.sync` manually. Record exact
JobExecution ID, issuer counts, source 403/404/partial/stale behavior,
negative secret-retention checks, responsive Violet UI/HTMX Visual QA
and explicit human acceptance. None of those are currently claimed PASS.

See the dedicated collector tests and official Vault PKI API docs.
See https://developer.hashicorp.com/vault/api-docs/secret/pki for provider
source API behavior.
