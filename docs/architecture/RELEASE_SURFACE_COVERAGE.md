# KAORI Release Surface Coverage v1

Status: **Locked release-coverage contract**

This registry answers one release question: **is every operator-visible menu, nested web domain, and non-navigation system surface explicitly owned by a release verifier or test boundary?**

The current baseline contains **76 navigation links** across the authenticated application shell and **36 registered blueprints**. A new menu link, workspace capability, menu template, or registered Blueprint must be added to the canonical registry in the same change or the general release audit fails closed.

Each declared release-evidence directory must contain at least one executable `test_*.py` module, not only a placeholder directory or `__init__.py`. `scripts/verify_release_surface_coverage.py` enforces this rule using the existing release-surface registry. The **Foundation & Governance → Release Surface Coverage** verifier first validates release ownership and stores the successful source-registration report. Once the existing named verifiers complete successfully, **Domain & Capability Contracts → Registered capability ownership** displays the already-validated registry as a compact, aligned operator table: one row per release surface with lock state, registered contract-module count, and static verifier **count** (or `contracts only`). A total line distinguishes registered surfaces, the sum of per-surface contract-module **registrations** (not necessarily globally unique modules), and contract-only surfaces. This keeps Artifact Registry, Object Storage Inventory, Tenant, provider integrations, and other domains visible without invoking the verifier twice or increasing its check count. The complete source-validated rows, including every exact static-verifier filename or `none (contract tests only)`, remain in the original Release Surface Coverage raw log and (after completed static execution) in `verification-report.md`. A malformed or missing captured registry report still fails closed; the compact terminal format never replaces source validation. The output is a **source-registration inventory**, not a per-capability test execution report. Its placement within Domain & Capability Contracts does not mean every surface has a standalone static verifier or that those contract modules ran as part of the static verifier group. A missing or malformed captured registry report fails closed. Only the actual named verifier, Contract & Migration Safety, Functional, Security, and Runtime & DAST jobs can establish their respective PASS/FAIL states. Counts and `REGISTERED` prove that executable test modules are registered; **they do not prove behavioral correctness or UAT PASS**. Functional execution remains under the existing Contract & Migration Safety / Functional / Security / Runtime & DAST admission lanes.

## Navigation and Surface Matrix

| Surface | State | Navigation ownership | Release evidence |
|---|---|---|---|
| Welcome | LOCKED | Main → Welcome | `verify_welcome_final_lock.py` |
| Operational Dashboards | LOCKED | Main → Dashboards → Kubernetes + Object Storage | `verify_operational_dashboard_standard.py` + Object Storage dashboard contracts |
| Kubernetes Inventory | LOCKED | Kubernetes → Inventory | `verify_inventory_final_lock.py` |
| Object Storage Inventory | LOCKED | Storage → Object Storage | `verify_object_storage_inventory_final_lock.py` |
| Artifact Registry | BASELINE LOCKED | Infrastructure → Artifact Registry | Artifact Registry contracts |
| Kubernetes Operations | LOCKED | Kubernetes → Operations → Overview, ConfigMaps, Secrets | `verify_kubernetes_operations_final_lock.py` |
| Kubernetes Governance | LOCKED | Kubernetes → Governance | `verify_governance_final_lock.py` |
| Tenant | BASELINE LOCKED | Kubernetes → Tenant | baseline + integrated Tenant UAT contracts |
| Analytics | LOCKED | Insights & Reporting → Kubernetes Analytics + Object Storage Analytics | `verify_analytics_final_lock.py` + `verify_object_storage_analytics.py` |
| Intelligence | BASELINE LOCKED | Insights & Reporting → Intelligence | `verify_intelligence_baseline_lock.py` |
| Reports | LOCKED | Insights & Reporting → Reports | Reports generation/job/storage/runtime verifiers + Reports contracts |
| Integrations | LOCKED | Platform Operations → Integrations → Orchestration, Observability, Storage, Registry, Secrets Management, Source Control | `verify_integrations_final_lock.py` and Integration contracts |
| Platform Operations | LOCKED | Platform Operations | `verify_platform_operations_final_lock.py` |
| Access | LOCKED | Administration → Access | `verify_access_final_lock.py` |
| Settings | LOCKED | Administration → Settings | `verify_settings_final_lock.py` |
| Authentication | LOCKED | Non-navigation public/auth shell | `verify_authentication_surface_final_lock.py` |
| Notification Center | LOCKED | Application shell; Activity Audit linked from Access | `verify_notification_center_final_lock.py` |
| Runtime Health | SYSTEM LOCKED | Non-navigation `/health/live` and `/health/ready` | release endpoint registry integration test |

