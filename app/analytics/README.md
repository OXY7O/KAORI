# Analytics Capability

`app/analytics/` is the cross-domain Analytics web-capability boundary. It owns only category-level route composition and must not become a second home for asset-domain analytics implementation.

## Canonical ownership

```text
app/analytics/
└── routes.py                              # cross-domain URL/category composition only

app/common/analytics/                     # genuinely domain-neutral analytics helpers
├── coercion.py
└── params.py

app/kubernetes/analytics/                 # Kubernetes Analytics domain

app/storage/object_storage/analytics/     # Object Storage Analytics domain
```

Templates mirror the owning asset domain:

```text
app/templates/kubernetes/analytics/
app/templates/storage/object_storage/analytics/
```

## Ownership rules

- Asset-specific analytics logic belongs to the owning asset package, never `app/analytics/`.
- `app/analytics/routes.py` may compose stable category URLs/endpoints, but business/query/materialization logic must remain in the owning domain.
- Cross-domain helpers belong in `app/common/analytics/` only after their semantics and dependencies are genuinely provider- and asset-neutral.
- Provider query syntax and runtime clients stay behind Integration adapters; analytics consumes canonical Metrics Source contracts.
- Do not add compatibility packages or retired paths such as `app/analytics/kubernetes` or `app/analytics/object_storage`.

## Domain test ownership

Functional tests mirror the domain tree:

```text
tests/kubernetes/analytics/
tests/storage/object_storage/analytics/
```

Purpose-specific tests mirror the same domain underneath `tests/unit/`, `tests/integration/`, `tests/security/`, `tests/rendering/`, and `tests/e2e/`.
