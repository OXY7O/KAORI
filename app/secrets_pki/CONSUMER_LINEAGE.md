# Secrets & PKI consumer/materialization lineage — HV-05 (#2589)

## Ownership and evidence

Canonical KAORI Secret identity is not the Vault mount/path. A source
provider remains authoritative for material; Kubernetes, Service Catalog,
automation/CI or another owning domain supplies **typed** downstream
materialization and consumer references. The correlation contract does not
own workload mutations, controller setup, Secrets synchronization or CMDB.

Every edge must have opaque canonical UUID identities and independent
evidence provenance, effective dates, last observation and a status:
`candidate`, `confirmed`, `rejected` or `conflict`. Names, namespaces,
Vault paths and close timestamps do **not** establish a confirmed edge.
An operator-approved mapping is a candidate, not proof of runtime use.

## Direction and attribution

```text
Canonical SecretIdentity UUID
    └─ secret_to_materialization → Typed materialization UUID
         └─ materialization_to_consumer → Typed consumer UUID
```

Confirmed lineage demands two confirmed, effective edges with deterministic
owning-domain references. The graph supports M:N. A rejected/conflicting edge
disqualifies that link; no automatic tie-break. An expired edge is historical
only, not a confirmed current use.

A projection may describe current impact **only** when both Secret source
freshness and cross-domain correlation freshness are `ready` and the
authorized consumer set was independently supplied by the owning domain.
Otherwise confirmed history can be surfaced as `historical_only`, never
turned into current blast-radius certainty. Consumer UUID output is
authorization-filtered. No paths/names, credentials, keys or provider raw
responses belong in the graph contract.

## Not delivered in this slice

No relationship database migration, effective-dated committed relation
worker, Service Catalog/Kubernetes/controller evidence adapter, endpoint,
UI, per-source RBAC resolution, controller deployment or active outage
blast-radius feed. This source-level contract must not be advertised as
an available Consumer Inventory until those bounded source-owner adapters
and DevContainer UAT pass.

Source checks:
`tests/contracts/secrets_pki/test_consumer_lineage_contract.py`.

Use established KAORI Developer Check, Full Admission, authorization and
Data Lifecycle retention policies; no custom graph engine or generic
MegaBinding table is introduced.


## Certificate fingerprint correlation (HV-05 extension)

`certificate_delivery_read_model.py` reuses existing committed TLS
Governance source records and optional Vault stored-public-certificate
records. The aggregate matching fingerprint is a *certificate identity
overlap only*. It does not create a confirmed
`secret_to_materialization` or `materialization_to_consumer` edge:
the missing provenance/endpoint serving readback is still a candidate.
Full evidence requirements are in
`CERTIFICATE_DELIVERY_CORRELATION.md`; no relationship database or
controller source has been silently added.


## Ingress TLS reference evidence — no implicit confirmed lineage

The Vault/Kubernetes overlap read model now consumes existing committed
Kubernetes TLS Governance `used_by` Ingress references and SAN/host
coverage counts for matched public certificates. This is evidence of
**Ingress referencing a Kubernetes TLS Secret** and of declared-host
identity matching; it is not a confirmed Vault `secret_to_materialization`
edge, controller synchronization proof, workload adoption or endpoint
serving. Source freshness and `tls_certificates.view` remain mandatory;
incomplete/malformed Ingress mapping yields unknown, not negative proof.


## Immutable Kubernetes TLS object UID

The existing TLS Governance collector records an optional, canonical,
immutable Kubernetes Secret object UID for newly collected source rows.
It is an essential future target-object identity for the confirmed
`materialization_to_consumer` chain: namespace/name may be reused on
replacement, and legacy `NULL` means no UID provenance. Cross-domain
Inventory shows only a bounded aggregate coverage counter, not those
identifiers. The UID does not prove distribution from Vault, controller
adoption, Ingress controller activation or endpoint serving. A source-owned
controller receipt and separate admitted match process remain pending.


## Kubernetes controller owner reference is a *candidate* (#2589)

Owning-domain TLS Governance may now commit a bounded typed controller
`ownerReferences` UID for ExternalSecret/cert-manager Certificate resources.
The reference is not a Secret source identity, controller sync receipt,
source binding, PKI issuance proof or readback of Kubernetes Secret content.
It is not an eligible `controller_uid` *confirmed* edge by itself; use it
as candidate identity for future controller-specific readback. A confirmed
Secret→materialization edge requires independent source-bound controller
evidence and exact current Kubernetes Secret UID and fingerprint, with
effective date, expiry/conflict and authorization checks.
