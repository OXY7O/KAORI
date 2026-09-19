# Expanded Inventory Detail

Inline expanded detail remains available as **Detail Style 1** for short row-owned evidence.

Complex Kubernetes Inventory resources no longer use this pattern. Node through Configuration Inventory use **Detail Style 2 — Full Workspace Modal**, owned by:

```text
components/resource_detail_modal.html
components/details/_detail_content.html
app/static/js/detail_rows.js
```

See:

- `docs/design/components/DETAIL_STYLES.md`
- `docs/design/components/RESOURCE_DETAIL_MODAL.md`
