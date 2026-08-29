#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

phase="${1:---all}"

append_test_summary() {
    local status="$1"
    local label="$2"
    local detail="$3"

    if [[ -z "${GITHUB_STEP_SUMMARY:-}" ]]; then
        return 0
    fi

    {
        printf -- '- **%s — KAORI %s**\n' "$status" "$label"
        printf '  - %s\n' "$detail"
    } >>"$GITHUB_STEP_SUMMARY"
}

run_pytest_gate() {
    local pass_label="$1"
    local fail_label="$2"
    local summary_label="$3"
    shift 3

    if pytest -q --tb=short "$@"; then
        printf '\n%s\n' "$pass_label"
        append_test_summary \
            'PASS' \
            "$summary_label" \
            'Pytest completed with concise traceback output; raw command output remains available in the job log.'
        return 0
    else
        local status=$?
        printf '\n%s\n' "$fail_label" >&2
        append_test_summary \
            'FAIL' \
            "$summary_label" \
            'Review the failing test name, assertion or reason, and source path in the job log.'
        return "$status"
    fi
}

run_e2e_gate() {
    if pytest -q tests/e2e -m e2e --tb=short; then
        printf '\nPASS — KAORI End-to-End Tests\n'
        append_test_summary \
            'PASS' \
            'End-to-End Tests' \
            'Explicit E2E smoke layer passed with concise traceback output; raw command output remains available in the job log.'
        return 0
    else
        local status=$?
        printf '\nFAIL — KAORI End-to-End Tests\n' >&2
        append_test_summary \
            'FAIL' \
            'End-to-End Tests' \
            'Review the failing E2E test name, assertion or reason, and source path in the job log.'
        return "$status"
    fi
}

