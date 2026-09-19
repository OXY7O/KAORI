# Kubernetes Ingress Inventory Alignment Audit — August 2026

## Result

Ingress Inventory was moved to the canonical KAORI workspace and evidence contract.

## Corrected defects

- removed the legacy `_inventory_scope.html` wrapper;
- made scope-changing filters refresh Hero, Snapshot Context, posture, filters, and table together;
- removed duplicate `host` and `address` database columns;
- widened `ingress_class` to support Kubernetes DNS-subdomain-length class names;
- recorded explicit Ingress collection evidence;
- prevented expected RBAC/API compatibility failures from appearing as successful empty inventory;
- preserved unexpected Kubernetes API errors instead of hiding them;
- distinguished Published, Address Pending, and Not Reported publication states;
- represented hostless rules as All Hosts;
- normalized networking/v1, resource backend, and supported v1beta1 provider schemas;
- resolved Service references only when Service collection evidence was collected;
- resolved TLS Secret references only when Secret collection evidence was collected;
- removed the unsafe protocol inference and direct Open Declared Host action;
- aligned Topology and XLSX/CSV export with canonical Ingress evidence;
- added behavioral collector/export tests and a static release verifier.

## Migration

`20260805_ingress_inventory_v2` preserves historical host/address values in `details`, widens `ingress_class`, and drops duplicate presentation columns. A fresh Inventory Sync is required after deployment to establish fully canonical evidence flags for every cluster.

## Remaining runtime verification

The source audit does not replace browser validation. Verify the 14-inch layout, dark mode, HTMX focus continuity, PostgreSQL migration execution, and Kubernetes API collection in the KAORI development environment.
