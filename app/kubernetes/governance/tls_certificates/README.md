# TLS Certificate Governance

## Ownership

This module owns read-oriented certificate governance:

- Kubernetes TLS Secret certificate discovery;
- validity classification from an explicit global policy;
- SAN/Common Name identity extraction;
- declared Ingress host coverage;
- Ingress consumer relationships;
- collection evidence and synchronization.

Kubernetes Secret Operations owns single and bulk certificate rotation.

## Validity policy

Defaults:

```text
TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS=30
TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS=7
```

Expiry uses the exact `not_after` timestamp. Validity labels are Valid, Renewal Window, Critical Window, Expired, Invalid, and Unknown.

## Collection evidence

Each cluster records independent evidence for:

```text
Secret Collection
Ingress Mapping
```

A missing Ingress consumer is not treated as a successfully collected zero-consumer result when the Ingress source failed or was not permitted.

## Database schema readiness

TLS Governance requires Alembic revision `20260731_tls_evidence`. Before any ORM inventory query, the service inspects the required table and evidence columns without loading `TLSCertificateInventory`. An older reachable schema renders an operator-facing upgrade blocker on Governance and TLS Rotation pages, disables direct synchronization and rotation requests with HTTP 409, and does not fall through to an `UndefinedColumn` 500 response.

The required upgrade commands are:

```text
flask --app run:app db upgrade
docker compose -f compose.production.yml run --rm migrate
```

The database migration remains mandatory; the readiness blocker is a safe failure boundary, not a compatibility substitute for the new evidence contract.

## Data minimization

The Kubernetes client may receive Secret objects transiently. Collector code may access and decode only `tls.crt`. It must not access, decode, log, persist, notify, or audit `tls.key` or unrelated Secret values.

## UI pattern

The page follows `docs/design/patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md`:

```text
Compact Hero
TLS Collection Snapshot
Certificate Validity Posture
Compact Certificate Registry
Full Workspace Modal
```

The dedicated detail route remains a direct-link and no-JavaScript fallback. Table actions open the shared modal directly; no inline expanded row is used.

## Permissions

Active Governance permissions:

```text
tls_certificates.view
tls_certificates.sync
```

Mutation handoff permissions:

```text
kubernetes_secrets.rotate_tls
kubernetes_secrets.bulk_rotate_tls
```

TLS mutation authority is owned exclusively by the Kubernetes Secret permissions above. Retired Governance mutation permissions are removed from the registry and migrated to their canonical equivalents.
## Operational feedback and Notification Deck

TLS Governance uses two distinct execution paths:

1. **Inventory synchronization** runs through the canonical inventory `JobExecution`. The page shows a compact progress toast and live operation panel. Queued acknowledgement is transient and does not create a duplicate Notification row. The worker writes terminal Activity Audit and requester Notification Deck evidence before closing the job; the terminal toast reports the actual persistence result.
2. **TLS Secret rotation** is a foreground mutation. Validation is transient. Single and bulk terminal outcomes are persistent in toast, Notification Deck, and Activity Audit, including success because certificate replacement is a governance-significant change.

Only safe metadata may be delivered: cluster, namespace, Secret identity, certificate fingerprint, validity dates, SAN coverage counts, job identifiers, and result counts. Certificate bytes and private-key material are never persisted or rendered.

The canonical workspace is `_page_workspace.html`, the canonical job presenter is `job_presentation.py`, and active progress uses `_sync_progress_toast.html`. The removed `toast.py`, `_inventory_scope.html`, `_content.html`, and `_sync_toast.html` files must not return.

## Final release evidence

The final Governance release boundary is reviewed through the KAORI L0–L7 strategy:

- **L0 Static Quality:** canonical quality gate plus `verify_governance_final_lock.py` and the TLS Governance verifier.
- **L1 Contract:** Governance/TLS ownership, collection, mutation, worker, and final-release contracts.
- **L2 Unit:** certificate validity, hostname matching, and terminal sync-outcome policy.
- **L3 Functional:** request-level AuthZ-before-readiness behavior for TLS inventory and sync status.
- **L4 Integration:** SQLAlchemy certificate registry pagination/read-model behavior.
- **L5 Security Regression:** permission ownership, requester-scoped job visibility, private-key minimization, and payload scrubbing.
- **L6 Rendering/UI Contract:** canonical Hero, table/status/pagination, Full Workspace Modal, and no page-local inline handlers.
- **L7 End-to-End Smoke:** real Flask/session/layout TLS Governance smoke with external infrastructure isolated.

