# Kubernetes Storage and Configuration Inventory Styling Audit — July 2026

## Decisions applied

- Applied the Inventory Resource Page pattern to Storage and Configuration.
- Replaced wide legacy tables with grouped compact evidence columns.
- Removed implicit StorageClass vendor, reclaim-policy, access-mode, Secret-type, and immutable scoring.
- Added key-index collection without payload-size processing.
- Added committed-generation collection evidence for ConfigMap and Secret capabilities.
- Added permission-aware operations handoff for ConfigMap and Secret management.
- Standardized every Inventory expanded row on the shared View Details workspace.

## Reusable outcomes

- Expanded Inventory Detail component contract.
- Technical Metadata Collection `keys` and `records` modes.
- Storage relationship collections for claims and mounted Pods.
- Configuration current Pod reference collection.
