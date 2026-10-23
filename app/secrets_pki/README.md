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


## Stored PKI certificate collection — bounded HV-03 follow-up

`secrets_pki.pki.stored_certs.sync` is separately optional, manual-only by
default and limited to 64 stored public certificates per PKI mount. Issuer
mount approval alone does not permit enumeration; the Vault connection
requires a separate default-off `pki_stored_certs_enabled` opt-in and a new
Full Validation. Committed state is stored in independent collection tables
and consumed through safe aggregate PKI readiness. This is **not** complete
issuance, expiration governance, CRL/revocation proof or endpoint delivery
assurance. See provider [PKI_STORED_CERTIFICATES.md](../integrations/secrets_management/secrets_pki/providers/vault/PKI_STORED_CERTIFICATES.md).


## Cross-domain public certificate overlap — HV-05 limited slice

Secrets & PKI Inventory now projects an aggregate comparison between
approved committed Vault **stored** public certificate fingerprints and
existing **Kubernetes TLS Governance** committed `tls.crt` fingerprints.
It is read-only and requires both `secrets_pki.view` and the independent
`tls_certificates.view` permission. No Kubernetes Secret name, Vault
serial/path, CN/SAN or key material enters ordinary presentation.

A fingerprint match proves only identical public certificate bytes across
observed sources, not Vault issuance provenance, controller materialization,
workload adoption, current endpoint TLS serving or successful rotation.
No-match is not a failure/verdict; collection unknown/partial/stale and
schema not migrated are explicit. The current preview is *not* a completed
Certificate Delivery Assurance feature. See
`CERTIFICATE_DELIVERY_CORRELATION.md` for source/coverage/UAT details.


## Ingress-reference qualification of public certificate overlap (HV-05)

The read-only public certificate overlap section now projects the number
of committed Kubernetes TLS Secrets actually referenced by a collected
Ingress mapping, and the subset with fully covered declared Ingress hosts.
It reuses existing Kubernetes TLS Governance `used_by` and
`coverage_state`, never provider HTTP calls or a new controller/TSDB.
Source read permissions and freshness are independent. Those figures are
**not proof** of Vault delivery, Ingress controller loading or current
endpoint TLS serving. See `CERTIFICATE_DELIVERY_CORRELATION.md`.

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

## Integrated Vault acceptance / UAT (#2593)

The exact-SHA coverage and acceptance matrix is maintained in
[VAULT_INTEGRATED_UAT.md](VAULT_INTEGRATED_UAT.md). It separates source
implementation from Not Tested / Not Implemented, requires existing quality
gates and real Vault/DevContainer evidence, and prohibits calling a review
merge a Full Admission or human UAT PASS.

## Scoped Secret Registry — prepared contract (#2678)

The source-owned [Scoped Secret Registry contract](SCOPED_SECRET_REGISTRY.md)
contains an unpublished, fail-closed committed KV v2 read model. It does
**not** activate Secret Detail, Vault path exposure, an HTTP route, or a
Scope Policy grant. A canonical #724 evaluator, scoped route/HTMX tests,
Violet registry UI, and human UAT are mandatory prerequisites. Global
`secrets_pki.view` alone does not permit per-Secret disclosure.

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

## Vault Secret Registry source-scope admission (#2689)

`registry_scope.py` supplies a pure deny-by-default qualification contract
for later per-source read models. It requires the global view permission,
**independently enforced** #724 resource scope, an explicit allowed
IntegrationInstance ID, fresh complete source evidence and bounded records.
It returns only count/status and **never** enables detail disclosure, Vault
path/name exposure, broad registry routes, grants, API calls or Secret values.
Until a canonical #724 scope policy is genuinely enforced, all attempts
must remain `scope_denied`; passing `scope_policy_enforced=True` without
an authoritative authorization decision is prohibited. The caller must
independently validate the queried committed record collection rather than
trust unscoped client arguments. Tests are located at
`tests/contracts/secrets_pki/test_registry_scope_contract.py`.

## Canonical Reporting coverage candidates — HV-15 #2694

