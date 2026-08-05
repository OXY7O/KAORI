#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

obsolete_paths=(
  'app/static/js/analytics_capacity.js'
  'app/static/js/analytics_forecast.js'
  'app/templates/alertmanager/partials/_operation_feedback_oob.html'
  'app/templates/analytics/alerts/partials/_pagination.html'
  'app/templates/analytics/alerts/partials/_source_status.html'
  'app/templates/analytics/components/_controls.html'
  'app/templates/analytics/components/_overview_surfaces.html'
  'app/templates/analytics/forecast/partials/_methodology.html'
  'app/templates/analytics/overview/partials/_empty_state.html'
  'app/templates/analytics/overview/partials/_prometheus_status_loading.html'
  'app/templates/analytics/storage/partials/_persistent_pagination.html'
  'app/templates/analytics/storage/partials/_record_pagination.html'
  'app/templates/analytics/top_consumers/partials/_consumer_detail_pagination.html'
  'app/templates/analytics/workload/partials/_record_pagination.html'
  'app/templates/components/footer.html'
  'app/templates/components/navigation/_operation_feedback_oob.html'
  'app/templates/components/navigation/_quick_sync_result.html'
  'app/templates/kubernetes_operations/_components.html'
  'app/templates/kubernetes_operations/configmaps/_operation_notification.html'
  'app/kubernetes_operations/secrets/routes.py'
  'tests/kubernetes_operations/test_secret_delete_workflow.py'
  'app/templates/governance/tls_certificates/partials/_operation_feedback_oob.html'
  'app/templates/governance/tls_certificates/partials/_sync_toast_oob.html'
  'app/templates/governance/tls_certificates/partials/_inventory_scope.html'
  'app/templates/governance/tls_certificates/partials/_content.html'
  'app/governance/tls_certificates/toast.py'
  'app/templates/governance/tls_certificates/partials/_sync_toast.html'
  'app/templates/integrations/kubernetes/partials/_runtime_history.html'
  'app/templates/integrations/partials/_binding_validation_posture.html'
  'app/templates/integrations/partials/_status_badge.html'
  'app/static/js/inventory/topology_bootstrap.js'
  'app/dashboards/kubernetes/snapshot_builder.py'
  'app/analytics/common/cache.py'
  'app/templates/inventory/components/_detail_macros.html'
  'app/templates/inventory/namespaces/partials/_inventory_scope.html'
  'app/templates/inventory/nodes/partials/_inventory_scope.html'
  'app/templates/inventory/pods/partials/_inventory_scope.html'
  'app/templates/inventory/services/partials/_inventory_scope.html'
  'app/templates/inventory/ingresses/partials/_inventory_scope.html'
  'app/templates/inventory/configuration/partials/_inventory_scope.html'
  'app/templates/inventory/storage/partials/_inventory_scope.html'
  'app/templates/inventory/workloads/partials/_inventory_scope.html'
  'app/templates/jobs/executions/partials/_hero_context_metrics.html'
  'app/templates/jobs/executions/partials/_hero_metadata.html'
  'app/templates/prometheus/partials/_validation_response.html'
  'app/templates/reports/overview/partials/_recommended_actions.html'
  'app/templates/settings/reports/index.html'
  'app/templates/settings/reports/partials/_placeholder.html'
  'docs/design/components/ANALYTICS_OVERVIEW_SURFACES.md'
  'tests/contracts/analytics/test_alerts_alert_column_width_hotfix_contract.py'
  'tests/contracts/analytics/test_alerts_auto_htmx_filters_hotfix_contract.py'
  'tests/contracts/analytics/test_alerts_cluster_overview_ownership_resources_tabs_contract.py'
  'tests/contracts/analytics/test_alerts_cluster_overview_refinement_contract.py'
  'tests/contracts/analytics/test_alerts_compact_ownership_and_anomaly_labels_contract.py'
  'tests/contracts/analytics/test_alerts_filter_scope_and_search_icon_hotfix_contract.py'
  'tests/contracts/analytics/test_alerts_filter_tabs_and_details_contract.py'
  'tests/contracts/analytics/test_alerts_hero_context_hotfix_contract.py'
  'tests/contracts/analytics/test_alerts_pagination_cluster_hydration_hotfix_contract.py'
  'tests/contracts/analytics/test_alerts_readiness_and_sections_refinement_contract.py'
  'tests/contracts/analytics/test_alerts_records_workspace_refinement_contract.py'
  'tests/contracts/analytics/test_alerts_severity_state_two_row_contract.py'
  'tests/contracts/analytics/test_alerts_signal_semantics_and_readiness_layout_contract.py'
  'tests/contracts/analytics/test_alerts_table_filter_and_action_refinement_contract.py'
  'tests/contracts/analytics/test_alerts_table_structure_pagination_and_controls_contract.py'
  'tests/contracts/analytics/test_alerts_tabs_and_anomaly_namespace_contract.py'
  'tests/contracts/analytics/test_alerts_workspace_presentation_contract.py'
  'tests/contracts/analytics/test_forecast_capacity_guidance_and_legend_spacing_contract.py'
  'tests/contracts/analytics/test_forecast_chart_redesign_contract.py'
  'tests/contracts/analytics/test_forecast_combined_chart_guidance_contract.py'
  'tests/contracts/analytics/test_forecast_layout_density_redesign_contract.py'
  'tests/contracts/analytics/test_forecast_overview_methodology_compact_contract.py'
  'tests/contracts/analytics/test_forecast_trend_analysis_redesign_contract.py'
  'tests/contracts/analytics/test_forecast_trend_compact_redesign_contract.py'
  'tests/contracts/analytics/test_forecast_workspace_controls_tabs_hotfix_contract.py'
  'tests/contracts/analytics/test_top_consumers_cluster_tab_and_loading_hotfix_contract.py'
  'tests/contracts/analytics/test_top_consumers_namespace_pod_identity_contract.py'
  'tests/contracts/analytics/test_top_consumers_snapshot_and_alert_tab_scroll_hotfix_contract.py'
  'tests/contracts/analytics/test_top_consumers_workspace_redesign_contract.py'
)

removed=0
for path in "${obsolete_paths[@]}"; do
  if [[ -e "$path" ]]; then
    rm -f -- "$path"
    printf 'Removed obsolete file: %s\n' "$path"
    removed=$((removed + 1))
  fi
done

# Local/generated artifacts must never be shipped in a source archive.
rm -f -- OX.zip
find . -type d \( \
  -name '__pycache__' -o \
  -name '.pytest_cache' -o \
  -name '.ruff_cache' -o \
  -name '.mypy_cache' \
\) -prune -exec rm -rf -- {} +
find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '.DS_Store' \) -delete

# Remove empty directories left by deleted compatibility pages/partials.
find app/templates/settings/reports -depth -type d -empty -delete 2>/dev/null || true

printf 'Cleanup complete. Removed %d tracked obsolete file(s).\n' "$removed"
