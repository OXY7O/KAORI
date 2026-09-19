# Kubernetes Ingress Inventory Standard

Ingress Inventory is the canonical KAORI view for committed Kubernetes Ingress declarations and controller publication evidence.

## Scope

The page reports:

- Ingress identity and namespace;
- explicit `ingressClassName` or legacy provider annotation source;
- explicit host declarations and hostless rules;
- controller-published addresses;
- rule paths and default backends;
- Service and resource backend declarations;
- TLS Secret references;
- committed Service and Secret reference resolution.

It does not prove public exposure, DNS resolution, reachability, traffic health, certificate validity, certificate expiry, private-key matching, or hostname coverage.

## Canonical page boundary

```text
#ingresses-page-workspace
├── Hero
├── Inventory Data Snapshot
├── Ingress Publication Posture
└── Ingress table card
    └── #ingresses-table-content
```

Cluster, namespace, class, TLS, and search filters refresh the complete workspace. Pagination and page-size changes refresh only the table content.

## Class semantics

An absent class is displayed as **Not Explicitly Set**. KAORI does not infer that a default `IngressClass` exists or will accept the object.

Provider compatibility with the historical `kubernetes.io/ingress.class` annotation is normalized in the collector. Downstream code receives one canonical class value and an explicit evidence source.

## Host semantics

A rule without `host` applies to **All Hosts**. It is valid routing configuration and is not treated as missing evidence.

Explicit hosts are preserved independently from hostless rules. Wildcard values remain factual declarations and are not expanded or tested.

## Publication states

- **Published** — one or more controller addresses are reported;
- **Address Pending** — controller load-balancer status is represented but contains no address;
- **Not Reported** — controller publication evidence is unavailable.

An address is controller status evidence, not proof of public reachability.

## Backend semantics

Ingress v1 Service backends, resource backends, and supported provider v1beta1 Service backends are normalized to one route contract.

Service references are resolved against the same committed Service Inventory generation:

- **Resolved**;
- **Missing**;
- **Not Reported** when Service collection evidence is unavailable.

Resource backends are preserved as **Resource Backend** declarations and are not falsely evaluated as missing Services.

## TLS semantics

TLS Secret references are resolved against committed Secret Inventory evidence:

- **Resolved**;
- **Missing**;
- **Not Reported** when Secret collection evidence is unavailable.

A resolved reference confirms only Secret existence in the committed namespace snapshot.

## Canonical persistence

`IngressInventory.details` owns hosts, controller addresses, evidence flags, TLS entries, class source, and metadata. `backend_paths` owns canonical route relationships. Duplicate compact `host` and `address` columns are not permitted.

## Export

XLSX and CSV export use only canonical JSON and route evidence. Publication counts remain blank when publication evidence was not reported.
