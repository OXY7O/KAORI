# Kubernetes TLS Certificate Governance

## Purpose

TLS Certificate Governance is a read-oriented registry for certificate validity, declared-host coverage, Ingress relationships, collection evidence, and controlled rotation handoff.

## Canonical structure

```text
Compact Hero
TLS Collection Snapshot
Certificate Validity Posture
Compact Certificate Registry
Detail Style 2 — Full Workspace Modal
```

This is the first canonical **Governance Resource Registry** implementation.

## Evidence authorities

| Evidence | Authority |
|---|---|
| TLS Secret certificate metadata | Kubernetes TLS Secret collection |
| Declared hosts and Ingress consumers | Kubernetes Ingress collection |
| Validity state | KAORI global validity policy |
| Rotation mutation | Kubernetes Secret Operations |
| Sync dispatch and outcome | KAORI Jobs and Activity Audit |

A missing Ingress consumer is not equivalent to a successful collection with zero consumers. Secret collection and Ingress mapping maintain separate evidence states.

## Global validity policy

Defaults:

```text
Renewal Window  30 days
Critical Window 7 days
```

The values are configured with:

```text
TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS
TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS
```

Expiry uses the exact `not_after` timestamp. A certificate with less than 24 hours remaining is still valid and belongs to the Critical Window; it is not Expired until `not_after <= now`.

Validity labels:

```text
Valid
Renewal Window
Critical Window
Expired
Invalid
Unknown
```

## Declared-host coverage

Coverage compares current certificate SAN/Common Name identities with declared Ingress TLS hosts from the same collected scope.

```text
Fully Covered
Partial
Uncovered
No Declared Hosts
Not Reported
```

Coverage is declaration evidence, not live endpoint reachability. Host values remain Technical Values. Opening a declared host is an explicit action and never proves route availability.

## Compact registry table

```text
Certificate
Scope
Validity
Host Coverage
Ingress Usage
Details
```

The table directly opens the shared Full Workspace Modal. It does not render an intermediate expanded row. The dedicated detail route remains a direct-link and no-JavaScript fallback.

## Full Workspace Modal

Canonical content:

```text
Certificate Summary
Certificate Identity
Issuer & Validity
Technical Identifiers
Host Coverage
Ingress Consumers
Collection Evidence
Host Coverage Matrix
Certificate Identities
Governance Snapshot Boundary
Rotation Handoff
```

The modal uses permission-aware rotation actions. Governance never owns the mutation form.

## Collection evidence

Per cluster:

```text
Secret Collection
Ingress Mapping
```

Supported states:

```text
Collected
Permission Unavailable
API Unavailable
Collection Failed
Not Reported
```

The Snapshot Context Bar aggregates missing or failed evidence for the active scope.

## Permission ownership

Governance owns:

```text
tls_certificates.view
tls_certificates.sync
```

Secret Operations owns:

```text
kubernetes_secrets.rotate_tls
kubernetes_secrets.bulk_rotate_tls
```

Legacy `tls_certificates.update` and `tls_certificates.bulk_update` keys remain registry compatibility aliases only. New UI and role design must not use them as mutation authorities.

## Data-minimization contract

The Kubernetes API response is processed transiently by the collector. KAORI may read and decode only `tls.crt` for certificate metadata extraction. It must not access, decode, log, persist, notify, or audit `tls.key` or unrelated Secret values.

## Pagination and filtering

- filter events are scoped to the filter form;
- the Rows selector refreshes `#tls-certificates-inventory-scope` using `outerHTML`;
- page size defaults to 5 and offers 5/10/25/50;
- Previous, numeric pages, and Next preserve all active filters and use the same HTMX target and loading indicator.
