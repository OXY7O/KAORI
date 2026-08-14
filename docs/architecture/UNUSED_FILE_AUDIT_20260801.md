# KAORI Unused File Audit — 2026-08-01

Status: cleanup approved for the uploaded `CS.zip` source snapshot.

## Scope

The audit checked direct-cutover delete manifests from the Analytics and Integrations standardization patches, exact Jinja/static references, current canonical contracts, generated archive artifacts, and zero-reference Python modules.

## Safe To Delete Now

These files are obsolete because their canonical replacements are already active, current contracts require them to be absent, or they have no runtime/template references.

### Application files (26)

- `app/static/js/analytics_capacity.js`
- `app/static/js/analytics_forecast.js`
- `app/templates/alertmanager/partials/_operation_feedback_oob.html`
- `app/templates/analytics/kubernetes/alerts/partials/_pagination.html`
- `app/templates/analytics/kubernetes/alerts/partials/_source_status.html`
- `app/templates/analytics/components/_controls.html`
- `app/templates/analytics/components/_overview_surfaces.html`
- `app/templates/analytics/kubernetes/forecast/partials/_methodology.html`
- `app/templates/analytics/kubernetes/overview/partials/_empty_state.html`
- `app/templates/analytics/kubernetes/overview/partials/_prometheus_status_loading.html`
- `app/templates/analytics/kubernetes/storage/partials/_persistent_pagination.html`
- `app/templates/analytics/kubernetes/storage/partials/_record_pagination.html`
- `app/templates/analytics/kubernetes/top_consumers/partials/_consumer_detail_pagination.html`
- `app/templates/analytics/kubernetes/workload/partials/_record_pagination.html`
- `app/templates/components/footer.html`
- `app/templates/governance/tls_certificates/partials/_operation_feedback_oob.html`
- `app/templates/governance/tls_certificates/partials/_sync_toast_oob.html`
- `app/templates/integrations/kubernetes/partials/_runtime_history.html`
- `app/templates/integrations/partials/_binding_validation_posture.html`
- `app/templates/integrations/partials/_status_badge.html`
- `app/templates/jobs/executions/partials/_hero_context_metrics.html`
- `app/templates/jobs/executions/partials/_hero_metadata.html`
- `app/templates/prometheus/partials/_validation_response.html`
- `app/templates/reports/overview/partials/_recommended_actions.html`
- `app/templates/settings/reports/index.html`
- `app/templates/settings/reports/partials/_placeholder.html`

### Superseded contract tests (29)

- `tests/contracts/analytics/test_alerts_alert_column_width_hotfix_contract.py`
- `tests/contracts/analytics/test_alerts_auto_htmx_filters_hotfix_contract.py`
- `tests/contracts/analytics/test_alerts_cluster_overview_ownership_resources_tabs_contract.py`
- `tests/contracts/analytics/test_alerts_cluster_overview_refinement_contract.py`
- `tests/contracts/analytics/test_alerts_compact_ownership_and_anomaly_labels_contract.py`
- `tests/contracts/analytics/test_alerts_filter_scope_and_search_icon_hotfix_contract.py`
- `tests/contracts/analytics/test_alerts_filter_tabs_and_details_contract.py`
- `tests/contracts/analytics/test_alerts_hero_context_hotfix_contract.py`
- `tests/contracts/analytics/test_alerts_pagination_cluster_hydration_hotfix_contract.py`
- `tests/contracts/analytics/test_alerts_readiness_and_sections_refinement_contract.py`
- `tests/contracts/analytics/test_alerts_records_workspace_refinement_contract.py`
- `tests/contracts/analytics/test_alerts_severity_state_two_row_contract.py`
- `tests/contracts/analytics/test_alerts_signal_semantics_and_readiness_layout_contract.py`
- `tests/contracts/analytics/test_alerts_table_filter_and_action_refinement_contract.py`
- `tests/contracts/analytics/test_alerts_table_structure_pagination_and_controls_contract.py`
- `tests/contracts/analytics/test_alerts_tabs_and_anomaly_namespace_contract.py`
- `tests/contracts/analytics/test_alerts_workspace_presentation_contract.py`
- `tests/contracts/analytics/test_forecast_capacity_guidance_and_legend_spacing_contract.py`
- `tests/contracts/analytics/test_forecast_chart_redesign_contract.py`
- `tests/contracts/analytics/test_forecast_combined_chart_guidance_contract.py`
- `tests/contracts/analytics/test_forecast_layout_density_redesign_contract.py`
- `tests/contracts/analytics/test_forecast_overview_methodology_compact_contract.py`
- `tests/contracts/analytics/test_forecast_trend_analysis_redesign_contract.py`
- `tests/contracts/analytics/test_forecast_trend_compact_redesign_contract.py`
- `tests/contracts/analytics/test_forecast_workspace_controls_tabs_hotfix_contract.py`
- `tests/contracts/analytics/test_top_consumers_cluster_tab_and_loading_hotfix_contract.py`
- `tests/contracts/analytics/test_top_consumers_namespace_pod_identity_contract.py`
- `tests/contracts/analytics/test_top_consumers_snapshot_and_alert_tab_scroll_hotfix_contract.py`
- `tests/contracts/analytics/test_top_consumers_workspace_redesign_contract.py`

### Replaced design document (1)

- `docs/design/components/ANALYTICS_OVERVIEW_SURFACES.md`

## Generated Artifacts Removed

- root source archive `OX.zip`;
- all `__pycache__/` directories;
- all `.pyc` and `.pyo` files;
- pytest, Ruff, and mypy cache directories when present.

These are local/generated artifacts and must not be included in source ZIP deliveries.

## Architecture Decision Update — 2026-08-10

`app/knowledge/remediation_workflow.py` was formally retired from the current release after module-reachability validation confirmed that it had no runtime import, configured entrypoint, permanent test, or script consumer. Intelligence remediation remains held for a future controlled redesign. Historical Domain 18 documentation is retained only as design history and is explicitly marked non-current.

`app/users/identity.py` was also removed after the same reachability check confirmed that its identity-source helpers were unused and duplicated provider-family ownership already held by the authentication provider catalog.

## Intentionally Retained

- historical audit/review documents under `docs/reviews/` and `docs/design/audits/`;
- supported-provider compatibility modules, because they implement real version lifecycle behavior rather than migration shims;
- dynamic Inventory index templates, whose paths are assembled by `app/inventory/routes.py`;
- canonical shared Analytics and Integrations components.

## Prevention

- `.gitignore` now ignores every ZIP at repository root via `/*.zip`;
- `scripts/verify_obsolete_files.py` fails when deleted files, root `OX.zip`, Python caches, or compiled Python files return;
- `scripts/cleanup_obsolete_files.sh` performs the approved cleanup idempotently.

## Analytics Overview follow-up — 2026-08-05

The following approved legacy files are now removed from the audited source:

- `app/templates/analytics/components/_overview_surfaces.html`
- `app/templates/analytics/kubernetes/overview/partials/_prometheus_status.html`

Analytics Overview now uses `_analysis_surfaces.html` and the Health Summary-owned
canonical Prometheus readiness card. No compatibility wrapper remains.

Additional Analytics legacy removal:

- `app/analytics/common/cache.py`

The Analytics cache module had no importer after Overview was standardized on
worker-owned committed snapshots. It was removed rather than retained as an
unowned Redis/local compatibility layer.