run_static() {
    bash scripts/verify_source_hygiene.sh
    python scripts/verify_release_surface_coverage.py
    python scripts/verify_release_governance.py
    python scripts/verify_environment_contract.py
    python scripts/verify_engineering_standard.py
    python scripts/verify_definition_registry.py
    python scripts/verify_domain_namespace_architecture.py
    python scripts/verify_application_package_architecture.py
    python scripts/verify_welcome_final_lock.py
    python scripts/verify_python_syntax.py
    python scripts/verify_template_dependencies.py
    python scripts/verify_single_pdf_engine.py
    python scripts/verify_analytics_pdf_publication.py
    python scripts/verify_report_generation_contract.py
    python scripts/verify_report_runtime_imports.py
    python scripts/verify_report_job_standard.py
    python scripts/verify_report_storage_resilience.py
    python scripts/verify_tabular_export_standard.py
    python scripts/verify_inventory_final_lock.py
    python scripts/verify_object_storage_inventory_final_lock.py
    python scripts/verify_governance_final_lock.py
    python scripts/verify_kubernetes_operations_final_lock.py
    python scripts/verify_node_inventory_standard.py
    python scripts/verify_namespace_inventory_standard.py
    python scripts/verify_configuration_inventory_standard.py
    python scripts/verify_configmap_management_standard.py
    python scripts/verify_secret_management_standard.py
    python scripts/verify_operational_delivery_policy.py
    python scripts/verify_operational_feedback_coverage.py
    python scripts/verify_access_ownership.py
    python scripts/verify_access_final_lock.py
    python scripts/verify_activity_audit_final_lock.py
    python scripts/verify_identity_provider_architecture.py
    python scripts/verify_authentication_surface_final_lock.py
    python scripts/verify_settings_final_lock.py
    python scripts/verify_intelligence_baseline_lock.py
    python scripts/verify_automation_control.py
    python scripts/verify_tls_certificate_governance_standard.py
    python scripts/verify_workload_inventory_standard.py
    python scripts/verify_pod_inventory_standard.py
    python scripts/verify_service_inventory_standard.py
    python scripts/verify_ingress_inventory_standard.py
    python scripts/verify_storage_inventory_standard.py
    python scripts/verify_core_workspace_legacy_cleanup.py
    python scripts/verify_core_workspace_code_health.py
    python scripts/verify_dark_mode_standard.py
    python scripts/verify_core_workspace_ui_lock.py
    python scripts/verify_core_kubernetes_final_lock.py
    python scripts/verify_platform_operations_final_lock.py
    python scripts/verify_job_progress_final_lock.py
    python scripts/verify_data_lifecycle_final_lock.py
    python scripts/verify_notification_center_final_lock.py
    python scripts/verify_notification_activity_center.py
    python scripts/verify_notification_surface_style.py
    python scripts/verify_integration_provider_foundation.py
    python scripts/verify_integration_domain_navigation.py
    python scripts/verify_minio_object_storage_provider.py
    python scripts/verify_metrics_source_consumer_profiles.py
    python scripts/verify_alertmanager_consumer_profiles.py
    python scripts/verify_integrations_final_lock.py
    python scripts/verify_notification_channels.py
    python scripts/verify_provider_frontpage_consistency.py
    python scripts/verify_hero_component_standard.py
    python scripts/verify_filter_layout_standard.py
    python scripts/verify_title_case_standard.py
    python scripts/verify_integrations_title_case.py
    python scripts/verify_operational_dashboard_standard.py
    python scripts/verify_operational_data_semantics.py
    python scripts/verify_analytics_compact_label_standard.py
    python scripts/verify_analytics_final_lock.py
    python scripts/verify_object_storage_analytics.py
    python scripts/verify_sidebar_navigation_standard.py
    python scripts/verify_application_shell_standard.py
    python scripts/verify_javascript_syntax.py
    python scripts/verify_snapshot_context_bar_standard.py
    python scripts/verify_pre_release_lint_cleanup.py
    python scripts/verify_pre_release_type_safety.py
    python -m ruff check app migrations tests scripts
    python -m ruff format --check app migrations tests scripts
    python -m djlint app/templates --check
    python -m pyright --project pyrightconfig.json
    python scripts/verify_architecture_boundaries.py
    python scripts/verify_internal_import_symbols.py
    python scripts/verify_import_cycles.py
    python scripts/verify_module_reachability.py
    python scripts/verify_celery_topology.py
    python scripts/verify_code_health.py
    python scripts/verify_code_health_baseline_integrity.py
    python scripts/verify_migration_graph.py
    python scripts/verify_test_source_paths.py
    python scripts/verify_test_taxonomy.py
    python scripts/verify_test_domain_architecture.py
    python scripts/verify_feature_test_coverage.py
    python scripts/verify_ui_reuse.py
    python scripts/verify_ui_style.py
    run_pytest_gate \
        'PASS — KAORI Contract & Migration Tests' \
        'FAIL — KAORI Contract & Migration Tests' \
        'Contract & Migration Tests' \
        tests/contracts tests/migrations -m 'contract or migration'
}

run_tests() {
    python scripts/verify_test_prerequisites.py
    run_pytest_gate \
        'PASS — KAORI Functional Tests' \
        'FAIL — KAORI Functional Tests' \
        'Functional Tests' \
        -m 'not debug and not e2e'

    # Domain characterization tests are explicit release gates. This protects
    # them from environment-level PYTEST_ADDOPTS or marker filtering that may
    # otherwise deselect unmarked behavioral tests.
    run_pytest_gate \
        'PASS — KAORI Domain Characterization Tests' \
        'FAIL — KAORI Domain Characterization Tests' \
        'Domain Characterization Tests' \
        tests/welcome \
        tests/access \
        tests/integrations \
        tests/kubernetes/dashboard \
        tests/kubernetes/analytics \
        tests/kubernetes/inventory \
        tests/kubernetes/governance \
        tests/kubernetes/operations \
        tests/storage \
        tests/platform_operations \
        tests/reports \
        tests/settings \
        -m functional

    # Keep the explicit command recognizable to release final-lock verifiers.
    run_e2e_gate
}

run_frontend() {
    npm ci --no-audit --no-fund
    npm run check-format
    npm run build-frontend
    npm run verify-frontend
}

case "$phase" in
    --static)
        run_static
        ;;
    --tests)
        run_tests
        ;;
    --frontend)
        run_frontend
        ;;
    --all)
        run_static
        run_tests
        run_frontend
        ;;
    *)
        printf 'Usage: %s [--static|--tests|--frontend|--all]\n' "$0" >&2
        exit 2
        ;;
esac
