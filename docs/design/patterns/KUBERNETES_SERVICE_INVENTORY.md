# Kubernetes Service Inventory Standard

Service Inventory is the canonical KAORI view for committed Kubernetes Service identity, access configuration, and backend-registration evidence.

## Page composition

```text
Canonical Hero
Compact Inventory Data Snapshot
Service Network Posture
Compact Service Table
Full Workspace Detail
```

Filter changes replace the complete `services-page-workspace`, including Hero, Snapshot Context, summary posture, filter options, and table. Numeric pagination only replaces table content.

## Compact table

```text
Service | Scope | Access Model | Port Mapping | Backend Registration | Details
```

Age remains in detail and is not displayed in the compact table.

## Effective Service types

- ClusterIP
- Headless
- NodePort
- LoadBalancer
- ExternalName
- Unknown

Headless is derived from `type=ClusterIP` and `clusterIP=None`.

## Access semantics

Service type and traffic policy are factual configuration:

- ClusterIP indicates cluster-internal identity.
- Headless indicates direct endpoint discovery without a virtual Cluster IP.
- NodePort indicates node-port declarations, not proven public exposure.
- LoadBalancer indicates load-balancer publication intent, not proven external reachability.
- ExternalName indicates an external DNS alias, not destination health.

## Backend-registration evidence

EndpointSlice is preferred. Endpoints is used only as a compatibility fallback when EndpointSlice collection is unavailable because of API availability or permission limitations.

Unexpected API failures are not hidden by fallback. They fail the inventory generation so operators do not receive a falsely complete snapshot.

Canonical backend states:

- Registered
- Partial
- Not Ready
- No Registered Backends
- Not Reported
- External Destination
- Manually Managed

A selectorless Service does not hide missing Endpoint evidence. When evidence is reported but no manual endpoint exists, the state remains Manually Managed with an attention signal.

## Evidence states

The UI and export distinguish:

- `Not Reported`: collector evidence was unavailable.
- `Not Configured`: authoritative Service specification was collected and the field is absent.
- `Not Applicable`: the concept does not apply, such as Pod selection for ExternalName or selectorless Services.
- `0`: evidence was collected and the factual count is zero.

## Collector contract

The committed generation stores:

- Service identity and metadata;
- full port definitions;
- Cluster IP and IP-family evidence;
- declared external IPs;
- load-balancer ingress addresses;
- traffic policies;
- Service selectors;
- EndpointSlice or Endpoints source;
- ready and not-ready backend addresses;
- EndpointSlice serving and terminating conditions;
- backend collection evidence in `ClusterInventory.collection_evidence`.

Service port and external-address evidence is stored only in canonical `ServiceInventory.details`. Duplicate presentation columns are not retained in the relational model.

## Detail contract

The detail workspace contains:

- Service Identity;
- Network Identity;
- Backend Registration;
- Traffic Configuration;
- Port Mappings;
- Endpoint Addresses;
- Selected Pods or Pod Selection Not Applicable;
- Labels and annotations;
- Operational Context.

The detail reports committed configuration and registration evidence. It does not prove live application reachability, traffic health, public exposure, or load-balancer health.

## Export contract

Service XLSX and CSV use the same canonical payload and include:

- effective Service type;
- access model;
- backend-registration state;
- Cluster IP and external addresses;
- complete port mappings;
- selector evidence;
- Endpoint source;
- ready and not-ready backend counts;
- load-balancer addresses;
- traffic policies;
- publish-not-ready configuration.

Missing endpoint-derived counts remain blank when collection evidence was not reported.
