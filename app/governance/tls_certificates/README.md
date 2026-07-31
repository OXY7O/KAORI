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

Legacy Governance mutation keys remain compatibility registry entries only and must not be used by new UI.
