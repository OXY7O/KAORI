#!/usr/bin/env python3
"""Fail when direct-cutover files or generated archive artifacts return."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OBSOLETE_PATHS = (
    'app/static/js/analytics_capacity.js',
    'app/static/js/analytics_forecast.js',
    'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_operation_feedback_oob.html',
    'app/templates/kubernetes/analytics/alerts/partials/_pagination.html',
    'app/templates/kubernetes/analytics/alerts/partials/_source_status.html',
    'app/templates/analytics/components/_controls.html',
    'app/templates/analytics/components/_overview_surfaces.html',
    'app/templates/kubernetes/analytics/forecast/partials/_methodology.html',
    'app/templates/kubernetes/analytics/overview/partials/_empty_state.html',
    'app/templates/kubernetes/analytics/overview/partials/_metrics_source_status_loading.html',
    'app/templates/kubernetes/analytics/storage/partials/_persistent_pagination.html',
    'app/templates/kubernetes/analytics/storage/partials/_record_pagination.html',
    'app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_pagination.html',
    'app/templates/kubernetes/analytics/workload/partials/_record_pagination.html',
    'app/templates/components/footer.html',
    'app/templates/components/navigation/_operation_feedback_oob.html',
    'app/templates/components/navigation/_quick_sync_result.html',
    'app/templates/kubernetes/operations/_components.html',
    'app/templates/kubernetes/operations/configmaps/_operation_notification.html',
    'app/templates/kubernetes/governance/tls_certificates/partials/_operation_feedback_oob.html',
    'app/templates/kubernetes/governance/tls_certificates/partials/_sync_toast_oob.html',
    'app/templates/kubernetes/governance/tls_certificates/partials/_inventory_scope.html',
    'app/templates/kubernetes/governance/tls_certificates/partials/_content.html',
    'app/kubernetes/governance/tls_certificates/toast.py',
    'app/templates/kubernetes/governance/tls_certificates/partials/_sync_toast.html',
    'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_history.html',
    'app/templates/integrations/partials/_binding_validation_posture.html',
    'app/templates/integrations/partials/_status_badge.html',
    'app/templates/platform_operations/jobs/executions/partials/_hero_context_metrics.html',
    'app/templates/platform_operations/jobs/executions/partials/_hero_metadata.html',
    'app/templates/integrations/observability/metrics_source/partials/_validation_response.html',
    'app/templates/reports/overview/partials/_recommended_actions.html',
    'app/templates/settings/reports/index.html',
    'app/templates/settings/reports/partials/_placeholder.html',
    'docs/design/components/ANALYTICS_OVERVIEW_SURFACES.md',
    'tests/contracts/analytics/test_alerts_alert_column_width_hotfix_contract.py',
    'tests/contracts/analytics/test_alerts_auto_htmx_filters_hotfix_contract.py',
    'tests/contracts/analytics/test_alerts_cluster_overview_ownership_resources_tabs_contract.py',
    'tests/contracts/analytics/test_alerts_cluster_overview_refinement_contract.py',
    'tests/contracts/analytics/test_alerts_compact_ownership_and_anomaly_labels_contract.py',
    'tests/contracts/analytics/test_alerts_filter_scope_and_search_icon_hotfix_contract.py',
    'tests/contracts/analytics/test_alerts_filter_tabs_and_details_contract.py',
    'tests/contracts/analytics/test_alerts_hero_context_hotfix_contract.py',
    'tests/contracts/analytics/test_alerts_pagination_cluster_hydration_hotfix_contract.py',
    'tests/contracts/analytics/test_alerts_readiness_and_sections_refinement_contract.py',
    'tests/contracts/analytics/test_alerts_records_workspace_refinement_contract.py',
    'tests/contracts/analytics/test_alerts_severity_state_two_row_contract.py',
    'tests/contracts/analytics/test_alerts_signal_semantics_and_readiness_layout_contract.py',
    'tests/contracts/analytics/test_alerts_table_filter_and_action_refinement_contract.py',
    'tests/contracts/analytics/test_alerts_table_structure_pagination_and_controls_contract.py',
    'tests/contracts/analytics/test_alerts_tabs_and_anomaly_namespace_contract.py',
    'tests/contracts/analytics/test_alerts_workspace_presentation_contract.py',
    'tests/contracts/analytics/test_forecast_capacity_guidance_and_legend_spacing_contract.py',
    'tests/contracts/analytics/test_forecast_chart_redesign_contract.py',
    'tests/contracts/analytics/test_forecast_combined_chart_guidance_contract.py',
    'tests/contracts/analytics/test_forecast_layout_density_redesign_contract.py',
    'tests/contracts/analytics/test_forecast_overview_methodology_compact_contract.py',
    'tests/contracts/analytics/test_forecast_trend_analysis_redesign_contract.py',
    'tests/contracts/analytics/test_forecast_trend_compact_redesign_contract.py',
    'tests/contracts/analytics/test_forecast_workspace_controls_tabs_hotfix_contract.py',
    'tests/contracts/analytics/test_top_consumers_cluster_tab_and_loading_hotfix_contract.py',
    'tests/contracts/analytics/test_top_consumers_namespace_pod_identity_contract.py',
    'tests/contracts/analytics/test_top_consumers_snapshot_and_alert_tab_scroll_hotfix_contract.py',
    'tests/contracts/analytics/test_top_consumers_workspace_redesign_contract.py',
)

GENERATED_ROOT_FILES = ('OX.zip',)


def main() -> int:
    violations = [path for path in OBSOLETE_PATHS if (ROOT / path).exists()]
    violations.extend(path for path in GENERATED_ROOT_FILES if (ROOT / path).exists())
    cache_dirs = [path for path in ROOT.rglob('__pycache__') if path.is_dir()]
    compiled = [*ROOT.rglob('*.pyc'), *ROOT.rglob('*.pyo')]
    if violations or cache_dirs or compiled:
        print('Obsolete/generated files detected:')
        for path in violations:
            print(f'- {path}')
        for path in cache_dirs:
            print(f'- {path.relative_to(ROOT)}')
        for path in compiled:
            print(f'- {path.relative_to(ROOT)}')
        return 1
    print('Obsolete-file audit passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
