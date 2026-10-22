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
