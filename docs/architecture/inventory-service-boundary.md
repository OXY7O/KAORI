# Inventory Domain Boundary

KAORI no longer exposes `app.inventory.service` as an aggregate import facade.
Every caller imports the module that owns the use case:

- `app.inventory.overview` for landing-page aggregation and cluster lookup;
- `app.inventory.resources.<resource>` for list, filter, and detail payloads;
- `app.inventory.synchronization` for inventory synchronization;
- `app.inventory.persistence` for database replacement writes;
- `app.inventory.formatting` for inventory-specific formatting.

Routes may import several owner modules explicitly. This is intentional: import
paths now document ownership and prevent a broad compatibility surface from
silently growing as Inventory features expand.
