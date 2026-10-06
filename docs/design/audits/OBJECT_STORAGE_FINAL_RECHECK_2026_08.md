# Object Storage Final Recheck — 2026-08

## Scope

Reviewed Object Storage Inventory (Overview, Systems, Buckets & Containers), Object Storage Analytics setup dependency, route/template ownership, HTMX behavior, snapshot semantics, provider boundaries, and KAORI inventory visual standards.

## Findings and corrections

1. **Setup state:** Object Storage Inventory previously rendered normal empty-state workspaces when no Storage integration had created an `ObjectStorageSystem`. The three inventory surfaces now render a setup-blocked Hero plus onboarding banner and hide committed-evidence surfaces.
2. **Snapshot consistency:** Systems and Buckets & Containers were missing the canonical `Inventory Data Snapshot`. Both now use the same shared snapshot renderer as Overview.
3. **Semantic zero evidence:** blocked Hero metadata no longer presents `0 Systems`, `0 Assets`, or similar values as if they were committed inventory results.
4. **HTMX fail-closed behavior:** direct partial/table requests while setup-blocked resolve to the setup banner rather than an empty table fragment.
5. **Ownership:** Object Storage Analytics Stage 1 now routes registration remediation directly to Integrations → Storage. Inventory remains read-only committed evidence and does not own provider registration.
6. **Collection Pending remains distinct:** a registered Object Storage system without a committed snapshot remains an inventory/freshness condition rather than being treated as setup-blocked.

## Final boundary

`Storage Integration → ObjectStorageSystem → Inventory Sync → Committed Inventory → Analytics Dependencies` remains the canonical flow. Inventory read-side code contains no MinIO client/provider API fallback.

## Follow-up — Hero geometry, RBAC, and Welcome discoverability

A browser review exposed a blocked-state Hero regression: the shared Object Storage blocker owned the canonical context panel, but its callers did not place it inside `page_hero.aside_classes()`. On `xl` layouts the blocker therefore occupied an implicit narrow grid column and wrapped text character-by-character. Overview, Systems, and Buckets & Containers now place the blocker inside the canonical five-column Hero aside; the blocker itself continues to own exactly one context panel.

Object Storage authorization is now separated from the Kubernetes domains:

```text
inventory.view                 → Kubernetes Inventory
object_storage_inventory.view  → Object Storage Inventory
analytics.view                 → Kubernetes Analytics
object_storage_analytics.view  → Object Storage Analytics
```

The RBAC split migration copies every existing role assignment from the legacy broad permission to the corresponding Object Storage permission. This preserves existing system/custom-role access at deployment time while allowing future custom roles to grant Kubernetes and Object Storage visibility independently. `storage.sync` now depends on `object_storage_inventory.view` plus `jobs.execute`.

Welcome exposes Object Storage Inventory and Object Storage Analytics as independent `Understand / Visibility & Operational Insight` workspaces with `Storage` scope. Sidebar visibility follows the same dedicated permission boundaries; Kubernetes permissions no longer reveal Object Storage menus and Object Storage permissions no longer reveal Kubernetes menus.
