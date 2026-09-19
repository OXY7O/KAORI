# Kubernetes Service Inventory Alignment Audit — August 2026

## Scope

The audit covered Service collection, EndpointSlice/Endpoints fallback, committed evidence, page scope refresh, Service semantics, detail evidence, selected-Pod relationships, and XLSX/CSV payloads.

## Corrected issues

- Filter and Rows changes now refresh Hero, Snapshot Context, posture, filters, and table together.
- Service objects without namespace or name are rejected before persistence.
- EndpointSlice fallback only handles permission/API compatibility failures; HTTP 500 and other unexpected errors remain visible.
- Backend collection evidence is committed to `ClusterInventory.collection_evidence`.
- Duplicate EndpointSlice addresses and ports are deduplicated.
- EndpointSlice serving and terminating conditions are retained.
- Duplicate `ports` and `external_ip` presentation columns were removed; complete port and external-address evidence remains in canonical JSON details.
- Selectorless Services no longer mask missing endpoint evidence.
- Empty manual endpoint registration is an attention state.
- Unknown Service type can be filtered correctly.
- Age was removed from the compact table.
- Detail values distinguish Not Reported, Not Configured, and Not Applicable.
- Service port tables now include captions and scoped headers.
- Selected-Pod preview uses canonical Pod lifecycle/readiness semantics.
- Service export now reads the real `load_balancer_ingress` collector field instead of unused legacy keys.
- Export includes access model, backend state, endpoint counts, complete port mappings, and traffic policy evidence.

## Boundary

Service Inventory remains committed-snapshot evidence. NodePort and LoadBalancer do not prove public exposure. Registered endpoints do not prove application reachability or traffic health.
