# Kubernetes Analytics UI Audit and Redesign

Date: 27 July 2026  
Scope: Resource Utilization, Capacity Analysis, Storage Analysis, Workload Analysis, Resource Forecast, Top Consumers, and Alerts & Anomalies.

## Outcome

This change standardizes the seven Kubernetes Analytics pages on the KAORI component and interaction patterns, fixes the Resource Utilization tab/progress behavior, removes requested expandable recommendation containers, and reduces duplicated page-local frontend logic.

No database migration, route-retention change, permission change, or deployment topology change is included.

The uploaded source archive does not contain `.git` metadata, so a Git commit could not be created in this workspace. Suggested commit message: `fix(analytics): standardize Kubernetes analytics interactions and layouts`.

## Functional Fixes

- Resource Utilization tabs now retain the active tab across HTMX page replacement by using the URL hash and session storage.
- Changing the selected cluster clears stale node-scoped filters before the HTMX request is submitted.
- Current Resource Utilization and node-detail bars now render the selected semantic class correctly. The former quoted class expression emitted literal Jinja text instead of the computed class.
- Progress widths and progress-ring values are hydrated by the shared Analytics controller after initial load and HTMX swaps.
- Capacity headroom ignores resources without a valid capacity baseline when determining the lowest-headroom posture. Missing storage capacity is represented as Unknown instead of a false Critical state.

## Reusable UI Changes

- Added `analytics/kubernetes/components/_prometheus_status.html` as the shared Prometheus Status component used by Analytics Overview and the redesigned pages.
- Added `analytics/components/_controls.html` for Forecast, Consumer, and Alert control surfaces.
- Consolidated Analytics tab initialization and persistence in `app/static/js/kubernetes/analytics/controls.js`.
- Removed template inline width styles from the shared progress component.
- Externalized Capacity and Forecast chart behavior into dedicated static modules.
- Removed obsolete Top Consumers chart code that targeted canvases and payloads no longer present in the rendered page.

## Page Changes

### Resource Utilization

- Fixed cluster-filter/tab behavior and progress-bar rendering.
- Standardized Prometheus Status with Analytics Overview.
- Kept Utilization Summary, Trend Analysis, Node Detail, and Recommendations as top-level content tabs.
- Removed expandable recommendation presentation.
- Replaced chart color literals with KAORI design tokens.

### Capacity Analysis

- Redesigned Worker Capacity Summary.
- Added a CPU/Memory — allocation pie — Pods/Storage composition.
- Added Storage to capacity risk/headroom analysis while keeping allocation datasets limited to CPU, Memory, and Pods.
- Redesigned Capacity Risk Summary and removed expandable recommendations.

### Storage Analysis

- Moved Capacity & Utilization, Node Filesystem, Persistent Storage, and Recommendations to the top-level Analytics tab position.
- Redesigned all storage sections without nested expandables.
- Standardized Prometheus Status.

### Workload Analysis

- Redesigned Tenant Quota Analysis and Workload Resource Mapping.
- Standardized progress rendering and Prometheus Status.
- Removed expandable recommendations and duplicate page-local hydration logic.

### Resource Forecast

- Redesigned Forecast Controls using the shared control surface.
- Moved Forecast Methodology directly below controls and outside content tabs.
- Redesigned Forecast Overview, Trend Analysis, and Recommendations.
- Externalized chart behavior and removed expandable recommendations.

### Top Consumers

- Redesigned Consumer Controls and Top Consumer Summary.
- CPU and Memory rankings now render together on one overview page instead of nested CPU/Memory tabs.
- Redesigned Consumer Detail and Recommendations.
- Removed obsolete Chart.js initialization that no longer had matching chart elements.

### Alerts & Anomalies

- Redesigned Alert Controls, Signal Control & Source Health, routing/suppression, ownership/readiness, and recommendations.
- Removed requested expandable presentation.
- Standardized title casing and semantic panel structure.

## Code and Legacy Audit

- No active compatibility package, route-retention shim, or analytics `warp` layer was found.
- One backward-compatible snapshot decoding branch remains in `app/kubernetes/analytics/materialization/serialization.py`. It is intentionally retained because it reads previously committed snapshots that predate embedded cluster metadata and does not return ORM entities into the presentation context.
- Existing Analytics load trackers remain page-specific because they implement polling/completion behavior rather than static metric progress; they are not duplicates of the shared metric-bar hydrator.
- Python cache files and test cache files are excluded from the delivered archives.
- The UI inline-debt baseline was reduced for templates whose inline script/style debt was removed. One already-resolved Inventory baseline entry was also removed so the repository UI reuse gate reflects the current source tree.

## Validation

Passed:

