# KAORI Reusable Components — Page/State Conformance Matrix

> **Audit candidate — source inventory, not executed Visual QA.** Original 2026-10-17 snapshot plus 2026-10-18 exact-head addendum. Do not treat historical row links as current-head QA. Work authority [#2296](https://github.com/OXY7O/KAORI/issues/2296); Design System [#572](https://github.com/OXY7O/KAORI/issues/572); focused table-action audit [#2270](https://github.com/OXY7O/KAORI/issues/2270).

| Field | Pinned value |
| --- | --- |
| Source branch | `kaori/review/staging-uat` |
| Audited baseline | `1c110073c947bf3444e996794e8a1734d4007bda` |
| Proposed evidence branch | `kaori/task-2296-ui-conformance-matrix-uat` |
| Work type | Documentation + execution plan; **no visual/product implementation** |
| Current addendum holding SHA | `4aa8d2641c775f99eaf130974529125fba99ef0e` (supplemental C074–C088 only) |
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
