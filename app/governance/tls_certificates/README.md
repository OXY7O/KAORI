# TLS Certificate Governance

## Purpose

This module owns certificate discovery, inventory presentation, expiry and risk posture, Subject Alternative Name coverage, issuer metadata, and Ingress relationships.

## Boundary

Governance is read-oriented. It identifies certificate posture and directs users to a controlled operation when a certificate must be rotated. Kubernetes Secret mutation workflows are owned by `app/kubernetes_operations/secrets`.

Governance may:

- collect TLS Secret certificate metadata;
- calculate expiry and risk status;
- present SAN and Ingress relationships;
- synchronize the certificate inventory snapshot;
- link to a Secret Management operation.

Governance must not:

- persist uploaded private keys;
- own create, update, or rotation forms;
- patch Kubernetes Secrets directly from its presentation routes;
- grant mutation access through a read permission.

## Shared validation

X.509 parsing and certificate/private-key matching live in `app/kubernetes/secrets/tls.py`. The compatibility module `validator.py` remains temporarily for existing imports.

## UI boundary

The Kubernetes TLS Secret governance UI follows the KAORI violet design standard across overview, detail, and bulk update pages. Structural surfaces and actions use KAORI brand tokens; certificate validity and expiry states remain semantic. Gradients and decorative blue/cyan treatments are not used. Governance remains read-oriented posture and relationship context, while certificate/private-key mutation is executed through the controlled Kubernetes Operations TLS rotation workflow.

## KAORI presentation and workflow contract

- TLS certificate inventory, detail, and rotation entry points use neutral structural surfaces with semantic status colors reserved for healthy, warning, critical, expired, and invalid states.
- Inventory actions use the shared expandable-row behavior in `components/details/_expandable_row.html` and `app/static/js/detail_rows.js`; TLS tables do not maintain a separate inline toggle implementation.
- Page-size selectors use the global `data-kaori-auto-submit` behavior. Sync progress is owned by `app/static/js/tls_certificate_management.js` rather than inline template JavaScript.
- TLS inventory and certificate-detail heroes use the canonical `page_hero.context_rows()` panel with exactly three horizontal label/value rows. Sync, bulk-update, back, and update actions live in content toolbars rather than inside the hero panel.
- Governance remains read-oriented. Bulk and single TLS Secret mutation actions link to Secret Management, and obsolete Governance-owned mutation templates are not retained.
- TLS Governance does not use Flask flash messages; missing-record and cluster-setup feedback use the KAORI notification and Activity Log pipeline.
