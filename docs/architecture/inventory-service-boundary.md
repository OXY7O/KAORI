# Inventory Domain Boundary

KAORI no longer exposes `app.kubernetes.inventory.service` as an aggregate import facade.
Every caller imports the module that owns the use case:

- `app.kubernetes.inventory.overview` for landing-page aggregation and cluster lookup;
- `app.kubernetes.inventory.resources.<resource>` for list, filter, and detail payloads;
- `app.kubernetes.inventory.synchronization` for inventory synchronization;
- `app.kubernetes.inventory.persistence` for database replacement writes;
- `app.kubernetes.inventory.formatting` for inventory-specific formatting.

Routes may import several owner modules explicitly. This is intentional: import
paths now document ownership and prevent a broad compatibility surface from
silently growing as Inventory features expand.
