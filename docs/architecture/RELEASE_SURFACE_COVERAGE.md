# KAORI Release Surface Coverage v1

Status: **Locked release-coverage contract**

This registry answers one release question: **is every operator-visible menu, nested web domain, and non-navigation system surface explicitly owned by a release verifier or test boundary?**

The current baseline contains **59 navigation links** across the authenticated application shell and **25 registered blueprints**. A new menu link, menu template, or registered Blueprint must be added to the canonical registry in the same change or the general release audit fails closed.

## Navigation and Surface Matrix

| Surface | State | Navigation ownership | Release evidence |
|---|---|---|---|
| Welcome | LOCKED | Main → Welcome | `verify_welcome_final_lock.py` |
| Kubernetes Dashboard | LOCKED | Main → Dashboards → Kubernetes | `verify_operational_dashboard_standard.py` |
| Kubernetes Inventory | LOCKED | Kubernetes → Inventory | `verify_inventory_final_lock.py` |
| Object Storage Inventory | LOCKED | Storage → Object Storage | `verify_object_storage_inventory_final_lock.py` |
| Kubernetes Operations | LOCKED | Kubernetes → Operations | `verify_kubernetes_operations_final_lock.py` |
| Kubernetes Governance | LOCKED | Kubernetes → Governance | `verify_governance_final_lock.py` |
| Analytics | LOCKED | Insights & Reporting → Kubernetes Analytics + Object Storage Analytics | `verify_analytics_final_lock.py` + `verify_object_storage_analytics.py` |
| Intelligence | BASELINE LOCKED | Insights & Reporting → Intelligence | `verify_intelligence_baseline_lock.py` |
| Reports | LOCKED | Insights & Reporting → Reports | Reports generation/job/storage/runtime verifiers + Reports contracts |
| Integrations | LOCKED | Platform Operations → Integrations | `verify_integrations_final_lock.py` |
| Platform Operations | LOCKED | Platform Operations | `verify_platform_operations_final_lock.py` |
| Access | LOCKED | Administration → Access | `verify_access_final_lock.py` |
| Settings | LOCKED | Administration → Settings | `verify_settings_final_lock.py` |
| Authentication | LOCKED | Non-navigation public/auth shell | `verify_authentication_surface_final_lock.py` |
| Notification Center | LOCKED | Application shell; Activity Audit linked from Access | `verify_notification_center_final_lock.py` |
| Runtime Health | SYSTEM LOCKED | Non-navigation `/health/live` and `/health/ready` | release endpoint registry integration test |

## Nested Cluster Management Ownership

**Cluster Management is intentionally not a separate sidebar menu.** The canonical list/lifecycle workspace remains the Kubernetes provider workspace under **Integrations → Orchestration → Kubernetes**. `cluster.*` Add/Edit/Delete/Sync routes remain active nested operations, and the Kubernetes provider registration must keep `cluster.*` associated with the Orchestration domain through navigation metadata.

The retired standalone Cluster Management listing chain must not return:

- `app/templates/cluster/index.html`
- standalone cluster table/pagination/status/inventory/delete-modal partials used only by that retired listing
- `cluster.list_clusters`

The active registration/edit surfaces remain:

- `app/templates/cluster/add.html`
- `app/templates/cluster/edit.html`
- shared form/connection-test/page-header partials

## General Release Commands

Fast ownership and locked-surface review:

```bash
python scripts/verify_final_release.py
```

Full release gate with static quality, test suite, and frontend build:

```bash
python scripts/verify_final_release.py --all
```

Include live runtime checks when release services/workers are running:

```bash
python scripts/verify_final_release.py --all --runtime
```

The general runner intentionally keeps successful output short:

```text
PASS — KAORI Inventory
PASS — KAORI Analytics
PASS — KAORI Reports
```

A failed child verifier prints its complete captured diagnostics after a concise `FAIL — KAORI <Area>` header. This preserves the agreed rule: **PASS is short; FAIL is detailed.**

## Change Control

When adding or moving a menu/domain:

1. Update `scripts/release_surface_registry.py` with ownership, endpoints, lock state, verifier, and release evidence.
2. Update this matrix.
3. Add/update the domain verifier and contract/runtime evidence.
4. Run `python scripts/verify_release_surface_coverage.py`.
5. Run `python scripts/verify_final_release.py --all` before release.

Do not silence a new endpoint by increasing a baseline or by classifying an active surface as hidden without an explicit ownership decision.

## Storage Integration Expansion

`Integrations → Storage → Object Storage` owns the MinIO provider workspace. MinIO remains registered under the Integrations release surface.

The provider-neutral inventory workspace is a separate authenticated release surface under **Storage → Object Storage** with **Overview**, **Systems**, and **Buckets & Containers**. It reads committed database snapshots only; provider configuration, validation, and runtime health remain Integration-owned. The `object_storage_inventory_bp` Blueprint and its three navigation endpoints are therefore release-owned independently from the MinIO provider workspace.


## Object Storage Analytics Expansion

`Insights & Reporting → Object Storage Analytics` is owned by the existing `analytics_bp` release surface. The first locked baseline adds **Overview**, **Capacity & Usage**, **Performance**, **Forecast**, **Top Consumers**, and **Alerts & Anomalies** without creating a provider-specific Blueprint.

The evidence contract is explicit: committed Object Storage Inventory owns current configuration/state evidence; the resolved provider-neutral metrics source owns operational time-series and KAORI metric-derived signal evidence; provider alert records use Alertmanager as the lifecycle-rich preferred source with scoped Prometheus `ALERTS` fallback. A registered system is not Analytics-ready until at least one committed inventory observation exists, so registration and Inventory Sync remain an explicit prerequisite before metric analysis. The two alert evidence paths remain independent so one source failure does not suppress usable evidence from the other. Forecast is worker-materialized through `object_storage.forecast.materialize` on the dedicated forecasting queue and persists Object Storage-specific 7d/30d/90d history artifacts rather than executing long-range queries inside the interactive page request.
