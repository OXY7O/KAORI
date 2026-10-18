# KAORI Reusable Components — Page/State Conformance Matrix

> **Audit candidate — source inventory, not executed Visual QA.** Original 2026-10-17 snapshot plus 2026-10-18 exact-head addendum. Do not treat historical row links as current-head QA. Work authority [#2296](https://github.com/OXY7O/KAORI/issues/2296); Design System [#572](https://github.com/OXY7O/KAORI/issues/572); focused table-action audit [#2270](https://github.com/OXY7O/KAORI/issues/2270).

| Field | Pinned value |
| --- | --- |
| Source branch | `kaori/review/staging-uat` |
| Audited baseline | `1c110073c947bf3444e996794e8a1734d4007bda` |
| Proposed evidence branch | `kaori/task-2296-ui-conformance-matrix-uat` |
| Work type | Documentation + execution plan; **no visual/product implementation** |
| Current addendum holding SHA | `4aa8d2641c775f99eaf130974529125fba99ef0e` (supplemental C074–C088 only) |
| Kubernetes Inventory focused source audit SHA | `d81c3304f7116742ce4ce1b395ae9ad4034f983d` (C089–C098; no browser execution) |
| Full Kubernetes entry-surface source coverage | `d81c3304f7116742ce4ce1b395ae9ad4034f983d` (C099–C147; 49 entries; no browser execution) |
| Official CI, Developer Check, Full Admission | **HOLD — NOT RUN** |
| Dev Container / Playwright / human acceptance | **NOT RUN** — no Dev Container/browser runtime in the connected environment |
| Promotion / release | **NOT AUTHORIZED** |

## 1. Authority, scope and meaning

- Current authoritative contracts: [Design System reference map](../REFERENCE_IMPLEMENTATION_AND_ENFORCEMENT.md), [canonical ownership](../components/REUSABLE_COMPONENT_OWNERSHIP.md), [Visual QA](../KAORI_VISUAL_QA.md), plus the relevant `docs/design/components/*.md` contract. Historical audit/closed issues establish accepted exceptions but do not supersede current approved standards.
- Existing executable catalog: `tests/ui/visual_audit.py::build_visual_surface_inventory()`; browser fixtures/viewports in `tests/ui/conftest.py`; accepted scenario format in `docs/TESTING.md`, with retrospective register tracked in [#1738](https://github.com/OXY7O/KAORI/issues/1738). **This matrix is not a second scenario registry or test runner.**
- Scope: sampled active consumer/reference files across nine requested component families. This is **not** an exhaustive census of every template or every possible state. Each row has an independently reviewable owner/issue; uninspected combinations remain pending.
- Semantic roles matter: compact table utility does **not** equal 40px create/save mutation; critical/destructive retains Critical semantics; domain-owned data/provider evidence stays authoritative.

### Source audit classifications (not Visual QA scores)

| Code | Meaning | May this be called a browser PASS? |
| --- | --- | --- |
| `S` | Shared-owner use or an existing source contract is visible in the cited file | **No** |
| `D` | Confirmed source-level divergence; a bounded issue records the finding | **No** |
| `E` | Documented accepted exception/approved domain-specific composition | **No** |
| `R` | Source or interaction requires exception review, fixture or runtime evidence | **No** |

Actual executed Visual QA uses only the existing three states in `KAORI_VISUAL_QA.md`: **PASS**, **Needs refinement**, **Broken**. **No row has received one of these findings yet**. Browser evidence, screenshot, trace, and human acceptance are all `NOT RUN`.

## 2. Component owner lookup

| Family | Canonical source/standard | Minimum visual/interaction assertions |
| --- | --- | --- |
| Action Buttons & Table Actions | `components/action_button.html`, `components/table_primitives.html`, `components/table.html`; `BUTTON.md`, `TABLE_AND_LABEL.md` | Semantic primary/secondary/Critical, icon label, keyboard focus, hover/disabled/loading, compact row geometry |
| Tables | `components/table.html`, `components/table_primitives.html`; `TABLE_AND_LABEL.md` | No document overflow, stable header/cell alignment, actions reachable, zero-state retained |
| Filters & Pagination | `components/table_registry.html`, `components/pagination.html`; `PAGINATION.md` | Default five, 5/10/25/50 options, reset-to-page-1, Clear first when active, HTMX history/zero |
| Hero & Page Context | `components/page_hero.html`, `components/page_context_card.html`; `HERO.md` | Title/description/context/action hierarchy, responsive single-line nonphone rule |
| Tabs & Navigation | `workspace_tabs.html`, `framed_workspace_tabs.html`, `content_tabs.html`, `segmented_tabs.html`, shared sidebar/navbar; `TAB_STYLES.md` | Role/ARIA, roving focus, Left/Right/Home/End, URL/HTMX, mobile horizontal overflow |
| Forms | `components/form_field.html`, `form_action_bar.html`, `action_button.html`; `FORM.md` | Labels/required/error, CSRF, validation retention, enter/submit, no-JS fallback, disabled/loading |
| Modals & Drawers | `destructive_confirmation_modal.html`, `resource_detail_modal.html`, `side_drawer.html`, native dialog controller; `MODAL_DRAWER.md` | Dialog label, opening focus, Escape, focus return, overlay, Critical consequence, responsive |
| Cards | `operational_section_card.html`, `operational_metric_card.html`, `workspace_summary_card.html`; `CARD.md` | Card geometry, information hierarchy, source/action placement, light/dark and wrapping |
| Loading & Feedback | `loading_bar.html`, `operational_section_loading.html`, `operational_toast.html`, `operation_feedback_oob.html`, state components; `LOADING.md`, `OPERATIONAL_ACTION_FEEDBACK.md` | Region-owned indicator, accurate pending/error, reduced motion, semantic ARIA, toast persistence and no fake empty |

## 3. Page-by-state audit matrix

**Reading rule:** the source classification is based on pinned GitHub source and existing issue history. The `Browser / human` result is always **NOT RUN**. `S` means ownership has been observed in the cited template, not that every requested state is proven.

| ID | Page/surface | Family | State(s) to review | Source evidence | Source | Authority / finding | Browser / human |
| --- | --- | --- | --- | --- | :---: | --- | --- |
| C001 | Welcome | Hero / Page Context | default | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/welcome/index.html) | `S` | — · Shared Hero; Welcome rendered reference | NOT RUN |
| C002 | Welcome | Cards | normal + responsive | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/welcome/index.html) | `S` | — · Shared catalog/card surfaces; geometry requires browser | NOT RUN |
| C003 | Welcome | Navigation | keyboard + theme | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/welcome/index.html) | `R` | — · Navigation/visual tests exist, unexecuted in this review | NOT RUN |
| C004 | Access · Activity Audit | Cards | normal | [`_activity_summary_cards.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/access/activity_audit/partials/_activity_summary_cards.html) | `E` | — · Existing approved four-metric and evidence-boundary composition | NOT RUN |
| C005 | Access · Activity Audit | Tables | normal + zero | [`_activity_table_content.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/access/activity_audit/partials/_activity_table_content.html) | `S` | #2270 · Canonical table/action usage; zero-state browser pending | NOT RUN |
| C006 | Access · Activity Audit | Filters & Pagination | filtered + zero | [`_activity_table_card.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/access/activity_audit/partials/_activity_table_card.html) | `S` | #2270 · Preserve search/page context and canonical footer | NOT RUN |
| C007 | Access · Users | Cards | normal | [`_summary_cards.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/access/users/partials/_summary_cards.html) | `E` | — · Access-specific approved overview geometry; no forced KPI migration | NOT RUN |
| C008 | Access · Users | Table Actions | normal + permissions | [`_table.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/access/users/partials/_table.html) | `S` | #2270 · Compact row action role observed | NOT RUN |
| C009 | Access · Roles | Tables / Filters | filtered + zero | [`_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/access/roles/partials/_registry.html) | `S` | #2270 · Table registry, conditional Clear and footer | NOT RUN |
| C010 | Access · Identity Providers | Tabs / Navigation | active + URL + keyboard | [`_tabs.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/access/identity_providers/partials/_tabs.html) | `S` | #1329 · Framed tabs adapter; HTMX history/browser not run | NOT RUN |
| C011 | Access · Identity Providers | Hero / Context | normal + blocked | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/access/identity_providers/index.html) | `S` | #1329 · Hero/context composition, permission variants pending | NOT RUN |
| C012 | Kubernetes · Dashboard | Cards | normal + responsive | [`_kpi_cards.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/dashboard/partials/_kpi_cards.html) | `S` | #923 · Shared operational_metric_card | NOT RUN |
| C013 | Kubernetes · Dashboard | Loading / Feedback | initial + delayed | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/dashboard/index.html) | `R` | #943 · Owned Fast Shell loading contract; render evidence outstanding | NOT RUN |
| C014 | Kubernetes · Inventory · Nodes | Tables | normal + overflow | [`_table_content.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/inventory/nodes/partials/_table_content.html) | `S` | #2270 · Shared table; wide-table viewport clipping NOT RUN | NOT RUN |
| C015 | Kubernetes · Inventory · Nodes | Filters / Pagination | filtered + zero | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/inventory/nodes/partials/_table_card.html) | `S` | #2270 · Canonical actions/footer and table loading | NOT RUN |
| C016 | Kubernetes · Analytics Overview | Tabs / Navigation | active + lazy | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/analytics/overview/index.html) | `S` | #1106 · Shared Content Tabs; loader tracking separate from worker | NOT RUN |
| C017 | Kubernetes · Analytics Overview | Loading | initial + lazy + reduced motion | [`_section_loading.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/analytics/overview/partials/_section_loading.html) | `D` | #2295 · Active local copied skeleton; shared loading owner pending | NOT RUN |
| C018 | Kubernetes · Analytics Overview | Loading / Feedback | error + retry | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/analytics/overview/index.html) | `R` | #2295 · HTMX failure/retry, busy state not browser verified | NOT RUN |
| C019 | Kubernetes · Tenant · Credentials | Table Actions | normal + permission | [`_credential_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/tenant/partials/_credential_registry.html) | `S` | #2270 · Compact row utilities; preserve More launcher | NOT RUN |
| C020 | Kubernetes · Tenant · Credentials | Modals / Action Buttons | dialog + mutation + Critical | [`_credential_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/tenant/partials/_credential_registry.html) | `D` | #2276 · Workflow submit in More dialog uses compact table action | NOT RUN |
| C021 | Kubernetes · Tenant · Access Grants | Modals / Action Buttons | dialog + mutation + Critical | [`_access_grant_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/tenant/partials/_access_grant_registry.html) | `D` | #2276 · Reconcile/Revoke dialog geometry mismatch | NOT RUN |
| C022 | Kubernetes · Tenant · Groups | Forms / Modals | edit + save + cancel | [`_group_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/tenant/partials/_group_registry.html) | `D` | #2290 · Local Save/Cancel styles within existing edit dialog | NOT RUN |
| C023 | Kubernetes · Tenant · Operations | Tabs / Navigation | active + URL + filters | [`operations.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/tenant/operations.html) | `S` | — · Shared Content Tabs; preserve existing primary drift navigation | NOT RUN |
| C024 | Kubernetes · Tenant · Operations | Tables / Pagination | normal + zero | [`_operations_drift_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/kubernetes/tenant/partials/_operations_drift_registry.html) | `S` | #2270 · Shared registry and footer; wide table needs viewport | NOT RUN |
| C025 | Kubernetes · Operations · Secret Reveal | Forms | ready + blocked + permission | [`_cluster_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html) | `R` | — · Controlled security mutation surface; browser negative cases pending | NOT RUN |
| C026 | Integrations · Overview | Tabs / Navigation | active + URL | [`overview.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/integrations/overview.html) | `S` | #916 · Framed Workspace Tabs; no provider mutation in QA | NOT RUN |
| C027 | Integrations · Registry | Tables / Pagination | normal + zero | [`_provider_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/integrations/components/_provider_registry.html) | `S` | #2270 · Shared pagination and connection action classes | NOT RUN |
| C028 | Integrations · Metrics Source | Filters / Pagination | filtered + zero | [`_capability_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/integrations/observability/metrics_source/partials/_capability_registry.html) | `S` | #2270 · Shared table filter, loading bar, numeric pages | NOT RUN |
| C029 | Integrations · Alertmanager | Filters / Pagination | filtered + zero | [`_capability_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_capability_registry.html) | `S` | #2270 · Shared capability registry geometry | NOT RUN |
| C030 | Integrations · Kubernetes Provider | Action Buttons | source bound + destructive | [`_registry_detail_content.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry_detail_content.html) | `E` | #404 · Approved normal/critical semantic tone distinction | NOT RUN |
| C031 | Integrations · Notification Channels | Table Actions | normal + header | [`_channels_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html) | `D` | #2283 · Add Channel / Setup Guide header actions local styles | NOT RUN |
| C032 | Integrations · Notification Channels | Forms / Modals | create + edit + guide | [`_channel_modals.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html) | `D` | #2292 · Workflow modal action classes are locally owned | NOT RUN |
| C033 | Integrations · Notification Channels | Loading / Feedback | success + failure + audit | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/integrations/delivery/notification_channels/index.html) | `R` | #1429 · Runtime toast and notification evidence not executed | NOT RUN |
| C034 | Artifact Registry · Security | Hero / Context | normal + degraded | [`_security_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/artifact_registry/partials/_security_workspace.html) | `S` | #2268 · Shared Hero and committed-evidence labels | NOT RUN |
| C035 | Artifact Registry · Security | Table Actions | normal + row details | [`_security_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/artifact_registry/partials/_security_workspace.html) | `S` | #2268 · View More / Open Runtime Usage accepted reference | NOT RUN |
| C036 | Artifact Registry · Security | Cards / Loading | loading + empty + blocked | [`_security_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/artifact_registry/partials/_security_workspace.html) | `S` | — · Shared section/metric, bar and canonical states observed | NOT RUN |
| C037 | Artifact Registry · Security | Tabs / Navigation | active + HTMX | [`_security_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/artifact_registry/partials/_security_workspace.html) | `S` | — · Content Tabs imported; state switch not executed | NOT RUN |
| C038 | Object Storage · Dashboard | Cards | normal + responsive | [`_kpi_cards.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/storage/object_storage/dashboard/partials/_kpi_cards.html) | `S` | #923 · Shared operational_metric_card | NOT RUN |
| C039 | Object Storage · Bucket Inventory | Tables / Pagination | filtered + zero | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/storage/object_storage/inventory/buckets/partials/_table_card.html) | `S` | #2270 · Shared table/footer; per-page reset needs browser | NOT RUN |
| C040 | Object Storage · Bucket Inventory | Modals / Drawers | open + close + focus | [`_table_content.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html) | `S` | — · Shared detail launcher; keyboard/focus unexecuted | NOT RUN |
| C041 | Object Storage · Analytics · Alerts | Tabs / Navigation | active + lazy | [`_alerts_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html) | `S` | — · Shared Content Tabs and hidden panels | NOT RUN |
| C042 | Object Storage · Analytics · Alert Records | Filters / Header Actions | filtered + zero | [`_alert_records.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/storage/object_storage/analytics/partials/_alert_records.html) | `D` | #2284 · Clear Filters follows persistent context labels | NOT RUN |
| C043 | Object Storage · Analytics · Buckets | Filters | filtered + reset | [`_bucket_table.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/storage/object_storage/analytics/partials/_bucket_table.html) | `R` | #2270 · 40px Clear Filters may be valid filter-row alignment | NOT RUN |
| C044 | Intelligence · Alert Intelligence | Forms / Filters | normal + filtered | [`_alert_intelligence_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/intelligence/partials/_alert_intelligence_workspace.html) | `S` | — · Shared filter geometry and hx-sync | NOT RUN |
| C045 | Intelligence · Alerts | Tables / Loading | normal + history + zero | [`_alert_ops_history.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/intelligence/partials/_alert_ops_history.html) | `S` | — · Shared loading bar/header and canonical state | NOT RUN |
| C046 | Intelligence · Routing Editor | Forms / Modals | create + update + Critical | [`_alert_ops_routing_editor_modal.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/intelligence/partials/_alert_ops_routing_editor_modal.html) | `D` | #2293 · Local submit/delete interaction states | NOT RUN |
| C047 | Intelligence · Automation Control | Forms / Modals | save + blocked + permission | [`_execution_configuration_modal.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/intelligence/partials/automation_control/_execution_configuration_modal.html) | `D` | #2293 · Locally owned policy save buttons | NOT RUN |
| C048 | Platform Operations · Jobs | Hero / Tabs | normal + navigation | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/platform_operations/jobs/index.html) | `S` | — · Shared Hero and Framed Workspace Tabs | NOT RUN |
| C049 | Platform Operations · Jobs | Cards / Loading | refresh + idle + active | [`_active_jobs.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/platform_operations/jobs/executions/partials/_active_jobs.html) | `S` | — · Region-specific loading bar and progress evidence | NOT RUN |
| C050 | Platform Operations · Jobs | Table Actions | cancel + protected | [`_active_jobs.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/platform_operations/jobs/executions/partials/_active_jobs.html) | `S` | #2270 · Critical cancel/permission preserved; no mutation execution | NOT RUN |
| C051 | Platform Operations · Jobs | Empty / Feedback | queue clear + error | [`_active_jobs.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/platform_operations/jobs/executions/partials/_active_jobs.html) | `S` | — · Canonical healthy-zero; failure feedback runtime pending | NOT RUN |
| C052 | Platform Operations · Data Lifecycle | Hero / Tabs | normal + navigation | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/platform_operations/data_lifecycle/index.html) | `S` | #1569 · Canonical shared Hero/Framed Tabs | NOT RUN |
| C053 | Platform Operations · Data Lifecycle | Action Buttons / Forms | save + archive + cleanup | [`_domain_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html) | `D` | #2291 · Local policy save/execute button geometry | NOT RUN |
| C054 | Platform Operations · Data Lifecycle | Loading / Feedback | pending + blocked + error | [`_domain_workspace.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html) | `R` | #1569 · No unsafe archive/cleanup mutations in visual-only QA | NOT RUN |
| C055 | Reports · Generate | Hero / Context | ready + blocked | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/generate/index.html) | `S` | — · Shared Hero/context; workflow readiness variants pending | NOT RUN |
| C056 | Reports · Generate | Forms | validation + wizard step | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/generate/index.html) | `R` | #1738 · Wizard negative/positive scenarios reference QE registry | NOT RUN |
| C057 | Reports · Templates | Table Actions | normal + selected | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/report_templates/index.html) | `D` | #2275 · View icon order and local action class bundles | NOT RUN |
| C058 | Reports · Templates | Forms / Modals | create + edit + delete | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/report_templates/index.html) | `D` | #2275 · Compact modal Cancel/Save and delete confirmation drift | NOT RUN |
| C059 | Reports · Generated | Tables / Pagination | normal + zero + filtered | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/generated/index.html) | `S` | — · Shared table registry, pagination and empty states | NOT RUN |
| C060 | Reports · Generated | Loading / Feedback | background polling + pending | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/generated/index.html) | `R` | — · Background poll indicator behavior requires human review | NOT RUN |
| C061 | Reports · Generated | Table Actions | bulk selection + archive | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/generated/index.html) | `S` | #2270 · Compact registry utility; mutation needs safe fixture | NOT RUN |
| C062 | Reports · Storage | Tabs / Navigation | active + URL | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/storage/index.html) | `S` | — · Shared Content Tabs; HTMX/history QA pending | NOT RUN |
| C063 | Reports · Storage | Hero / Context | normal + degraded | [`index.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/reports/storage/index.html) | `S` | — · Shared Hero/context; provider storage posture dynamic | NOT RUN |
| C064 | Settings · General | Tabs / Navigation | active + URL | [`_tabs.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/settings/general/partials/_tabs.html) | `S` | — · Shared Integrated Workspace tabs | NOT RUN |
| C065 | Settings · General · Compatibility | Filters / Pagination | filtered + reset + no-JS | [`_compatibility_registry.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/settings/general/partials/_compatibility_registry.html) | `R` | — · Apply/Reset local fallback; preserve progressive enhancement | NOT RUN |
| C066 | Settings · Account | Tabs / Navigation | active + URL | [`_tabs.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/settings/account/partials/_tabs.html) | `S` | — · Shared Integrated Workspace tabs | NOT RUN |
| C067 | Shared · Destructive Confirmation | Modals / Action Buttons | confirm + cancel + focus | [`destructive_confirmation_modal.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/components/destructive_confirmation_modal.html) | `D` | #2277 · Shared Critical interaction-state styling gap | NOT RUN |
| C068 | Shared · Resource Details | Modals / Drawers | open + Escape + focus return | [`resource_detail_modal.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/components/resource_detail_modal.html) | `S` | #2271 · Action delegation merged earlier; browser acceptance pending | NOT RUN |
| C069 | Shared · Side Drawer | Modals / Drawers | open + Escape + focus trap | [`side_drawer.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/components/side_drawer.html) | `S` | — · Canonical shell/ARIA; JS runtime tests pending | NOT RUN |
| C070 | Shared · Operational Feedback | Loading / Feedback | success + warning + error | [`operational_toast.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/components/operational_toast.html) | `S` | — · Semantic ARIA live/role and shared toast contract | NOT RUN |
| C071 | Shared · Empty State | Cards / Feedback | healthy-zero + no-result | [`_empty_state.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/components/states/_empty_state.html) | `S` | — · Canonical label/action permissions; output not rendered here | NOT RUN |
| C072 | Shared · Blocked State | Cards / Feedback | setup + unavailable | [`_blocked_state.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/components/states/_blocked_state.html) | `S` | — · Canonical blocked variant; distinguish dependency failure | NOT RUN |
| C073 | Shared · Loading | Loading / Feedback | busy + reduced motion | [`operational_section_loading.html`](https://github.com/OXY7O/KAORI/blob/1c110073c947bf3444e996794e8a1734d4007bda/app/templates/components/operational_section_loading.html) | `S` | #943 · Reusable skeleton owned by Operational Dashboard family | NOT RUN |

## 3.1 Current-head source reconciliation — 2026-10-18

> **Additive exact-head review; does not rewrite historical baseline evidence.** The 73 original C001–C073 rows remain pinned to commit `1c110073c947bf3444e996794e8a1734d4007bda`. The 15 C074–C088 supplementary rows below were reviewed against holding `4aa8d2641c775f99eaf130974529125fba99ef0e`. Neither source inspection is browser execution.

| Item | Verified read-only state |
| --- | --- |
| Latest reviewed holding SHA | `4aa8d2641c775f99eaf130974529125fba99ef0e` |
| Original matrix source SHA | `1c110073c947bf3444e996794e8a1734d4007bda` |
| Diff between source SHAs | 59 commits, 37 changed files, 0 behind (GitHub compare) |
| Original distinct file links still present | 58 / 58 |
| Directly changed baseline-linked templates | Notification Channels `_channels_workspace.html`, `_channel_modals.html`, and `index.html` |
| Indirect cross-family changed owner | `components/table_primitives.html::action_classes(size='header')` |
| Scope after additive reconciliation | 73 original rows + 15 supplemental = **88 page/state source rows**; not an exhaustive route census |
| Playwright / browser / human acceptance | **NOT RUN / PENDING**; never infer PASS from source or issue history |
| CI / staging / main / release | **HOLD**; this update is on the existing draft PR issue branch only |

### Changed-source interpretation

- **C031–C033 require re-evaluation at current HEAD.** Provider-card Guide/Configure actions now use shared compact `table_ui.action_classes(size='header')`; this does not resolve top-level Channel Registry `Setup Guide` / `Add Channel` local class ownership in #2283. Configured Channels now has canonical name/provider/enabled filters (#2318), header-owned loading (#2327), result-count and pagination; Delivery Activity now uses the shared event-key filter/clear contract (#2319). Modal headers/provider guidance changed (#2320/#2321/#2330), but #2292 still owns distinct modal-footer workflow buttons.
- **Shared table primitives changed** to add the header-size variant. It preserves compact row geometry and is not a replacement for 40px primary workflow controls. All indirect consumers and negative states still require regression tests; compare alone does not prove estate-wide conformance.
- **Other original C### file paths remain addressable**, but unchanged file bytes are not a substitute for browser testing, data projection review, CSS bundle verification, or new feature-route coverage.

### Supplemental conformance rows

| ID | Page/surface | Family | State(s) to review | Source evidence (current SHA) | Source | Authority / finding | Browser / human |
| --- | --- | --- | --- | --- | :---: | --- | --- |
| C074 | Integrations · Notification Channels Registry | Filters / Loading | normal + filtered + zero + request | [_channels_workspace.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/integrations/delivery/notification_channels/partials/_channels_workspace.html) | S | #2318, #2327 · Shared HTMX filter, filtered count, 5-row footer and header-owned loading integrated; browser pending. | NOT RUN |
| C075 | Integrations · Notification Delivery Activity | Filters / Pagination | exact event-key + clear + zero | [index.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/integrations/delivery/notification_channels/index.html) | S | #2319 · Shared filter and Clear link source-integrated; preserve event-key matching and tab-scoped HTMX. | NOT RUN |
| C076 | Integrations · Notification Guide / Config | Forms / Modals | guide + create + edit + keyboard | [_channel_modals.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/integrations/delivery/notification_channels/partials/_channel_modals.html) | D | #2292, #2320, #2321, #2330 · Guide/header/copy refined on holding; modal footer action ownership remains separate source debt; UAT pending. | NOT RUN |
| C077 | Settings · General | Loading / Tabs | tab fetch + screen-reader status | [_page_content.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/settings/general/partials/_page_content.html) | E | #2225 · Superseding human decision: no visible loading bars in Settings; nonvisual HTMX status is source-present. | NOT RUN |
| C078 | Settings · Account | Loading / Tabs | tab fetch + mutation feedback | [_page_content.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/settings/account/partials/_page_content.html) | E | #2225 · Same approved exception; nonvisual HTMX status and canonical mutation feedback retained. | NOT RUN |
| C079 | Shared · Right Context Rail | Cards / Documentation | related workspace light + dark | [RIGHT_CONTEXT_RAIL.md](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/docs/design/components/RIGHT_CONTEXT_RAIL.md) | D | #751, #572 · Rail doc still claims legacy deep-Violet related card while component and approved ownership require soft Violet. | NOT RUN |
| C080 | Shared · Workspace Summary Card | Cards / Typography | title + description + wrap | [workspace_summary_card.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/components/workspace_summary_card.html) | D | #572 · Documented 14/12px conflicts with implemented 16/14px; decide accepted authority before styling. | NOT RUN |
| C081 | Shared · Resource Detail History | Modals / Navigation | open + Back + Forward + direct link | [detail_rows.js](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/static/js/detail_rows.js) | D | #572 · Standard requires history push on row open; current opener calls replace; runtime navigation not proven. | NOT RUN |
| C082 | Access · User Profile Form | Forms / Accessibility | label + input accessible name | [form.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/access/users/form.html) | R | #1340, #1726 · Some labels have no explicit for/wrapping input in source; browser accessibility-tree confirmation required. | NOT RUN |
| C083 | Shared · Embedded Form Action Bar | Forms / Tokens | surface + dark theme + focus | [form_action_bar.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/components/form_action_bar.html) | R | #572 · Uses bg-surface-subtle; token mapping not seen in @theme source; verify generated CSS before declaring visual FAIL. | NOT RUN |
| C084 | Kubernetes · Tenant Overview Posture | Cards / Responsive | five peers + narrow + zoom | [overview.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/kubernetes/tenant/overview.html) | R | #572 · Existing columns=5 resource posture grid is incompletely described in 3/4-column doc; determine approved exception. | NOT RUN |
| C085 | Shared · Inventory Asset Catalog | Cards / Ownership | cross-domain asset destinations | [inventory_asset_card.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/components/inventory_asset_card.html) | S | #946 · Canonical asset card reused beyond Kubernetes; reconcile docs' Kubernetes-only scope without new components. | NOT RUN |
| C086 | Artifact Registry · Governance | Empty / Progress | observed-empty + not-collected + viewer | [_governance_workspace.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/artifact_registry/partials/_governance_workspace.html) | R | #1453 · Presenter owns replication empty copy, but observed-zero/read-only polling require domain and browser verification. | NOT RUN |
| C087 | Shared · Destructive Confirmation | Modals / Responsive | short viewport + focus + critical | [destructive_confirmation_modal.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/components/destructive_confirmation_modal.html) | R | #2277 · Short viewport and long consequences: verify modal body scrolling and critical action states. | NOT RUN |
| C088 | Reports · Templates Registry | Tables / Filters | header + row + 40px filters | [index.html](https://github.com/OXY7O/KAORI/blob/4aa8d2641c775f99eaf130974529125fba99ef0e/app/templates/reports/report_templates/index.html) | D | #2275, #2305, #2313 · Existing action debt plus focused table geometry and filter-height source issues; keep issue scopes separate. | NOT RUN |

### Authority reconciliation candidates (not auto-approved changes)

1. **Source/doc mismatch:** Resource Detail history navigation needs a bounded authority decision: `RESOURCE_DETAIL_MODAL.md` says opening pushes browser history, while `detail_rows.js` row opens with replace. Preserve direct links, Back/Forward and focus behavior during any fix; do not implement a new navigation framework.
2. **Stale guidance:** `RIGHT_CONTEXT_RAIL.md` still describes legacy deep-Violet Related Page Card; `RELATED_PAGE_CARD.md`, `REUSABLE_COMPONENT_OWNERSHIP.md`, and `related_page_card.html` support soft Violet (#751). Reconcile approved documentation; do not restore full-Violet panel.
3. **Typography contract:** `WORKSPACE_SUMMARY_CARD.md` says 14px title and 12px description, whereas current shared HTML uses 16px and 14px. Human-approved reference determines whether code or documentation changes.
4. **Documented composition:** `resource_posture_grid.html` supports five-column Tenant posture and `inventory_asset_card.html` is reused cross-domain. Document observed composition only after accepted viewport/semantic review.
5. **Accessibility and tokens require proof:** bare form labels and `bg-surface-subtle` in embedded Form Action Bar are source-level review candidates, not asserted browser failures; check accessible names and generated CSS first.

### Batch additions to the existing nine QA batches

- **Batch A/C:** include Notification Channel top-level header, provider-card compact actions, filtered/zero Channel Registry, Delivery Activity exact event-key, 5→10 Rows and live Clear reset; verify current `table_primitives` header/row semantics.
- **Batch F/G:** include Access username/email/password accessibility-tree labels, embedded form footer surface under light/dark, Resource Detail row open → Back → Forward → direct URL, destructive modal at 360×800/200% zoom.
- **Batch H/I:** include Related Workspace soft Violet, peer summary typography, Tenant five-column posture, Governance observed-empty vs not-collected, Settings nonvisual HTMX status, Kubernetes Analytics skeleton (#2295), stale/failure and Job progress.
- Reuse established #543/#1726/#1738 scenario and visual-test authorities. No new runners, screenshots, baselines, or acceptance statuses from this documentation revision.

### Scope and acceptance gate

- This delta updates **source evidence and test planning only**. `D` denotes source/documentation divergence, `R` requires further characterization, `E` preserves a source-visible approved exception, and `S` means shared-owner use is observed; none means tested PASS.
- New implementation issues are not implicitly authorized by this matrix. First search relevant current/merged issue authorities; make a bounded child issue only for an unresolved confirmed defect without owner, preserving #572 as umbrella.
- Before accepting the matrix, recheck exact review branch HEAD and attach actual Dev Container fixture, role, viewport/theme, screenshot/trace, and human acceptance for each executed batch. Current statuses remain **NOT RUN**.

---

## 3.2 Kubernetes Inventory sibling conformance — 2026-10-18 (source audit)

**Audit authority:** Kubernetes Inventory #733, reusable component matrix #2296 and Design System v2 #572. **Exact reviewed holding baseline:** `d81c3304f7116742ce4ce1b395ae9ad4034f983d`. These are additive current-head observations; original C001–C088 rows remain pinned to their earlier evidence SHAs. **No browser execution, screenshots, runtime verification or human acceptance occurred.** Source classification is not an execution PASS.

| ID | Active consumer | Family | State coverage to execute | Exact source evidence | Source | Finding / ownership | Browser / human |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C089 | Kubernetes · Inventory Overview | Hero / Cards / Table | fleet + zero + detail + narrow | [`index.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/overview/index.html) · [`_resources_by_cluster_content.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/overview/partials/_resources_by_cluster_content.html) | `S` | #733 · Shared section intro, table, pagination and cluster detail host; semantic freshness/zero and modal unexecuted | NOT RUN |
| C090 | Kubernetes · Node Inventory | Tables / Filters | filtered + zero + keyboard | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/nodes/partials/_table_card.html) | `S` | #733 · Shared registry, linked filter labels and HTMX page workspace; viewport/test result unexecuted | NOT RUN |
| C091 | Kubernetes · Namespace Inventory | Tables / Filters | filtered + zero + keyboard | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/namespaces/partials/_table_card.html) | `S` | #733 · Linked filter labels and shared registry; click/focus and responsive unexecuted | NOT RUN |
| C092 | Kubernetes · Workload Inventory | Tables / Pagination | filtered + zero + overflow | [`_table_content.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/workloads/partials/_table_content.html) · [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/workloads/partials/_table_card.html) | `S` | #1017 · Shared table and pager; accessible filter linkage present; no browser conformance claim | NOT RUN |
| C093 | Kubernetes · Pod Inventory | Tables / Filters / Detail | filtered + owner + modal | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/pods/partials/_table_card.html) | `S` | #1017 · Linked filter labels and shared table block; long-name/detail modal scenarios outstanding | NOT RUN |
| C094 | Kubernetes · Service Inventory | Filters / Accessibility | normal + refresh + keyboard | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/services/partials/_table_card.html) | `D` | **#2398 · Four unassociated visible filter labels/controls:** Cluster, Namespace, Service Type, Search Services | NOT RUN |
| C095 | Kubernetes · Ingress Inventory | Filters / Accessibility | normal + refresh + keyboard | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/ingresses/partials/_table_card.html) | `D` | **#2398 · Five unassociated visible filter labels/controls:** Cluster, Namespace, Ingress Class, TLS Reference, Search | NOT RUN |
| C096 | Kubernetes · Storage Inventory | Tables / Filters / Pagination | filtered + overflow + detail | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/storage/partials/_table_card.html) | `S` | #733 · Shared registry and linked filter controls; pagination and responsive still require execution | NOT RUN |
| C097 | Kubernetes · Configuration Inventory | Filters / Accessibility | normal + refresh + keyboard | [`_table_card.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/configuration/partials/_table_card.html) | `D` | **#2398 · Four unassociated visible filter labels/controls:** Cluster, Namespace, Object Type, Search | NOT RUN |
| C098 | Kubernetes · Resource Detail (all eight resource families) | Modal / Drawer / Detail | deep-link + Escape + focus + dark + mobile | [`DETAIL_STYLES.md`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/docs/design/components/DETAIL_STYLES.md) · [`resource_detail_modal.html`](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/components/resource_detail_modal.html) | `R` | #733 / #2271 · V10 shared-modal authority exists; per-family actual interaction, focus return and theme parity must be verified in Dev Container | NOT RUN |

**Source-level conformance summary:** nine Inventory page families were sampled; eight sibling registry filter templates were inspected, with a **confirmed 13-control semantic label-association drift in three templates**, already tracked as bounded #2398. Other families use the registered shared section/table/pagination owners in inspected source; `S` means *shared-source use*, not complete UI conformance. The overview is intentionally a different approved archetype (Fleet Snapshot → Asset Catalog → Cluster Table), so its different section structure is **not** drift. No global Design System token or component change is authorized by this finding.

**Next exact-head Dev Container pilot:** (1) render Service/Ingress/Configuration filtered forms and inspect accessible labels and click-to-focus; (2) rerender with HTMX and test filtered → cleared / zero results / page size 5 → 10; (3) exercise one Node and one Configuration detail open/Escape/focus return; (4) review all three affected registries at approved light/dark and desktop/mobile viewports with real screenshot/trace. Report the issue and pinned holding SHA with PASS/FAIL/BLOCKED/NOT RUN per executed scenario. Current status is **NOT RUN**. CI/CD admission, staging/main promotion and deploy remain **HOLD**.


## 3.3 Kubernetes complete entry-surface coverage — 2026-10-18

**Authority:** #572 Design System v2 → #2296 reusable-component conformance inventory; respective domain standards #733, #757, #2270, #405 and approved component contracts. **Exact immutable source baseline:** `d81c3304f7116742ce4ce1b395ae9ad4034f983d` (`kaori/review/staging-uat`). **Read-only source inspection, not a full rendered-product audit.**

### Scope and source-validation boundary

- GitHub recursive tree identified **329 HTML templates** under `app/templates/kubernetes/**`, `app/templates/platform_operations/kubernetes/**` and `app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/**`. These contain page entries, HTMX partials, components, and modal fragments, **not 329 distinct routes**.
- This coverage ledger lists **49 page/fallback entry templates across nine Kubernetes-adjacent page families**, and the GitHub tree path-existence check confirms **all 49** at the pinned SHA. Entry HTML was read for the represented route families; relevant composing partials were sampled, **not every one of the 329 files read line-by-line**. A route's `S` means observed use of a canonical shared owner in source, never an all-partial or rendered PASS.
- Category legend retained: `S` = shared-owner use observed; `D` = confirmed source divergence/issue; `R` = needs further source/runtime determination; `E` = intentionally approved special-purpose composition. Six `D` route entries represent **five distinct confirmed tracked remediation issues** (#2295, #2276, #2290, #2398, #2399; #2276 and #2290 share the Tenant Registry entry), not six newly discovered bugs. The separate #2400 navigational CTA ownership review is `R`, not confirmed nonconformance. **No source classification is browser PASS.**
- This is additive to C001–C098; earlier pinned audit evidence remains unchanged. This pass does not claim 49 application URLs were launched, nor that unauthorized, protected, provider or destructive scenarios were executed.

### All Kubernetes page/fallback entries

| ID | Page family / entry | Pinned entry template | Source | Evidence / disposition | Browser acceptance target | Visual / human |
| --- | --- | --- | --- | --- | --- | --- |
| C099 | Integration · frontpage | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html) | `S` | Provider Frontpage and Integration Workspace Tabs are reused | Coverage/Registry, role and zero | NOT RUN |
| C100 | Integration · detail | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html) | `S` | Shared Hero, Framed Tabs and provider detail posture; no cloned tab owner | Connection/Capabilities/Runtime/Lifecycle | NOT RUN |
| C101 | Cluster Registration · add | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/cluster/add.html) | `R` | Registration Hero and action bar reused; locally styled form fields need approved #405 boundary review | Kubeconfig, validation, TLS, mobile | NOT RUN |
| C102 | Cluster Registration · edit | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/cluster/edit.html) | `R` | Shared edit Hero and same form; field visual-contract comparison still needed | Rotation, credential test, failure | NOT RUN |
| C103 | Dashboard · index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/dashboard/index.html) | `S` | Shared Operational Dashboard workspace/tabs/section loading visible through included content | Fast Shell, stale, empty, tab keyboard | NOT RUN |
| C104 | Inventory · overview/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/overview/index.html) | `S` | Canonical Snapshot → Assets → Cluster Table and shared V10 detail modal | Fleet, zero, modal, narrow | NOT RUN |
| C105 | Inventory · nodes/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/nodes/index.html) | `S` | Shared section/table/pagination and detail-host reference | Long Node, missing evidence, modal | NOT RUN |
| C106 | Inventory · namespaces/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/namespaces/index.html) | `S` | Shared section/table/pagination and detail-host reference | Quota, PSA, mobile | NOT RUN |
| C107 | Inventory · workloads/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/workloads/index.html) | `S` | Shared table/pagination/modal; column precision #1017 | Owner, long names, responsive | NOT RUN |
| C108 | Inventory · pods/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/pods/index.html) | `S` | Shared table/pagination/modal; precision #1017 | Restarts, state, focus | NOT RUN |
| C109 | Inventory · services/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/services/index.html) | `D` | #2398: four unbound Service filter labels; shared table owner otherwise present | Filters, HTMX and screen reader | NOT RUN |
| C110 | Inventory · ingresses/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/ingresses/index.html) | `D` | #2398: five unbound Ingress filter labels; shared table owner otherwise present | TLS/hosts, filters, focus | NOT RUN |
| C111 | Inventory · storage/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/storage/index.html) | `S` | Shared table/pagination/modal and associated-resource evidence | Long PVC/PV, layout | NOT RUN |
| C112 | Inventory · configuration/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/configuration/index.html) | `D` | #2398: four unbound Configuration filter labels; protected metadata remains domain-owned | ConfigMap/Secret, filter focus | NOT RUN |
| C113 | Inventory · topology/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/inventory/topology/index.html) | `S` | Shared Visualization Workspace, Segmented Tabs and topology components | Graph/List, depth, keyboard | NOT RUN |
| C114 | Analytics · overview/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/overview/index.html) | `D` | #2295: copied local section skeleton; source lacks section-local busy semantics | Initial/lazy load, reduced-motion | NOT RUN |
| C115 | Analytics · alerts/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/alerts/index.html) | `S` | Shared analysis workspace, tabs, loading; inspected selectors have associated labels | Alerts/anomalies/error | NOT RUN |
| C116 | Analytics · capacity/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/capacity/index.html) | `S` | Shared analysis workspace and accessible cluster/time selectors | Allocation, risk, empty | NOT RUN |
| C117 | Analytics · forecast/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/forecast/index.html) | `S` | Shared analysis control structure; selector labels associated | Model/chart, no-source | NOT RUN |
| C118 | Analytics · storage/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/storage/index.html) | `S` | Shared analysis source/readiness controls | Usage, stale, responsive | NOT RUN |
| C119 | Analytics · top_consumers/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/top_consumers/index.html) | `S` | Shared analysis filters with linked selectors | Ranking, zero, pagination | NOT RUN |
| C120 | Analytics · utilization/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/utilization/index.html) | `S` | Shared analysis workspace and labeled filters | Lazy trend, partial/error | NOT RUN |
| C121 | Analytics · workload/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/workload/index.html) | `R` | Local quota/mapping lazy pulse placeholders; compare with suitable Analytics loading owner, not automatically Dashboard skeleton | Lazy tabs, busy, reduced motion | NOT RUN |
| C122 | Analytics · materialization/blocked | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/materialization/blocked.html) | `S` | Shared analytics Hero, dependency blocker and blocked posture | Unavailable source and RBAC | NOT RUN |
| C123 | Analytics · materialization/pending | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/analytics/materialization/pending.html) | `S` | Shared Hero and worker snapshot preparation context | Pending→ready/failure | NOT RUN |
| C124 | Tenant Management · overview | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/tenant/overview.html) | `R` | Shared sections/posture grid; five-peer responsive/documented-exception question in existing C084 | 5 peers, zoom/mobile | NOT RUN |
| C125 | Tenant Management · tenants | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/tenant/tenants.html) | `D` | #2276 / #2290: known child-partial modal action drift, no duplicate issue | Credential/Grant/Group dialog | NOT RUN |
| C126 | Tenant Management · tenant_detail | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/tenant/tenant_detail.html) | `R` | Large domain-owned detail and release/evidence partial; full per-state interaction review pending | Release, keyboard, negative | NOT RUN |
| C127 | Tenant Management · operations | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/tenant/operations.html) | `R` | Shared tabs/tables; classify reconciliation submit controls vs workflow action authority | Reconcile permissions, states | NOT RUN |
| C128 | Tenant Management · resource_profiles | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/tenant/resource_profiles.html) | `R` | #2367 responsive registry remediation present in source; Firefox/browser acceptance pending | 390/768/1024/1457px, Manage | NOT RUN |
| C129 | Tenant Management · namespace_provisioning | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/tenant/namespace_provisioning.html) | `S` | Shared Content Tabs and workflow sections; domain disclosures preserved | Allocation/cutover, errors | NOT RUN |
| C130 | Tenant Management · credential_material | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/tenant/credential_material.html) | `E` | Security-specific one-time credential presentation legitimately differs from ordinary inventory modal | TTL, redact, focus | NOT RUN |
| C131 | Operations · overview | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/overview.html) | `S` | Shared Hero, operational section and workspace links | Role, blocked, CTA | NOT RUN |
| C132 | Operations · cluster_required | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/cluster_required.html) | `S` | Shared Hero and canonical zero-cluster blocker | Unconfigured state | NOT RUN |
| C133 | Operations · configmaps/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/configmaps/index.html) | `S` | Shared workflow catalog, context and operational evidence | Capabilities, blocked | NOT RUN |
| C134 | Operations · configmaps/create | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/configmaps/create.html) | `S` | Shared Info Flow, form rail, validation boundary | Dry run, error, cancel | NOT RUN |
| C135 | Operations · configmaps/update | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/configmaps/update.html) | `S` | Shared form rail/Info Flow/evidence boundary | Diff/optimistic lock | NOT RUN |
| C136 | Operations · configmaps/delete | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/configmaps/delete.html) | `S` | Shared destructive confirmation and Critical workflow | Name match, denied | NOT RUN |
| C137 | Operations · secrets/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/secrets/index.html) | `S` | Shared Hero and protected workflow catalog | Role and routing | NOT RUN |
| C138 | Operations · secrets/create | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/secrets/create.html) | `S` | Shared choice cards/structured editor, secret boundary | No secret persistence | NOT RUN |
| C139 | Operations · secrets/replace | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/secrets/replace.html) | `S` | Shared form/Info Flow and preserved-key semantics | Partial input, failed validation | NOT RUN |
| C140 | Operations · secrets/delete | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/secrets/delete.html) | `S` | Shared destructive confirmation and protected evidence | Authorization and exact name | NOT RUN |
| C141 | Operations · secrets/reveal | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/secrets/reveal.html) | `E` | Approved step-up/approval/one-time protected reveal; intentionally nonstandard detail treatment | RBAC, step-up, expiry | NOT RUN |
| C142 | Operations · secrets/tls_rotate | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/secrets/tls_rotate.html) | `E` | TLS governance-approved full-width single-rotation and visible chooser exception | Preview/validate/focus | NOT RUN |
| C143 | Operations · secrets/tls_rotation | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/operations/secrets/tls_rotation.html) | `E` | Approved in-memory bulk rotation/upload workflow | Bulk failure, permission, focus | NOT RUN |
| C144 | Governance · overview/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/governance/overview/index.html) | `R` | Shared Hero/sections, local capability-card markup; verify accepted #757 card ownership before any migration | One/multiple cards, RBAC | NOT RUN |
| C145 | Governance · tls_certificates/index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/governance/tls_certificates/index.html) | `D` | #2399: TLS Search label targets missing input ID; fixed-width columns approved | Search, page 5, modal | NOT RUN |
| C146 | Governance · tls_certificates/detail | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/kubernetes/governance/tls_certificates/detail.html) | `S` | Shared Hero and bounded evidence detail route | Deep link, permitted action | NOT RUN |
| C147 | Kubernetes Administration · index | [source](https://github.com/OXY7O/KAORI/blob/d81c3304f7116742ce4ce1b395ae9ad4034f983d/app/templates/platform_operations/kubernetes/index.html) | `R` | #2400: Admin Overview navigational CTA visually duplicates primary button classes, but BUTTON.md excludes tabs/navigation from mutation-action contract; semantic owner decision pending | Tab activation, focus/disabled | NOT RUN |

### Confirmed remediation and non-duplicate backlog

| Finding | Severity to triage | Source / outcome | Authority |
| --- | --- | --- | --- |
| **Inventory Service/Ingress/Configuration filter associations** | Medium accessibility | 13 visible filter/control associations missing in 3 templates; standalone issue already exists, do not re-open | [#2398](https://github.com/OXY7O/KAORI/issues/2398) |
| **TLS Certificate Registry Search input association** | Low–Medium accessibility | `label for=tls-search-filter` has no corresponding ID because `table_ui.search_field(...)` omitted `id` | [#2399](https://github.com/OXY7O/KAORI/issues/2399) |
| **Kubernetes Analytics Overview copied loading skeleton** | Medium reusable ownership | Existing local `_section_loading.html` source and missing local `aria-busy` already tracked; not a proven runtime a11y failure | [#2295](https://github.com/OXY7O/KAORI/issues/2295) |
| **Tenant Credential/Grant dialog action hierarchy** | Medium UX | Compact table action geometry reused inside workflow mutation dialogs; preserve the table's compact More launcher | [#2276](https://github.com/OXY7O/KAORI/issues/2276) |
| **Tenant Group edit Save/Cancel ownership** | Low–Medium UX | Existing locally styled modal footer, separate from Credential/Grant action semantics | [#2290](https://github.com/OXY7O/KAORI/issues/2290) |
| **Kubernetes Admin navigational CTA ownership** | Review candidate | `_overview_workspace.html` Open Secret Reveal duplicates primary-like classes, but BUTTON.md excludes tabs/navigation; ownership must be decided before changing | [#2400](https://github.com/OXY7O/KAORI/issues/2400) |
| **Resource Profile responsive registry** | Existing UI feedback | Source uses responsive table/reflow candidate; #2367 has separate remediation, **browser/human still NOT RUN** | [#2367](https://github.com/OXY7O/KAORI/issues/2367) |

### Review candidates — not confirmed defects

- **Analytics → Workload:** local lazy pulse tiles in `workload/index.html:40–68`; examine suitability of existing Analytics/shared loader while preserving per-section HTMX and tab semantics. Do not incorrectly impose Operational Dashboard geometry.
- **Tenant → Overview:** five-peer `resource_posture_grid` composition is already a matrix/doc exception review (C084), not evidence of failed responsive behavior.
- **Tenant → Operations:** `_operations_drift_registry.html` uses compact `table_ui.action_classes()` for some reconciliation submits; determine whether these are row-level utilities or workflow mutations under #2270 before opening a finding.
- **Governance → Overview:** bespoke capability-card/link shape may be intentional per #757; compare canonical semantic card family and accepted #757 architecture before changing.
- **Cluster Add/Edit:** local field input class bundles in `cluster/partials/_form.html` are a potential reusable form-field boundary; honor merged #405 and its accepted registration contract before classifying.
- **Kubernetes Admin → Overview:** #2400 is a semantic component ownership review, not a confirmed defect: Open Secret Reveal is a tab-navigation CTA, not a resource mutation. Evaluate approved nav/tab CTA versus action-button contract before modifying geometry.
- **TLS registry:** deliberate fixed-width/hidden columns documented under #733 remain **accepted layout behavior**, even though some table classes are page-local. Do not turn proportional column specification into forced scroll/wrapping by mechanical shared macro replacement.

### Existing local Dev Container verification plan (no new runner)

Follow #1726, #1738 and existing `docs/design/KAORI_VISUAL_QA.md` / `tests/ui/visual_audit.py` only. Use **1440×900, 1280×800, 1024×768, 768×1024, 390×844, 360×800**, each light/dark. Execute and record the following separately by page family: Hero/section hierarchy, one normal and one blocked/empty/error state, role/permission gating, labels/focus, action active/disabled and destructive distinction, tab selection/history, modal open/Escape/focus restoration/deep link, filter/search/clear, HTMX swap with stale response, page-size 5→10/reset, long identifiers and horizontal overflow, loading/reduced motion and provider source freshness. Controlled mutation only on explicitly authorized test resources. Capture issue/work SHA, aggregation SHA, environment, provider readiness, expected/actual, screenshot/trace/log and human acceptance. Initial execution: **ALL NOT RUN**.

**Governance:** Audit documentation PR #2298 stays **OPEN/DRAFT** to `kaori/review/staging-uat`; #2398/#2399/#2400 are bounded remediation issues, not product changes. The work branch must be non-destructively reconciled with the moving holding baseline before integration. No official Developer Check, Full Admission, deployment, staging/main promotion or release authorized.


## 3.4 Remediation applied to temporary Dev Container holding — 2026-10-18

**Do not overwrite the pinned C001–C147 source findings.** Rows `D` remain truthful for their historical evidence SHA. This section records **subsequent source remediation** at a newer holding SHA; no browser acceptance follows from the GitHub merge.

**Aggregated Dev Container holding:** `kaori/review/staging-uat@be7922fac481e3b2374ce80ce6847d83c471cc8f`. The official `kaori/staging` / `main` and admission pipelines are **HOLD**.

| Source finding authority | Review entry | Issue-scoped remediation | Holding PR | Source disposition | Browser / UAT |
| --- | --- | --- | --- | --- | --- |
| #2398 | Inventory → Services, Ingresses, Configuration | Associate 13 filter labels with stable select/search IDs through existing table primitives | [#2402](https://github.com/OXY7O/KAORI/pull/2402) | MERGED holding; source readback | NOT RUN |
| #2399 | Governance → TLS Certificates → Search | Bind existing Search label to the shared search input | [#2403](https://github.com/OXY7O/KAORI/pull/2403) | MERGED holding; source readback | NOT RUN |
| #2290 | Tenant → Tenants → Memberships → Group Edit | Secondary Cancel and Primary Save use shared action button | [#2404](https://github.com/OXY7O/KAORI/pull/2404) | MERGED holding; source readback | NOT RUN |
| #2295 | Analytics → Overview → Health Summary / tabs | Delegate repeatable skeleton geometry to shared Analytics surfaces, with accessible busy/loading state | [#2405](https://github.com/OXY7O/KAORI/pull/2405) | MERGED holding; source readback | NOT RUN |
| #2276 | Tenant → Tenants → Credentials / Access Grants → More Actions | Shared secondary workflow actions and Critical Revoke, preserving compact table launchers | [#2406](https://github.com/OXY7O/KAORI/pull/2406) | MERGED holding; source readback | NOT RUN |
| #2367 | Tenant → Resource Profiles → Profile Library | Earlier responsive implementation already aggregated, not reimplemented | [#2370](https://github.com/OXY7O/KAORI/pull/2370), [#2372](https://github.com/OXY7O/KAORI/pull/2372) | SOURCE ALREADY REMEDIATED | NOT RUN |
| #2400 | Kubernetes Admin → Overview CTA | Navigation-vs-mutation owner remains a semantic review candidate; no speculative change | No remediation PR | REVIEW CANDIDATE | NOT RUN |

Existing components and documentation remain canonical: `table_primitives.search_field(..., id=...)`, `action_button.classes()` with shared Critical variant under `BUTTON.md`, and `analytics/components/_analysis_surfaces.html`. This is not a new domain architecture or provider-specific UI library.

**Source validation actually performed:** GitHub five PR bounded diffs, SHA-pinned merges and post-merge readback of 11 modified UI/docs paths. **No executable tests were run** in this GitHub-only environment. Review in Dev Container with approved `pytest` focused contracts, existing UI verifiers, frontend asset build, six viewports in light/dark, keyboard/AT, loading/empty/error/HTMX and explicit permitted mutation fixtures. Capture exact SHA/evidence, then request human acceptance before moving any issue to accepted/done or opening official staging PRs.


## 3.5 Object Storage page/view conformance — 2026-10-18 (source audit, #2411)

**Authority:** #572 Design System v2 → #2296 canonical page/state matrix → **#2411** Object Storage-specific source review; table/header findings retain existing owners #2270, #2284 and #2317. **Pinned source:** `kaori/review/staging-uat@7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088`.

**Coverage counting:** 98 template HTML files were enumerated by GitHub tree across `app/templates/storage/object_storage/**` and `app/templates/integrations/storage/object_storage/**`. They include HTMX partials, field adapters, and shared domain fragments, **not 98 distinct route pages**. Eight entry page/form/detail templates were identified; the Analytics entry uses six server-defined `page_key` views. The matrix therefore contains **13 meaningful page/view entries** plus **eight targeted partial-level samples**. All 21 documented paths have been verified in the source tree. This is **not a file-by-file review of all 98 templates** or proof of route/browser execution.

Use existing classifications `S` observed shared-source component ownership, `D` confirmed source drift, `R` needs semantic/visual investigation, `E` documented exception. In these 21 new rows: **S=12, D=4, R=5, E=0**. The four D rows represent **two distinct already-open findings**: #2284 and #2317 each appears once as a page/view entry and once as its exact underlying partial. Neither has been remediated by this audit; no new/duplicate defect was opened. A source `S` never means browser PASS.

| ID | Page/view or focused partial | Pinned source | Source | Concrete observed ownership / finding | Dev Container UAT focus | Execution |
| --- | --- | --- | --- | --- | --- | --- |
| C148 | Object Storage Dashboard | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/dashboard/index.html) | `S` | Canonical Operational Dashboard Hero, content/section loading and sections; #923 remains human-QA pending | System scope, 4-tab selection, KPI lazy HTMX, blocked/no-system | NOT RUN |
| C149 | Object Storage Inventory · Overview | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/inventory/overview/index.html) | `R` | Snapshot/Section Intro/shared cards and catalog; #946 human-accepted composition needs final runtime viewport check | 4-signal posture, 2 asset destinations, partial/unknown, narrow viewport | NOT RUN |
| C150 | Object Storage Inventory · Systems | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/inventory/systems/index.html) | `S` | Shared snapshot, labeled filters, table, 5-row pager, full detail modal; #1199 | Provider/Environment/Status/Search, long ID, no-system, detail | NOT RUN |
| C151 | Object Storage Inventory · Buckets & Containers | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/inventory/buckets/index.html) | `S` | Shared snapshot, five accessible filters, table, pagination, detail modal; #1199 | Quota/Protection, pending versus observed zero, filter clearing | NOT RUN |
| C152 | Object Storage Analytics · Overview | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/index.html) | `S` | Overview via route-scoped page_key; shared Hero/readiness, content tabs, tracker; #1114/#1122 | Snapshots, lazy vs server panels, unavailable source, tabs | NOT RUN |
| C153 | Object Storage Analytics · Capacity & Usage | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_capacity_workspace.html) | `R` | Shared Content Tabs and Analytics sections; shared bucket records table needs accessible-name review | Capacity/Quota/Buckets, 5-row pagination, charts, source gaps | NOT RUN |
| C154 | Object Storage Analytics · Performance | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_performance_workspace.html) | `R` | Shared Content Tabs; bucket record table semantic naming parity pending, not proven AT failure | Reliability/Traffic/Buckets, chart loading, bucket table | NOT RUN |
| C155 | Object Storage Analytics · Forecast | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html) | `S` | Shared Content Tabs + forecast worker status; forecast record table has descriptive caption | Window, worker status, history unknown, chart and record paging | NOT RUN |
| C156 | Object Storage Analytics · Top Consumers | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_top_consumers_workspace.html) | `R` | Shared Content Tabs + shared bucket records; table accessible-name parity pending | Storage/Activity/Records, rank consistency, filter and paging | NOT RUN |
| C157 | Object Storage Analytics · Alerts & Anomalies | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html) | `D` | #2284: Provider Alert Records header Clear Filters trails persistent source/status labels in DOM | Records tab, filter active, source fallback, keyboard and reading order | NOT RUN |
| C158 | MinIO Integration · Provider Landing | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/integrations/storage/object_storage/providers/minio/index.html) | `S` | Shared provider frontpage + integrated tabs/registry + coverage; registration provider-owned | Coverage/Registry, permission and empty, filter/HTMX | NOT RUN |
| C159 | MinIO Integration · Instance Detail | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/integrations/storage/object_storage/providers/minio/instance_detail.html) | `D` | #2317: Capability Registry header Clear Filters trails persistent Capability Contracts label in DOM; other framed/detail owners reused | Validation tab, labels/order, runtime/inventory, role | NOT RUN |
| C160 | MinIO Integration · Registration/Edit | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/integrations/storage/object_storage/providers/minio/instance_form.html) | `S` | Approved shared provider registration/edit Hero, action bar, button/toggle/validation; #917 remains parity authority | New/Edit, config error, Test Connection, password preservation | NOT RUN |
| C161 | Object Storage Dashboard · lazy section | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/dashboard/partials/_content.html) | `S` | Shared Operational Dashboard and section_loading; not an executed loading-state assertion | Fast Shell and four tabs | NOT RUN |
| C162 | Object Storage Inventory · Systems filters | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/inventory/systems/partials/_table_card.html) | `S` | Four linked labels/IDs via shared table filter classes and search_field id | Label click and HTMX refresh | NOT RUN |
| C163 | Object Storage Inventory · Buckets filters | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/inventory/buckets/partials/_table_card.html) | `S` | Five linked labels/IDs, shared table shell and clear filters | Label click, page size 5/10 | NOT RUN |
| C164 | Object Storage Analytics · Controls | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_controls.html) | `S` | Shared analytics readiness frame/filter geometry and HTMX indicator; #2098 closed verifier correction | Six views, source ready/blocked | NOT RUN |
| C165 | Object Storage Analytics · Alert Records | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_alert_records.html) | `D` | #2284 existing confirmed DOM order; do not duplicate issue or claim visual failure | Clear Filters first in source order | NOT RUN |
| C166 | Object Storage Analytics · Bucket Records | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_bucket_table.html) | `R` | Shared table classes but lacks descriptive caption unlike forecast peer; THEAD th scope inferred; inspect AT naming | Capacity/Performance/Top Consumers | NOT RUN |
| C167 | Object Storage Analytics · Bucket Forecast | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/storage/object_storage/analytics/partials/_bucket_forecast_table.html) | `S` | Shared filter and pagination, accessible label IDs and explicit table caption | Watch/history filters, zero/error | NOT RUN |
| C168 | MinIO Integration · Capability Registry | [source](https://github.com/OXY7O/KAORI/blob/7bf8739e62974b1b375d4dd6c90cdfc1ce4cb088/app/templates/integrations/storage/object_storage/providers/minio/partials/_capability_registry.html) | `D` | #2317 existing shared Clear Filters DOM order; UI visual order may be corrected by order-first CSS | Status/Requirement/Search, DOM vs visual | NOT RUN |

### Canonical and accepted boundaries

- **Dashboard:** #923/#753 and `docs/design/patterns/OPERATIONAL_DASHBOARD.md` define operational Hero, shared KPI/section loading, bounded reads and tabs. Do not replace with Analytics-specific cards or loader.
- **Inventory:** `docs/design/patterns/OBJECT_STORAGE_INVENTORY.md` and #946 own the approved Snapshot → Fleet Inventory Posture → Inventory Assets hierarchy. Systems/Buckets are read-only committed snapshots and open the existing Full Workspace Resource Detail. Do not infer a healthy state from missing/partial provider evidence or create a new embedded provider-management UI.
- **Analytics:** #1114/#1122, shared Analytics readiness/controls, Content Tabs, load tracker, fail-closed dependencies and provider-neutral Metrics Source/JobExecution are authoritative. The six page_keys are separate views of one entry template, not six independent top-level files. Alertmanager lifecycle records and metric-derived signals retain separate source authority.
- **MinIO provider integration:** #916/#917, shared provider frontpage, Framed Workspace Tabs, registration/edit action buttons, validation and lifecycle modal owners. No credential, token, provider operation or connection mutation occurs in audit. Integration instance and external MinIO remain authoritative.
- **Semantic table R candidate:** `_bucket_table.html` shares its styling and THEAD/TH markup but lacks an explicit `<caption>`, unlike `_bucket_forecast_table.html` and Inventory tables. Since THEAD's TH association can be inferred by browsers and accessible names can depend on surrounding labelled regions, **do not call this an assistive-technology FAIL without rendered/AT evidence**. If confirmed, create a small regression-backed child issue; do not rewrite the table.

### Existing confirmed work / remediation separation

| Existing issue | Scope and current evidence | Status |
| --- | --- | --- |
| [#2284](https://github.com/OXY7O/KAORI/issues/2284) | Analytics → Alerts & Anomalies → Provider Alert Records; clear-first header source order | **D / SOURCE FAIL**, OPEN; no remediation in #2411 |
| [#2317](https://github.com/OXY7O/KAORI/issues/2317) | MinIO → Instance Detail → Validation & Capabilities; shared clear-first provider header source order; other providers share issue | **D / SOURCE FAIL**, OPEN; no remediation in #2411 |
| [#946](https://github.com/OXY7O/KAORI/issues/946) | Inventory Overview accepted grouped hierarchy; final layout/contrast review | **R / Visual QA PENDING** |
| [#923](https://github.com/OXY7O/KAORI/issues/923) | Shared Operational Dashboard presentation/loader integration | **S source**, browser acceptance pending |
| [#1114](https://github.com/OXY7O/KAORI/issues/1114), [#1122](https://github.com/OXY7O/KAORI/issues/1122) | Shared Analytics tracker, readiness, cross-domain presentation | **S source**, runtime and browser QA pending |
| [#1199](https://github.com/OXY7O/KAORI/issues/1199), [#917](https://github.com/OXY7O/KAORI/issues/917), [#916](https://github.com/OXY7O/KAORI/issues/916) | Inventory title Info Tips; integration edit and detail parity | Existing authorities; do not duplicate |

### Executable UAT handoff (not yet executed)

Use **existing** Dev Container/browser QA and test runners (#1726, #1738, `tests/ui/visual_audit.py`, `tests/ui/conftest.py` and focused existing contract suites), not a new verifier. Test **1440×900, 1280×800, 1024×768, 768×1024, 390×844, 360×800** in both light/dark, with keyboard, text zoom and reduced motion. Capture route/view, selected provider/system, role, pinned exact SHA, screenshot/trace, expected/actual, test result and human decision.

1. Dashboard: blocked/no provider, fresh/stale evidence, Fast Shell KPIs and four tab HTMX request/indicator/swap focus.
2. Inventory: Overview 4-signal posture and responsive two-asset catalog; Systems/Buckets 9-column wide scroll, title Info Tip, label click, filter/search/clear, row default 5 and page 10, full detail modal focus/deep-link, partial/pending/observed-zero distinctions.
3. Analytics: all six views and each active Content Tab; readiness/source failure; Metrics Source/Alertmanager evidence boundaries; bucket/forecast/alert pagers and HTMX retained scope; verify #2284 DOM reading order, Bucket Records accessible name/header announcements and 360px table overflow.
4. MinIO Integration: Provider Landing/Registry, Add/Edit (validate without persisting secrets), detail Configuration/Validation/Runtime/Inventory & Lifecycle; verify #2317 DOM reading order, capability filters/pager, empty Observability binding footer, RBAC and destructive-confirmation cancel only.
5. No unsafe external provider mutation for screenshot acceptance. Any data-changing test requires a specifically authorized test fixture/target and separately captured evidence.

**Recorded execution:** GitHub source/path and issue-authority inspection **DONE**; Jinja, pytest, djlint, verifiers, browser Playwright, AT, screenshots, external provider and human acceptance **NOT RUN**. **Official CI/CD, Full Admission, `kaori/staging`, `main`, deploy/release remain HOLD.** This is audit before remediation, with product templates/CSS/JS unchanged.

## 4. Visual QA execution plan — existing harness only

### 4.1 Environment preflight (NOT EXECUTED)

1. Checkout the **accepted candidate exact head** in a local Dev Container, not the holding branch by accident. Record `git rev-parse HEAD` and `git status --short`. Never change `kaori/staging` or `main` as part of this exercise.
2. Run a development server from the existing repository instructions with safe test fixtures, approved auth/role personas and deterministic committed-state examples. **Do not use production provider credentials or perform destructive provider operations** to produce a visual state.
3. Resolve active route names and seed-backed object IDs from the running app. `tests/ui/visual_audit.py::build_visual_surface_inventory()` is the canonical surface-inventory authority: deterministic, parameterized and runtime-dependent classification must remain visible.
4. Reuse `tests/ui/conftest.py::CANONICAL_VIEWPORTS` without copying breakpoint values into new test utilities. Switch light/dark using the actual KAORI operator theme control.
5. Preserve `KAORI_UPDATE_VISUAL_BASELINES` **unset**; screenshots must not overwrite `tests/ui/baselines/authenticated-visual.json`. Do not invoke `.github/workflows/ui-visual-baseline-capture.yml` as part of local Dev Container review.

### 4.2 Viewport/theme coverage

| Viewport | Dimensions | Light | Dark |
| --- | ---: | --- | --- |
| large-desktop | 1440 × 900 | NOT RUN | NOT RUN |
| laptop | 1280 × 800 | NOT RUN | NOT RUN |
| compact-laptop | 1024 × 768 | NOT RUN | NOT RUN |
| tablet | 768 × 1024 | NOT RUN | NOT RUN |
| mobile | 390 × 844 | NOT RUN | NOT RUN |
| small-mobile | 360 × 800 | NOT RUN | NOT RUN |

Run the **full 12-combination matrix** on representative deterministic surfaces, then expand to parameterized/runtime-dependent surfaces with recorded fixture prerequisites. Missing fixtures are `NOT RUN`, never PASS. Do not silently narrow to only mobile/desktop.

### 4.3 Controlled state/interaction batches

| Batch | Surface selection | Preconditions & operation | Required assertion | Expected evidence | Status |
| --- | --- | --- | --- | --- | --- |
| A — Action hierarchy | Reports Templates, Notification Channels, Tenant dialog, common resource actions | Fixture has viewer and manager; hover/tab without submitting destructive operation | Primary/secondary/Critical appropriate; row compact vs modal workflow; disabled/accessibility; no action shift | Light/dark desktop+phone screenshots, focus trace, issue #2275/#2276/#2283/#2290/#2292 | NOT RUN |
| B — Table geometry | Access Roles, Kubernetes Node Inventory, Object Storage Bucket, Generated Reports | Fixture with multi-row + long values, empty results and enough records for pagination | Page never scrolls horizontally; table may own bounded horizontal scroll; action/header alignment | Geometry output via existing `visual_audit.py`, screenshots at 6 viewports | NOT RUN |
| C — Filters / pagination | Kubernetes Inventory, Integrations Capability, Object Storage Alert Records | Search, clear, 5→10 rows, zero state, page >1 → new filter | Page resets to 1; per_page persists; Clear first; zero-state footer; stale responses do not win | HTML state/query and existing browser trace | NOT RUN |
| D — Hero / Context | Welcome, Identity Provider, Jobs, Reports Storage | Normal, setup-blocked, long context and permission-limited scopes | One-line description for 768px+; natural phone wrapping; stable Action/Context | Shared Hero assertions and screenshots, no unreviewed baseline update | NOT RUN |
| E — Tabs / Navigation | Identity Providers, Analytics, Tenant Operations, Reports Storage | Mouse and keyboard; URL reload/back/forward; disabled/permission variants | ARIA-selected/current, panel visibility, Left/Right/Home/End, focus, no leaking hidden tab content | Browser trace across 6 viewports + light/dark | NOT RUN |
| F — Forms | Report Generate wizard, Tenant Group edit, Notification Channel config | Valid/invalid required fields, cancel and no-JS read-only fallback | Error retained, permission guards unchanged, no duplicate primary, stable loading | Safe fixture recording + screenshot and contract note | NOT RUN |
| G — Dialog / Drawer | Resource detail, Tenant More, Intelligence routing editor, destructive confirmation | Open, Tab/Shift+Tab, Escape, close, nested action without committing | Focus contained and returned; Critical consequence visible; dark/mobile accessible | Browser trace and screenshots with dialog opened and focus indicator | NOT RUN |
| H — Cards / States | Kubernetes/Object Storage KPI, Access summary, blocked/empty source | Seed normal, no data, filtered no-result, source-not-configured, dependency unavailable | Correct semantic empty/blocked/error; no duplicate card grammar; no invented readiness | 12 theme/viewport snapshots for deterministic fixture; issue notes | NOT RUN |
| I — Loading / Feedback | Kubernetes Analytics, Jobs Active Work, Reports Generated, provider registry | Simulate safe delayed section and rejected/no-permission response via test-owned fixture | Indicator belongs to target; no hero jump; reduced motion; toast severity & feedback/audit evidence | Existing trace, DOM ARIA, screenshot, feedback/audit evidence where safe | NOT RUN |

### 4.4 Existing command entry points (illustrative; **NOT RUN**)

Run inside the **existing** KAORI Dev Container after the environment is prepared; do not run official admission workflows for this holding-branch review:

```bash
# Focused contract inspection using existing suites
python -m pytest -q tests/contracts/design/test_ui_style_shared_ownership_contract.py
python -m pytest -q tests/contracts/design/test_kaori_empty_state_standard_contract.py
python -m pytest -q tests/contracts/integrations/test_framed_workspace_tabs_overflow_contract.py
python -m pytest -q tests/contracts/reports/test_shared_content_tabs_contract.py

# Existing representative Playwright suite uses tests/ui/conftest.py fixtures.
# It may SKIP or fail without the configured KAORI browser host and dependencies.
python -m pytest -q tests/ui/test_representative_interactions.py tests/ui/test_accessibility_disclosures.py

# Existing source verifiers if separately authorized for local-only diagnostic checks:
python scripts/verify_ui_reuse.py
python scripts/verify_ui_style.py
python scripts/verify_sidebar_navigation_standard.py
python scripts/verify_operational_feedback_coverage.py
```

Existing evidence output paths (only after a real run): `tmp/ci-artifacts/test-output/ui-browser/` with screenshot and `*-trace.zip` as produced by the existing harness, plus `visual-audit-report.json` and `visual-audit-report.md`. No artifacts were produced by this document-only change.

### 4.4a Exact-head executable pilot and non-deterministic gap

**Preflight reviewed at work-branch HEAD `767af749a91760459cc2d69049ab4ab8f99be71a`.** The QA harness, Dev Container recipe and test entrypoints below are existing repository sources; **none has been executed in this GitHub-only session**. Run only inside the local KAORI Dev Container after an operator confirms safe test-owned resources.

**Actual deterministic coverage boundary:** `tests/ui/visual_audit.py::DETERMINISTIC_VISUAL_SURFACES` currently contains **Welcome**, **Settings General**, and **Notification Center** only. `tests/ui/conftest.py` supplies a patched `kaori_authenticated_base_url` local Flask server and a separate unready authentication local server, so the following pilot does *not* require production provider credentials or a live external KAORI endpoint. Browser dependencies and Playwright binaries must still be installed in Dev Container; runtime startup and tests remain unverified here.

```bash
# From /workspace/kaori in the existing Dev Container
git rev-parse HEAD
git status --short
# Inspect collection before execution; do not count SKIP as PASS
python -m pytest --collect-only -q \
  tests/ui/test_representative_interactions.py \
  tests/ui/test_accessibility_disclosures.py \
  tests/ui/test_runtime_state_responsiveness.py

# Phase 1: isolated deterministic 6-viewport pilot, with real screenshot/trace on run
python -m pytest -q --maxfail=1 \
  tests/ui/test_representative_interactions.py::test_deterministic_visual_surface_catalog_light_and_dark \
  tests/ui/test_representative_interactions.py::test_representative_filter_pagination_and_form_controls \
  tests/ui/test_representative_interactions.py::test_reduced_motion_keeps_shared_loading_and_overlay_state_without_animation \
  tests/ui/test_accessibility_disclosures.py::test_side_drawer_controller_contains_and_restores_focus_across_viewports \
  tests/ui/test_runtime_state_responsiveness.py::test_authentication_readiness_state_is_responsive_and_traceable
```

**Pilot-to-batch mapping:** deterministic visual catalog supports representative **B/D/H** geometry/state review, notification filters support **C**, reduced-motion and HTMX feedback support **I**, side-drawer focus supports **G**, and login prerequisite failure supports **H**. It **does not** exercise complete real-world **A/F**, Notification Channels Create/Edit, Reports Generate, Tenant high-risk workflow, multi-source committed evidence, or external provider admission; mark these **NOT RUN** until test-owned fixtures and safe runner authority are supplied.

**External-endpoint distinction:** `tests/ui/test_browser_smoke.py` and `tests/ui/test_visual_regression.py` consume `KAORI_UI_BASE_URL` and may **SKIP** without it. Do not claim an external smoke PASS from the deterministic in-process suite; likewise do not point the browser at production to fill this gap. The existing Dev Container configuration forwards Flask port 5000 but does not itself constitute running evidence.

**Required human handoff per pilot result:** save actual `tmp/ci-artifacts/test-output/ui-browser/` screenshots/traces, exact commit, Playwright/Python result summary, six viewport names, theme and RBAC persona where applicable, linked C### rows and issue authority. Missing browser install, missing fixtures, collected-zero tests, exceptions or any SKIP must be reported individually as `NOT RUN`, `BLOCKED`, or a real failure—not rewritten into `PASS`. Keep `KAORI_UPDATE_VISUAL_BASELINES` unset; no GitHub CI workflow trigger.

**Broader nine-batch follow-up:** use #1726 for new interactive browser coverage and #1738 for scenario authority; add tests only on their dedicated implementation work branches. Keep this #2296 PR documentation-only; do not silently add integration providers, mutations or a second runner to this PR.

### 4.5 Evidence recording and acceptance

For each executed row/batch, append a result using this exact structure in the relevant issue evidence, without mutating the static source-audit classification:

| Field | To record after execution |
| --- | --- |
| Source exact head | `git rev-parse HEAD` |
| Surface / scenario | Row C### plus route/fixture/role |
| Device and theme | Canonical viewport name and Light/Dark |
| Test result | **PASS**, **Needs refinement**, or **Broken** per `KAORI_VISUAL_QA.md`; `NOT RUN` while unexecuted |
| Assertion | Geometry / keyboard / state / no-JS / semantic authority |
| Browser artifacts | Actual screenshot/trace/report filename and location, not inferred |
| Linked issue | Current owner or new bounded defect authority |
| Human acceptance | Explicit reviewer decision and reason; blank until reviewed |

**Guardrails:** `PASS` requires executable/observed evidence; `Needs refinement` is for usable but unaccepted visual composition; `Broken` requires a reproducible failed invariant. A failing provider mutation, access denial or unavailable dependency must not be relabelled as a healthy empty state. Do not create a new role, stylesheet, tab style, driver, visual baseline or QA framework for this audit.

## 5. Existing issue backlog and intentional boundaries

| Issue | Scope | Responsibility |
| --- | --- | --- |
| [#2270](https://github.com/OXY7O/KAORI/issues/2270) | Table/header action audit | Report broader inventory and canonical owner coverage |
| [#2275](https://github.com/OXY7O/KAORI/issues/2275) | Reports Template actions | Local primary, modal and row icon anatomy |
| [#2276](https://github.com/OXY7O/KAORI/issues/2276) | Tenant Credential/Access Grant dialogs | Compact table helper inside workflow mutation dialog |
| [#2277](https://github.com/OXY7O/KAORI/issues/2277) | Shared destructive confirmation | Focus, active and disabled state contract |
| [#2283](https://github.com/OXY7O/KAORI/issues/2283) | Notification Channel header | Setup Guide/Add Channel ownership |
| [#2284](https://github.com/OXY7O/KAORI/issues/2284) | Object Storage Alerts header | Clear Filters before persistent context labels |
| [#2290](https://github.com/OXY7O/KAORI/issues/2290) | Tenant Group edit dialog | Save/Cancel local styling |
| [#2291](https://github.com/OXY7O/KAORI/issues/2291) | Data Lifecycle direct action | Save Policy / Archive & Cleanup; preserve archive safety |
| [#2292](https://github.com/OXY7O/KAORI/issues/2292) | Notification Channel modals | Guide and config footer action geometry |
| [#2293](https://github.com/OXY7O/KAORI/issues/2293) | Intelligence policy modals | Routing, deployment, safety action state semantics |
| [#2295](https://github.com/OXY7O/KAORI/issues/2295) | Kubernetes Analytics Overview loading | Local skeleton delegates to an approved owner |
| [#404](https://github.com/OXY7O/KAORI/issues/404) | Closed exception | Preserve normal bound-source navigation and Critical provider Delete |
| [#1329](https://github.com/OXY7O/KAORI/issues/1329) | Approved Access composition | Activity Audit overview as Identity Provider layout reference |
| [#943](https://github.com/OXY7O/KAORI/issues/943) | Shared Operational Dashboard loading | Do not conflate with separate Analytics section-load tracker #1106 |
| [#1738](https://github.com/OXY7O/KAORI/issues/1738) | Acceptance scenario backfill | Link rather than duplicate 91 scenario-case register |

## 6. Current checkpoint and release boundary

- **Implemented in this work item:** issue-scoped documentation; source review of pinned paths and existing test references. No product behavior change.
- **Not implemented:** any source fix associated with the defect issues above, custom QA script, new design family, or modified visual baseline.
- **Not executed:** Local Dev Container, Python tests, `djlint`, Playwright, accessibility/DAST checks, Developer Check, Full Admission, staging deployment, UAT/human acceptance, main promotion or release.
- **Next authorised execution context:** open the review candidate in a running Dev Container with seed-backed deterministic fixtures, run existing browser tests and structured manual scenario batches, attach actual evidence and only then update the matrix findings/issue acceptance.
- **GitHub Project metadata:** assign the task and PR to KAORI Project and current existing Type/Status/Priority/Sprint/Story Point values via native Project controls if the connector cannot set them; no new taxonomy.

---

Document owner: KAORI Design System v2 (#572). Audit snapshot is immutable; rerun source audit and update the pinned SHA if the candidate branch or target source changes before acceptance.
