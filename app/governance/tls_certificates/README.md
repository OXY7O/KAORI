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
