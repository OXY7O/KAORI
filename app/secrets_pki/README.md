# Secrets & PKI — Operational Capability (HV-07, #2591)

## Ownership

KAORI's provider-neutral Secrets & PKI operational workspace owns safe,
committed-state presentation and future cross-domain correlation. Vault remains
authoritative for material, authentication, Secret engines and PKI issuance.
The Vault provider connection remains under
`Integrations → Secrets Management → Secrets & PKI → Vault`.

## First workspace slice

- `GET /secrets-pki/`: canonical four-tab Operational Dashboard following
  `docs/design/patterns/OPERATIONAL_DASHBOARD.md` v1.7. Tabs are exactly
  Operations Overview, Capacity & Demand, Signals & Actions, Reporting.
- `GET /secrets-pki/inventory`: safe, aggregated KV v2 metadata-only source
  coverage, first/last observed counts, and committed collection readiness.
- Both routes require server-side `secrets_pki.view` (HV-13, #2597).
  Connections and allowed mount configuration require `integrations.manage`;
  the worker job uses `secrets_pki.sync` + `jobs.execute`.
- Both routes read the canonical `VaultInstance` and
  `SecretInventoryCollectionState` only. **No live Vault request** occurs in
  page rendering. The scope is bounded to 25 active provider identities and up
  to eight approved mounts each. Over-budget scope is blocked rather than
  silently dropping sources and showing a misleading healthy KPI.
- No Secret path/name, KV value, hashes of values, AppRole credential, private
  key, or raw provider response is exposed by these pages. The source-specific
  provider identity is not published to viewer roles until #724 approved
  resource-scoping and future Secret Detail read models are admitted.

## Evidence and blocked states

A successful Vault API check does not prove KV v2 inventory readability.
A valid **zero** is shown only after an actual committed snapshot; missing
snapshots are `Not Collected`. Counts from stale or partial committed sources
remain explicitly labelled stale/partial; absent source is not deletion.
PKI issuance/certificates, lease posture, consumer correlation, Vault
Metrics Source, Alert Source, canonical Recommendations and Reporting are
shown as unavailable/not materialized until their dedicated workstreams are
admitted. Neither dashboard nor Inventory starts jobs on GET.

## Deferred work

Complete Secret/PKI/Lease/Consumer details, row-level source authorization
(#724), pagination at five per page, certified PKI inventory (#2587),
historical Analytics (#2594), Metrics/Alert bindings (#2590), central
Intelligence (#2595/#2596), Reports (#2599), and role-aware Welcome (#2598)
require their own admitted evidence contracts. The current workspace is the
minimal usable Overview/Inventory evidence slice, not the complete Vault
operations product.

## Validation before promotion

Use existing Developer Check, Ruff, Djlint, Pytest, Pyright, visual QA, RBAC
negative checks, PostgreSQL migration tests, Celery worker and actual Vault
KV2/read ACL UAT. No CI/DevContainer/UAT pass is claimed by the existence of
this source.


## HV-03 public PKI issuer inventory (review candidate)

Approved Vault PKI mounts are configured separately from KV v2 metadata mounts.
The canonical public PKI collector reads only Vault issuer metadata and the
`/issuer/<UUID>/json` public-certificate endpoint; `secrets_pki.pki.sync`
runs through default-disabled canonical JobExecution on the existing inventory
worker. Its committed models preserve independent per-mount freshness,
issuer identity and public X.509 fingerprint/validity history; issuer absence
is `not_observed`, never provider revocation.

The Inventory workspace and Vault integration Runtime workspace display
aggregate public issuer readiness from committed KAORI database state.
They do **not** expose Secret paths, certificate subject/SAN, raw PEM, issuer
labels, private keys or unqualified trust/revocation claims. Public issuer
history does not establish issued-leaf certificate inventory or delivered
endpoint certificate assurance.

Implementation and DevContainer acceptance steps:
`app/integrations/secrets_management/secrets_pki/providers/vault/PKI_PUBLIC_EVIDENCE.md`.
Migration: `20261022_vault_pki_evidence`. Tests must pass on real PostgreSQL
and supported Vault PKI mounts before a staging or capability-ready claim.