The Reporting tab now reads six **Planned** report coverage items from
`app/definitions/catalogs/reports/coverage.yaml`, the same catalog consumed
by central Reports Overview. The list is permission-gated by `reports.view`
and cannot generate/schedule an artifact. No source-level Secret report
export is admitted while #724/#2688 authorization and HV-15 datasets,
sanitization, retained evidence and human UAT remain incomplete.


## PKI Expiration Analytics — HV-10 #2702

The new GET-only `/secrets-pki/analytics/certificates` view requires **both**
`secrets_pki.view` and `analytics.view`. Existing source-owned stored public
PKI certificate readiness (fresh/current generation, count coherence, opt-in,
approved mounts) now provides disjoint upcoming validity expiry bands: within
7 days, after 7 through 30 days, and after 30 days. Expired, not-yet-valid
and unknown chronology remain separate. The Inventory and capacity Dashboard
link to this view only with the Analytics permission. It reuses shared Violet
Hero/cards/section components, no live Vault calls and no new tables/jobs.

The new view is a **current-generation snapshot** only. No time-series,
forecast, revoked/trusted CA finding, Secret identity, owner, per-instance
drill-down, report export or inferred workload TLS serving is provided.
Disabled/failed/stale/incomplete source evidence removes **all numeric expiry
bands**, never replacing missing data with healthy zero. Future resource
specific drill-down depends on #724/#2688.

Focused tests extend
`tests/integrations/test_vault_pki_validity_posture.py`. Existing quality
gates and real Vault/PostgreSQL, RBAC, Visual QA/UAT remain required.

## Lifecycle & Assurance workspace (HV-07 #2761 — review implementation)

- `GET /secrets-pki/lifecycle` is capability-level, provider-neutral and requires
  `secrets_pki.view`. Its server-side route reuses bounded committed KV v2
  lifecycle, opted-in public PKI validity and Kubernetes TLS candidate overlap
  read models. The sidebar entry uses the existing Infrastructure Secrets & PKI
  workspace registry, not a Vault-specific navigation root.
- KPI cards only render numeric values after the respective source-qualified
  complete/current generation. `observed_empty` is a valid KV2 zero; blocked,
  stale and partial statuses show text, never invented zero counts.
- Correlation requires separate `tls_certificates.view` and never reveals
  certificate identities, paths, names or provider secrets. Fingerprint overlap
  is **not** Vault-to-controller delivery proof, workload adoption, certificate
  trust, rotation or endpoint serving.
- Existing `analytics.view` controls the canonical PKI Expiration Analytics
  deep link; the page itself is not a historical Analytics workspace.
- Human DevContainer light/dark/responsive Visual QA, exact-SHA backend tests,
  Developer Check, Full Admission and source-specific UAT are **pending**.

## Bounded Central Intelligence expiry pressure (#2778 / HV-11)

Central Intelligence reuses the qualified current-generation public stored PKI
certificate validity aggregate for one **capability-wide** Recommendation.
Severity is P1 if any expired, P2 if none expired but expiry within 7 days,
or P3 if only the 8–30-day window is affected. This does not identify the
affected source, Secret or certificate: an authorized operator must investigate
the provider directly before remediation. No Vault HTTP, Secret path, public
fingerprint, certificate serial, private material, provider ID or new engine.

Only a request actor with both `intelligence.view` and `secrets_pki.view`
can see the aggregate. Actorless evaluation is fail-closed until governed
worker-side scoped evaluation has its own implementation authority.
Only status `ready` and internally consistent complete counts can emit a
finding. Missing/stale/partial/disabled evidence does not imply a safe zero,
a resolved alert or collection success. There is no automatic AlertCase,
outbound notification, Accepted Risk policy override or per-asset assessment.
The other HV-11 rules remain unimplemented. Source code alone is not DevContainer
UAT acceptance; follow `VAULT_INTEGRATED_UAT.md` on exact tested SHA.

## HV-07 #2826 scoped KV v2 Registry browser admission

The previously internal-only Registry now has an explicitly scoped, audited
metadata-only GET page with an opaque policy-reference selector and default
five-item pagination. See `SCOPED_SECRET_REGISTRY.md` for strict access,
unsupported Detail/export and UAT boundaries. Never infer Secret read
privileges from `integrations.manage` or a provider admin role.