Kubernetes/provider semantics remain worker/integration concerns; deterministic E2E smoke does not require a live Kubernetes cluster.


## TLS worker collection safety (#1325)

TLS Secret and Ingress inventory enumeration uses complete, bounded Kubernetes
LIST continuation pages (100 objects per page, 10-second per-request timeout,
100-page cap). A malformed page, repeated continuation token, or exhausted page
budget is a collection failure, never a successfully collected empty snapshot.
Secret failure preserves the previous committed certificate inventory.
Ingress failure is recorded independently as unavailable coverage mapping.

Only `tls.crt` is decoded for certificate metadata. The worker scrubs `data`
and `string_data` on every returned Secret object, including unrelated Secret
types, in a `finally` block before fetching the next page. Raw Secret objects
are not retained in normalized results or audit/job metadata. The provider
still transmits Secret payloads for LIST; metadata-only discovery requires a
separate feasibility and permission review.


## Immutable Kubernetes Secret object UID evidence (HV-05, #2589)

The existing TLS Governance collector now normalizes `metadata.uid` from
Kubernetes TLS Secret objects alongside the committed public `tls.crt`
fingerprint. The identifier is kept **only as source-owned internal state**
(`TLSCertificateInventory.secret_uid`) and is not exposed in the normal
Secrets & PKI correlation UI, exports, task summaries, logs or audit.

Migration `20261022_tls_object_uid` is nullable, with **no name-based
backfill**: historical rows remain `NULL` until the next successful TLS
collection. Missing/invalid/noncanonical UIDs remain unknown, and a
recreated Secret with the same namespace/name is a **new** object identity.
Ordinary certificate collection and Kubernetes TLS Governance availability
must not become unavailable simply because a UID was omitted.

This does NOT read `tls.key`, deploy a controller, attest source ownership,
or prove Vault synchronization. The existing bounded LIST and per-page
Secret payload scrub controls remain unchanged. The follow-up
`secrets_pki/certificate_delivery_read_model.py` counts only
source-qualified matching public certificates with a canonical UID;
controller readback and endpoint serving remain separate proof layers.

Requires Developer Check, reviewed Alembic PostgreSQL upgrade, new source
collection, old/new Secret recreation test, role-negative/browser Visual
QA and human DevContainer/staging UAT before acceptance.


## Controller ownerReference candidate evidence (HV-05, #2589)

TLS Governance now additionally extracts **only** a bounded Kubernetes
`metadata.ownerReferences` controller UID for supported `ExternalSecret`
(`external-secrets.io`) and `Certificate` (`cert-manager.io`) objects.
The source-owned committed `controller_owner_refs` column contains at most
one accepted {kind, api_group, immutable UID} record; resource names,
annotations, provider paths and arbitrary labels are never stored by this
contract. Unsupported ownership kinds yield no supported candidate, not a
negative claim about controllers. Legacy/unqualified/malformed observations
remain NULL/unknown and do not fail normal TLS inventory or imply no syncing.

**Warning:** `ownerReferences` is *Kubernetes ownership metadata*. It
does not attest a controller reconciled this Secret, used Vault as its
SecretStore/issuer, adopted its `tls.crt` bytes, or served them at an
endpoint. In particular, some controller creation policies do not populate
ownerReferences. The optional evidence is distinct from controller-specific
status and readback and must not be reported as Verified Delivery.

Alembic revision `20261022_tls_controller_owner` is nullable and intentionally
does not backfill old snapshots using names or annotations. Re-run the
existing bounded TLS collection after migration. Preserve TLS Secret
payload-scrubbing and `tls.crt`-only behavior; no extra Kubernetes API
discovery or mutation is introduced. Tests:
`tests/kubernetes/governance/test_tls_controller_owner_evidence.py`.

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
