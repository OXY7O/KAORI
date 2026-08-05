# Kubernetes Network Inventory Pattern

Service Inventory and Ingress Inventory are the canonical network-resource implementations of the Inventory Resource Page Pattern.

## Page composition

```text
Canonical Hero
Compact Inventory Data Snapshot
Network Resource Posture
Compact Inventory Table
Full Workspace Modal
```

## Service Inventory

The compact table groups:

```text
Service | Scope | Access Model | Port Mapping | Backend Registration | Details
```

Service type and traffic policy are factual configuration. NodePort or LoadBalancer does not prove public reachability. Backend registration is derived from EndpointSlice evidence first, with Endpoints as a compatibility fallback.

Backend states are:

- Registered
- Partial
- Not Ready
- No Registered Backends
- Not Reported
- External Destination
- Manually Managed

## Ingress Inventory

The compact table groups:

```text
Ingress | Scope | Publication | TLS References | Routing | Details
```

TLS references remain factual. A Secret reference does not validate certificate existence, expiry, hostname coverage, or live termination. No TLS reference remains neutral until an explicit governance policy evaluates it.

Backend Service references are resolved only against the current committed Service Inventory and display Resolved, Missing, or Not Reported. Resource backends remain factual declarations and are not evaluated as missing Services.

Controller publication is represented as Published, Address Pending, or Not Reported. Hostless rules are represented as All Hosts rather than missing configuration. TLS Secret references are resolved only when committed Secret collection evidence is available.

## Detail density

Network details use Adaptive Detail Stacks and natural-height cards. Tables use the canonical table owner. Labels, annotations, selectors, declared hosts, addresses, and TLS references use shared metadata/value components.

## Data boundary

Inventory reports declared configuration and committed registration evidence. It does not prove public exposure, live reachability, traffic health, certificate validity, or certificate expiry.

## Service collection resilience

Service backend collection records a committed evidence state. EndpointSlice permission/API compatibility failures may use Endpoints fallback. Unexpected API failures are not hidden. Selectorless Services distinguish reported manual registration from missing endpoint evidence, and exports leave endpoint-derived counts blank when evidence was not reported.

## Ingress collection resilience

Ingress list permission/API compatibility failures are recorded as committed collection evidence. Unexpected API failures are not hidden. Supported provider v1beta1 payloads are normalized at the collector boundary; downstream services use only the canonical route contract.
