# Secrets & PKI lifecycle evidence — HV-04 (#2588)

This bounded slice defines domain-owned evaluation contracts. It is **not** an
admitted Lease source collector, stored policy engine or privileged Vault workflow.

## Independent axes

- KV v2 metadata: `available`, `scheduled_deletion`, `soft_deleted`,
  `destroyed`, `unknown`. Interpret `deletion_time` relative to observation;
  a future `deletion_time` is a scheduled event, not proven current deletion.
- Static Secret logical lifecycle: future policy/owner-owned retirement state,
  separate from KV metadata; never mutate logical Secret identity on version
  change, and never infer a compromise or rollback from provider version alone.
- Rotation: version change is **only** material-authority evidence. Versioned
  policy, explicit approved consumer UUIDs, deterministic controller/workload
  readbacks of the required target version, and an independently attested
  cutover timestamp are needed before the derived status can be `verified`.
  Unknown/missing consumer readbacks are not a successful rotation. Overdue
  only applies to an explicitly specified age threshold and a verified cutover.
- Lease: a source-owned opaque KAORI UUID represents *one known Lease*.
  The provider lease ID, dynamic username/password, token, secret path, token
  accessor, raw lookup JSON and value hashes are prohibited in ordinary KAORI
  evidence. An expiry window that has elapsed is **unverified**, not proven
  expired, revoked or deleted; renewed leases and source outages require newer
  authoritative observations. No `LIST` or arbitrary Lease enumeration.

## Source authorization and coverage

HashiCorp documents `POST /v1/sys/leases/lookup` for lookup of **an already
known lease_id**, and `LIST /v1/sys/leases/lookup/:prefix` requires Vault
`sudo` capability. This phase implements neither endpoint; privileged
enumeration and provider renewal/revocation are out of scope. Qualified
issuance receipts and authorized known-lease lookup are candidate future
bounded source adapters only, each requiring approval, custody and redaction
review. The lifecycle evaluator cannot itself attest a readback or a provider
status; callers must use committed, independently qualified evidence.

See official provider references:
- https://developer.hashicorp.com/vault/api-docs/system/leases
- https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2

## Next bounded HV-04 slices

Approved retention and policy-version persistence, source qualification,
opaque identity linkage, committed cutover/Lease observation storage,
governed JobExecution, safe Governance/Analytics feed and negative real-Vault
UAT. Reuse existing Data Lifecycle, existing RBAC and central Intelligence;
do not create a second rule engine, provider secret store or scheduler.

Focused tests authored:
`tests/contracts/secrets_pki/test_lifecycle_evidence_contract.py`.

**QA state:** Source/test authored, pytest/ruff/pyright and PostgreSQL/real
Vault UAT not yet attested. Do not present Lease or verified rotation as
Available in UI based on this source contract.