## Nested Cluster Management Ownership

**Cluster Management is intentionally not a separate sidebar menu.** The canonical list/lifecycle workspace remains the Kubernetes provider workspace under **Integrations → Orchestration → Kubernetes**. `cluster.*` Add/Edit/Delete/Sync routes remain active nested operations, and the Kubernetes provider registration must keep `cluster.*` associated with the Orchestration domain through navigation metadata.

The retired standalone Cluster Management listing chain must not return:

- `app/templates/kubernetes/cluster/index.html`
- standalone cluster table/pagination/status/inventory/delete-modal partials used only by that retired listing
- `cluster.list_clusters`

The active registration/edit surfaces remain:

- `app/templates/kubernetes/cluster/add.html`
- `app/templates/kubernetes/cluster/edit.html`
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
2. For catalog-backed workspaces, keep the release owner aligned with the canonical `WorkspaceDefinition`; do not create a duplicate menu only to satisfy release coverage.
3. Update this matrix.
4. Add/update the domain verifier and contract/runtime evidence.
5. Run `python scripts/verify_release_surface_coverage.py`.
6. Run `python scripts/verify_final_release.py --all` before release.

Do not silence a new endpoint by increasing a baseline or by classifying an active surface as hidden without an explicit ownership decision.

### Required admission format for new or changed capabilities

The release matrix and registry are the **ownership** layer of the mandatory operator-facing evidence standard in `docs/engineering/TERMINAL_OUTPUT.md`. For any new or materially changed feature, domain, capability, provider, integration, menu, registered Blueprint or static verifier:

1. Identify its capability/domain-first owner, provider and instance boundaries; use an existing parent release surface when appropriate instead of creating an artificial top-level surface or duplicate gate.
2. Update the authoritative taxonomy/workspace, `scripts/release_surface_registry.py`, this matrix and existing navigation/Blueprint registrations **when applicable**. Declare a real owner and corresponding verifier or executable contract-test path; an integration provider remains nested under Integrations when that is its approved authority.
3. Describe the operator-facing gate **identity, specific purpose/scope, command/test selector, executed result, duration, raw evidence and first actionable failure** in the existing CI output pattern. For a newly added standalone static verifier, supply a specific purpose in the existing `scripts/quality_gate.sh` reporting mapping; do not rely on the generic fallback or infer tests ran from its registration.
4. Add or update the behavior-focused tests, including authorization/negative scenarios and provider/runtime/security checks where applicable. Report their actual executed pytest/JUnit, security, frontend and runtime/DAST evidence independently from registry ownership. Any not-run, skipped, reused or blocked work remains explicit.
5. Link the governing Issue and PR, commit SHA, real CI results and applicable staging/UAT human acceptance. Do not label a static surface lock as full feature readiness or presume DevContainer review is hosted UAT.
6. Use the existing `verify_release_surface_coverage.py`, release contracts, focused tests, Developer Check and Full Admission. Fail closed on missing ownership or evidence and extend existing tests when a new registration shape requires it; never bypass gates or invent a parallel validation/reporting framework.

For example, **Integrations → Source Control → GitHub** is owned by the existing Integrations release surface: `REGISTERED` proves navigation/Blueprint/test ownership; `Integrations Final Lock` protects shared UI/contracts; GitHub webhook security, repository synchronization, scoped authorization and real provider readiness require their own executed tests and UAT evidence, not a fabricated GitHub static-PASS line.

## Storage Integration Expansion

`Integrations → Storage → Object Storage` owns the MinIO provider workspace. MinIO remains registered under the Integrations release surface.

