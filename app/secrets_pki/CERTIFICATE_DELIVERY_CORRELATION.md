# Secrets & PKI: public certificate correlation (HV-05, #2589)

## Authority and evidence

This is a bounded, read-only **cross-domain fingerprint overlap** capability.
It does **not** demonstrate that Vault issued a certificate for a particular
workload, that any controller distributed it, that the workload adopted it,
or that a production endpoint currently serves it.

- Vault remains authoritative for its PKI mounts and stored public issuance
  records. KAORI consumes committed `PKIStoredCertificateObservation` from
  the optional explicit opt-in `secrets_pki.pki.stored_certs.sync` job.
- Existing `app/kubernetes/governance/tls_certificates` remains the
  authoritative KAORI adapter for committed Kubernetes TLS Secret and
  Ingress observations. This slice invokes no Kubernetes API or tls.key read.
- A matching SHA-256 fingerprint of **the public DER-encoded X.509
  certificate** is a deterministic *public certificate identity overlap*.
  The same certificate can reach Kubernetes by an unrelated import/controller,
  so fingerprint alone is **not** source-to-consumer provenance.
- No-match is only no-match in qualified observed sources. Missing,
  stale or partially collected sources are not negative evidence that a
  certificate was never issued or that an endpoint does not use it.

## Privacy and authorization

The normal Secrets & PKI Inventory page requires `secrets_pki.view`.
The cross-domain read model then requires the *independent*
`tls_certificates.view` permission before it queries Kubernetes TLS
Governance. This is a backend check; hiding UI components is insufficient.
The presentation emits **only aggregate counts**, source readiness and
unqualified/unknown state. It does not expose Vault mount/path/serial,
Kubernetes cluster/Namespace/Secret name, certificate CN/SAN/issuer,
TLS key material, public PEM, or unapproved provider response.

The read is bounded by 25 Vault instances, 100 approved PKI scopes,
100 Kubernetes collection states, and 1500 certificate observations on
each side. It blocks rather than silently truncating a fleet. Data is
filtered to enabled, active, separately opt-in Vault instances, approved
PKI mounts and successful committed source states no older than 24 hours.
Kubernetes must have a successful recent TLS Secret collection and fresh
persisted fingerprint; Ingress mapping success and endpoint serving are
**independent** and never inferred from the overlap count.

Readiness statuses:
- `overlap_observed`: identical public certificate seen on both qualified
  committed sources, **delivery_proven=false**.
- `no_overlap_observed`: no overlap within the currently qualified
  observed sample, not a failed deployment or revocation.
- `incomplete_evidence`: qualified subset available but source coverage
  is partial/stale; counts are only partial observations.
- `source_unknown`, `not_configured`, `permission_required`,
  `blocked`: cannot evaluate, counts are unknown rather than zero.

## Next source workstreams

