# Kubernetes TLS Certificate Governance Styling Audit — July 2026

## Decision

TLS Certificate Governance adopts the Governance Resource Registry pattern and the existing Full Workspace Modal. No page-specific visual component is introduced.

## Correctness fixes

- Critical Window is no longer labelled Expired.
- Expiry is evaluated against the exact certificate timestamp instead of floored integer days.
- the default 30/7-day validity thresholds are explicit global configuration;
- current SAN/Common Name identities are evaluated against declared Ingress TLS hosts;
- Secret collection and Ingress mapping failures are represented separately;
- UI actions use Secret Operations permissions rather than legacy Governance mutation keys.

## Presentation changes

- replaced the oversized combined summary surface with Snapshot Context and Resource Posture;
- replaced the legacy table with grouped certificate, scope, validity, host-coverage, and Ingress-usage columns;
- replaced inline expansion with the shared Full Workspace Modal;
- added a Host Coverage Matrix and collection evidence;
- corrected filter event ownership and canonical HTMX pagination;
- retained direct detail routes as fallback and deep links.

## ConfigMap and Secret Management refinements included

- workflow destination actions are compact and naturally sized rather than large solid Violet blocks;
- workflow catalog rows remain flat instead of nesting action cards;
- shared Form Action Bar uses one rounded bordered surface rather than a full-width rectangular strip;
- Bulk TLS Rotation guidance uses an expandable Operational Point Flow, closed by default.

## Security boundary

Only `tls.crt` is deliberately accessed and decoded. The collector does not access or persist `tls.key`. Kubernetes Secret objects may still arrive transiently in the client response; this boundary is documented without claiming that the process never receives Secret objects.
