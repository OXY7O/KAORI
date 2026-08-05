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
