# Inventory Capability

`app/inventory/` is the capability boundary for committed infrastructure
inventory. Every asset family owns an explicit domain package.

```text
app/inventory/
├── kubernetes/
└── object_storage/
```

## Rules

- Kubernetes collection/read behavior lives only in `app.inventory.kubernetes`.
- Object Storage collection/read behavior lives only in
  `app.inventory.object_storage`.
- The capability root must not accumulate domain-specific routes, collectors, or
  persistence modules.
- Public endpoint names may remain stable, but imports/tasks must reference the
  canonical domain package directly.
- Namespace changes are direct cutovers. Do not create compatibility imports,
  forwarding packages, or alias modules for retired paths.
- Inventory owns committed current state. Time-series behavior belongs to the
  Analytics capability.