- `python scripts/verify_python_syntax.py` — 612 Python source files.
- Jinja parser validation — 71 Analytics/component templates.
- `node --check` — `analytics_controls.js`, `analytics_capacity.js`, and `analytics_forecast.js`.
- Shared Jinja behavior checks for dynamic progress classes and Prometheus status states.
- `python scripts/verify_ui_reuse.py` — zero inline styles and reduced inline script debt.
- `node scripts/verify_frontend_assets.mjs` — pinned frontend assets and local font verified.
- Targeted contract tests — 7 passed.
- Tab/panel mapping check for all seven redesigned pages.
- No `<details>` or `<summary>` elements remain in the seven target page trees.
- No hard-coded color literals remain in the modified target Analytics templates or JavaScript modules.

Environment limitation:

- The complete Flask-dependent test suite could not be collected in the provided sandbox because Flask is not installed. The same source archive already fails the repository code-health and architecture-boundary gates before this patch; comparison of original and updated outputs showed no additional failures or changed debt from this work.

## Deployment and Rollback

Deployment:

1. Apply the patch files or deploy the full updated source archive.
2. Restart the KAORI web process and Analytics worker processes because Capacity service/presentation code changed.
3. Confirm static assets are served from the updated source and perform a browser hard refresh if a proxy or browser caches JavaScript aggressively.
4. Validate each page with at least two clusters and switch tabs before and after changing the cluster filter.

Rollback:

- Restore the same paths from the original `MI.zip` archive and restart the web/worker processes.
- No database rollback or Alembic downgrade is required.

## Changed Files

- `app/kubernetes/analytics/capacity/service.py`
- `app/analytics/common/presentation.py`
- `app/static/js/analytics_capacity.js`
- `app/static/js/kubernetes/analytics/controls.js`
- `app/static/js/analytics_forecast.js`
- `app/templates/kubernetes/analytics/alerts/index.html`
- `app/templates/kubernetes/analytics/alerts/partials/_cluster_signal_overview.html`
- `app/templates/kubernetes/analytics/alerts/partials/_filters.html`
- `app/templates/kubernetes/analytics/alerts/partials/_hero.html`
- `app/templates/kubernetes/analytics/alerts/partials/_incident_readiness.html`
- `app/templates/kubernetes/analytics/alerts/partials/_ownership_summary.html`
- `app/templates/kubernetes/analytics/alerts/partials/_recommendations.html`
- `app/templates/kubernetes/analytics/alerts/partials/_routing_summary.html`
- `app/templates/kubernetes/analytics/alerts/partials/_silence_inhibition_summary.html`
- `app/templates/kubernetes/analytics/alerts/partials/_source_status.html`
- `app/templates/kubernetes/analytics/capacity/index.html`
- `app/templates/kubernetes/analytics/capacity/partials/_hero.html`
- `app/templates/kubernetes/analytics/capacity/partials/_recommendations.html`
- `app/templates/analytics/components/_controls.html`
- `app/templates/kubernetes/analytics/components/_prometheus_status.html`
- `app/templates/kubernetes/analytics/forecast/index.html`
- `app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html`
- `app/templates/kubernetes/analytics/forecast/partials/_methodology.html`
- `app/templates/kubernetes/analytics/overview/partials/_prometheus_status.html`
- `app/templates/kubernetes/analytics/storage/index.html`
- `app/templates/kubernetes/analytics/storage/partials/_filesystem_panel.html`
- `app/templates/kubernetes/analytics/storage/partials/_hero.html`
- `app/templates/kubernetes/analytics/storage/partials/_storage_section.html`
- `app/templates/kubernetes/analytics/top_consumers/index.html`
- `app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_section.html`
- `app/templates/kubernetes/analytics/top_consumers/partials/_hero.html`
- `app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html`
- `app/templates/kubernetes/analytics/utilization/index.html`
- `app/templates/kubernetes/analytics/utilization/partials/_hero.html`
- `app/templates/kubernetes/analytics/utilization/partials/_node_detail.html`
- `app/templates/kubernetes/analytics/utilization/partials/_recommendations.html`
- `app/templates/kubernetes/analytics/utilization/partials/_trend.html`
- `app/templates/kubernetes/analytics/workload/index.html`
- `app/templates/kubernetes/analytics/workload/partials/_hero.html`
- `app/templates/kubernetes/analytics/workload/partials/_recommendations.html`
- `app/templates/kubernetes/analytics/workload/partials/_tenant_quota_section.html`
- `app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html`
- `app/templates/components/progress_bar.html`
- `docs/architecture/ui-inline-debt-baseline.json`
- `docs/reviews/2026-07-27-kubernetes-analytics-ui-audit.md`
- `tests/contracts/analytics/test_materialization_pending_progress_contract.py`