The provider-neutral inventory workspace is a separate authenticated release surface under **Storage → Object Storage** with **Overview**, **Systems**, and **Buckets & Containers**. It reads committed database snapshots only; provider configuration, validation, and runtime health remain Integration-owned. The `object_storage_inventory_bp` Blueprint and its three navigation endpoints are therefore release-owned independently from the MinIO provider workspace.


## Object Storage Analytics Expansion

`Insights & Reporting → Object Storage Analytics` is owned by the existing `analytics_bp` release surface. The locked workspace provides **Overview**, **Capacity & Usage**, **Performance**, **Forecast**, **Top Consumers**, and **Alerts & Anomalies**.

The evidence contract is snapshot-first: committed Object Storage Inventory owns current asset/configuration evidence; `object_storage.analytics.materialize` collects operational metrics and alert evidence in the background and commits reusable analytics snapshots; `object_storage.forecast.materialize` commits long-range system and bucket forecast artifacts. Interactive analytics and dashboard requests read those committed artifacts and never query Metrics Source or Alertmanager directly. Alertmanager remains the lifecycle-rich preferred alert source with metrics-backed alert evidence retained as the independent fallback inside the same committed analytics snapshot.

## Object Storage Dashboard Expansion

`Dashboards → Object Storage` is owned by `object_storage_dashboard_bp` under `/dashboards/object-storage`. It mirrors the Kubernetes operational-dashboard concept with **Operations Overview**, **Capacity & Demand**, **Signals & Actions**, and **Reporting** tabs, a scope selector, lazy HTMX sections, and committed-evidence freshness. The dashboard reads Object Storage Inventory plus committed Object Storage Analytics and Forecast snapshots only; no live provider, Metrics Source, or Alertmanager query is permitted on page load.


## Kubernetes Tenant Expansion

`Kubernetes → Tenant` is a distinct provider-neutral Kubernetes capability surface. Tenant is one expandable parent with five release-owned submenu destinations: **Overview**, **Tenants**, **Resource Profiles**, **Namespace Provisioning**, and **Operations**. Native Kubernetes and Capsule remain providers behind the same Tenant contract and do not become sidebar products. Operations owns task-level Content Tabs for Provisioning, Runs & Evidence, Drift & Reconcile, and Activity; no third sidebar nesting level is introduced.

The current state remains **BASELINE LOCKED** until #125 completes full staging UAT and human acceptance. #728 owns the human-UAT navigation/UI correction that recomposes the admitted Tenant domain, access/credential, capacity, managed-resource/policy, provider, audit, Intelligence, and Reports authorities into the approved five-destination Tenant IA. Native Kubernetes is mandatory for baseline acceptance. Capsule execution remains capability-conditional and must not be inferred from fixture-only evidence.


## Registry and Artifact Registry Expansion

`Integrations → Registry` owns provider connectivity, readiness, diagnostics, and instance lifecycle. Harbor remains the first Registry provider and `harbor_bp` stays release-owned by the Integrations surface.

`Artifact Registry` is a separate provider-neutral operational workspace backed by committed KAORI state. Its release-owned navigation is **Overview**, **Inventory**, **Security**, **Runtime Usage**, **Governance**, and **Analytics**. The `artifact_registry_bp` Blueprint is therefore owned by the Artifact Registry surface rather than being folded into the Harbor provider surface.

The boundary remains:

```text
Integrations → Registry → Harbor → Instance
    = provider connection / readiness / diagnostics

Artifact Registry
    = committed inventory / security / runtime correlation / governance / analytics
```

The Artifact Registry surface is **BASELINE LOCKED** while the consolidated staging candidate proceeds through staging/UAT. This preserves the existing provider-first integration taxonomy without treating Harbor as a KAORI product domain.


## Secrets Management and Source Control Admission

The existing Integrations release surface owns the two domain workspaces `integrations.secrets_management` and `integrations.source_control`. Their provider-facing blueprints remain nested under Integrations rather than separate top-level KAORI products: `vault_bp`, `secrets_pki_bp`, `security_posture_bp`, `source_control_bp`, `github_source_bp`, and `github_uat_bp`.

This release-coverage ownership records registered application routes and contract evidence only. It neither grants provider credentials nor establishes UAT/production readiness; exact-head static, functional, security, runtime/DAST, immutable artifact and hosted acceptance gates remain authoritative.