For genuine **Certificate Delivery Assurance**, add an approved controller
or workload-origin proof linking the Vault-issued certificate fingerprint to
a typed Kubernetes TLS Secret identity, then a runtime endpoint TLS readback
(or qualified Ingress/controller service evidence) with explicit timestamp
and ownership provenance. Preserve link conflict, rotation replacement,
version/serial ambiguity, source retention, and per-source authorization.
These belong under HV-05/HV-03 and must use current Secrets & PKI lineage
contracts, not a second Kubernetes TLS collector or a new recommendation
engine. Central Alert Intelligence/Rules remains independent (#2595/#2596).

## Validation (not attested)

Targeted contract/integration source:
- `tests/contracts/secrets_pki/test_certificate_delivery_overlap_contract.py`
- `tests/integrations/test_certificate_delivery_read_model.py`

Execute the existing Ruff, pytest, pyright, djlint, and route/security/Visual
QA gates in the DevContainer at the exact review SHA. Verify stale/off/
unmigrated sources, unprivileged Viewer and Kubernetes TLS permission denials,
empty committed scans, matching/unmatching SHA-256, and no secret-name
disclosure. Real Kubernetes and Vault UAT plus human acceptance remain
pending. No CI PASS has been claimed by authoring these contracts.


## Ingress TLS reference and declared host identity (HV-05 follow-up)

This source extension uses `TLSCertificateInventory.used_by` and
`coverage_state` from **existing** Kubernetes TLS Certificate Governance.
The Ingress mapping source must independently report `collected` and
the TLS Secret source must be fresh; each matching Secret must have a
source-validated structured reference list. Empty is a valid zero only
when the collection actually completed. Invalid/missing references are
unknown, not proof of absence.

After a *matching public certificate SHA-256* and qualified Ingress
source, KAORI may report:
- number of matching Kubernetes TLS Secrets **referenced by a declared
  Ingress TLS Secret reference**;
- subset whose declared hosts are fully covered by the certificate
  hostname/SAN identity, where host count is nonzero.

These are Kubernetes configuration facts only. Ingress hosts matching a
certificate do not prove that a controller accepted the configuration,
loaded the Secret, routed traffic, reached a backend, served the expected
certificate to a TLS client, or obtained it from Vault.

No Ingress/Secret/DNS names or per-resource identities are emitted in the
Secrets & PKI aggregate cross-domain presentation; the existing
`tls_certificates.view` permission remains required **before** querying
Kubernetes Governance. Direct access and non-HTML HTMX behavior must be
UAT-tested with allowed and denied roles.

Future proof layers must be owned by authorized controller reconciliation
and external endpoint TLS readback sources with timestamp, TLS trust/route
context, provenance and policy-controlled destinations. No endpoint scanning
is added by this implementation. Existing collected Ingress mapping cannot
stand in for those missing source adapters.

Focused tests authored but not executed:
`tests/contracts/secrets_pki/test_certificate_ingress_assurance_contract.py`
and `tests/integrations/test_certificate_delivery_read_model.py`.
Run standard KAORI quality gates and human DevContainer Visual QA at the
exact reviewed commit.


## Kubernetes object UID identity bridge (#2589)

The Kubernetes TLS collector now persists canonical `metadata.uid` to
a nullable, new `TLSCertificateInventory.secret_uid` column. That UID
distinguishes a recreated Secret from the previous object even if the
cluster, namespace and name are reused. It is **source-owned** Kubernetes
evidence, not a Vault provider field or user-declared mapping.

The Secrets & PKI aggregate overlap page reports **matching TLS Secret
observations with canonical object UID**, independently from matching
certificate fingerprint and Ingress host/SAN coverage. UID values themselves
are withheld. Legacy/unobserved/malformed UIDs yield `Not Qualified`,
not a false successful object-identity claim. A qualified UID count
does NOT establish Vault/controller delivery, controller activation, issuer
identity, end-to-end TLS serving or successful rotation.

Before any genuine Vault→controller→Kubernetes lineage can be `confirmed`,
an approved source-owning controller adapter must produce a **separate**
readback/receipt identifying the Vault source identity, controller identity,
exact target cluster + Secret UID, public certificate fingerprint, scope,
observation timestamp and controller synchronization status. KAORI must
validate against both committed owner sources and effective dates;
a controller annotation, namespace/name match, and a certificate fingerprint
alone may only form candidates. Receiver authorization, source version,
conflicts and Secret UID replacement require explicit admission review.
No controller receipt or endpoint probe is implemented here.


## Controller owner candidate stage (#2589)

The existing TLS Governance collector now normalizes up to one typed,
canonical owner reference for a supported ExternalSecret or cert-manager
Certificate. Secrets & PKI Inventory reports the *aggregate number of
matching public-certificate TLS Secret observations* with an admissible
controller owner reference; UID/name/namespace remain hidden.

Proof ladder:
1. Vault stored public certificate fingerprint and Kubernetes TLS Secret
   public fingerprint are identical (identity overlap).
2. Kubernetes API reports a stable TLS Secret object UID.
3. Kubernetes API reports a supported controller owner reference (candidate).
4. **NOT IMPLEMENTED:** owning-controller reconciliation receipt and explicit
   Vault integration source identity, source version, destination Secret UID,
   fingerprint and observed generation, independently qualified against
   committed source evidence.
5. **NOT IMPLEMENTED:** controlled, authenticated endpoint served-TLS readback.

Stages 1–3 do not establish stage 4 or 5. Source collection stale/partial,
unknown/malformed owner references, unsupported controller policies and
replaced TLS Secret objects are not confirmation or failed delivery.
`vault_to_controller_proven`, `delivery_proven` and
`endpoint_serving_verified` remain False. No ownerReference may be used
to upgrade a `LineageEdge` to `confirmed` without a source-owning
controller readback adapter and its admission/security UAT.

## ESO reconciliation qualification contract (HV-05 child #2666)

Source owner: app/kubernetes/governance/tls_certificates/eso_reconciliation.py.
This is a pure source normalization and candidate qualification contract, **not**
an installed or active ESO API adapter, Vault delivery attestation, or UI feature.
It reads typed ExternalSecret metadata/status only: UID, namespace scope,
generation, optional observed-generation evidence, Ready condition,
refresh time, bounded sync-version marker and source observation time.
Arbitrary spec/SecretStore references, Vault paths and Secret data are not read
or retained in its normalized output; internal identities are never presented.

An eligible reconciliation *candidate* requires independent current Kubernetes
Secret UID corroboration, exact TLS Secret owner UID, and any present
observed-generation agreement,
fresh controller and TLS source evidence, exact cluster/namespace context and
a validated public certificate fingerprint. ESO Ready alone has no target
immutable Secret UID or Vault source/version receipt. Missing ESO
`syncedResourceVersion`,
permission denied, stale/malformed/ambiguous source, Secret UID recreation and
unknown current UID are **unknown**, not verified zero or delivery failure.
Even reconciled_candidate keeps vault_to_controller_proven, delivery_proven
and endpoint_serving_verified false; no confirmed lineage edges are produced.

No database migration, CRD call, new RBAC scope, worker, presentation change or
controller mutation is included. Before active collection: explicitly review
ESO CRD version/support, bounded Kubernetes custom-objects API and permission
scope, persistence/effective dates, resource-level authorization, separate
current Secret UID readback, Vault source binding and real source UAT.
Contract tests: tests/kubernetes/governance/test_eso_reconciliation_contract.py.

ESO CRD status normally provides `refreshTime`, `conditions.Ready` and
`syncedResourceVersion` instead of `observedGeneration`. The latter is
optional and, if supplied, must match metadata generation. A bounded
`syncedResourceVersion` marker only
qualifies *controller-reported status*; it cannot be compared directly to
current Kubernetes `metadata.resourceVersion` because status writes can
increment the resource version. The marker never proves current spec
reconciliation, Vault provenance, TLS Secret write, or target object UID.
