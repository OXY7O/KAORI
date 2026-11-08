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

## Current-generation KV v2 Version Lifecycle aggregate (#2674)

The Secrets & PKI Inventory page now has a bounded, source-owned **aggregate-only**
version posture. It reuses the HV-04 `classify_kv2_version` semantics for
available, scheduled deletion, soft deleted, destroyed and unknown.
Full readiness requires approved enabled active Vault KV v2 sources, recent
(24h) ready committed mount scans, matching source generation and observed
representation counts, with strict record/version budgets. Historical
`not_observed` Secret representations and version rows not refreshed in the
current committed generation are excluded. Missing coverage, stale and
schema-not-ready states display Not Qualified, **never zero**; a qualified
committed empty mount may display genuine zero.

No provider read, Vault path/Secret name, value hash, raw ID, Secret data,
private key, auth material, mutation, new migration, Lease enumeration or
new scheduler is involved. A version destruction/soft-delete is Vault
material history, not verified revocation, rotation or consumer adoption.
Tests: `tests/integrations/test_vault_kv2_version_posture.py`.
Exact-SHA Ruff/Pyright/pytest, runtime PostgreSQL, RBAC and browser UAT still
need Developer Check/Full Admission; a review merge is not PASS.

## Impossible future source timestamps (#2704)

The current-generation KV v2 aggregate now refuses source-owned
`last_observed_at` **and** `last_committed_at` values later than the UTC
evaluation instant. A timestamp can appear recent but cannot be valid
committed provenance when it is in the future. Missing, stale and future
commit/observation times all produce `incomplete_evidence` and no
numerical lifecycle values, even when a mount claims an empty or
otherwise-valid generation. No historical rows are deleted or provider
data re-read; reconcile and inspect worker clock/time synchronization
before retrying the source-owned inventory job.
