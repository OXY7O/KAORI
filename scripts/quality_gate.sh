#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

phase="${1:---all}"
TEST_OUTPUT_DIR="tmp/ci-artifacts/test-output"
STATIC_OUTPUT_DIR="tmp/ci-artifacts/static-output"

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

record_test_result() {
    local status="$1"
    local label="$2"
    local detail="$3"

    printf '\n%s — KAORI %s · %s\n' "$status" "$label" "$detail"
    append_test_summary "$status" "$label" "$detail"
}

pytest_result_line() {
    local log_file="$1"
    grep -E '(^|[[:space:]])([0-9]+ (passed|failed|error|errors|skipped|deselected)|no tests ran)' "$log_file" \
        | tail -n 1 \
        | sed -E 's/^[[:space:]]+//'
}

print_pytest_failure_excerpt() {
    local log_file="$1"
    local first_failure

    first_failure="$(grep -m1 -E '^FAILED |^ERROR ' "$log_file" || true)"
    if [[ -z "$first_failure" ]]; then
        first_failure="$(grep -m1 -E '^E[[:space:]]|^ERRORS$|^FAILURES$' "$log_file" || true)"
    fi
    if [[ -z "$first_failure" ]]; then
        first_failure='Pytest exited non-zero; inspect the retained raw diagnostic log.'
    fi

    printf 'First actionable failure — %s\n' "$first_failure" >&2
    printf 'Diagnostic excerpt — bounded; full pytest output is retained at %s\n' "$log_file" >&2

    awk '
        /={3,} FAILURES ={3,}/ {capture=1}
        /={3,} ERRORS ={3,}/ {capture=1}
        capture {print; lines++}
        lines >= 60 {exit}
    ' "$log_file" >&2

    printf '%s\n' '--- short test summary info / final output ---' >&2
    tail -n 80 "$log_file" >&2
}

run_pytest_capture() {
    local label="$1"
    shift
    local slug log_file result_line status

    mkdir -p "$TEST_OUTPUT_DIR"
    slug="$(printf '%s' "$label" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9_-')"
    log_file="$(mktemp "$TEST_OUTPUT_DIR/${slug}.XXXXXX.log")"

    if pytest "$@" >"$log_file" 2>&1; then
        result_line="$(pytest_result_line "$log_file" || true)"
        [[ -n "$result_line" ]] || result_line='Pytest completed successfully.'
        record_test_result 'PASS' "$label" "$result_line"
        return 0
    else
        status=$?
    fi

    result_line="$(pytest_result_line "$log_file" || true)"
    [[ -n "$result_line" ]] || result_line="Pytest exited with status $status."
    record_test_result 'FAIL' "$label" "$result_line" >&2
    print_pytest_failure_excerpt "$log_file"
    printf 'Next action — repair the first actionable failure above, then rerun this gate.\n' >&2
    return "$status"
}

run_command_capture() {
    local group="$1"
    local label="$2"
    shift 2
    local slug log_file status first_failure

    mkdir -p "$STATIC_OUTPUT_DIR"
    slug="$(printf '%s-%s' "$group" "$label" | tr '[:upper:] /&' '[:lower:]----' | tr -cd 'a-z0-9_-')"
    log_file="$(mktemp "$STATIC_OUTPUT_DIR/${slug}.XXXXXX.log")"

    if "$@" >"$log_file" 2>&1; then
        return 0
    else
        status=$?
    fi

    first_failure="$(grep -m1 -E '^(FAIL|FAILED|ERROR|E[[:space:]]|[A-Z][0-9]{3}[[:space:]])' "$log_file" || true)"
    [[ -n "$first_failure" ]] || first_failure="Command exited with status $status."
    printf '  FAIL — %s\n' "$label" >&2
    printf 'First actionable failure — %s\n' "$first_failure" >&2
    printf 'Diagnostic excerpt — bounded; full output retained at %s\n' "$log_file" >&2
    tail -n 60 "$log_file" >&2
    printf 'Next action — repair %s, then rerun %s.\n' "$label" "$group" >&2
    return "$status"
}

run_static_group() {
    local group="$1"
    shift
    local group_pass_count=0

    while (( "$#" )); do
        local label="$1"
        local command="$2"
        local status
        shift 2

        if run_command_capture "$group" "$label" bash -lc "$command"; then
            group_pass_count=$((group_pass_count + 1))
        else
            status=$?
            return "$status"
        fi
    done

    printf 'PASS — KAORI %s · %s checks\n' "$group" "$group_pass_count"
    append_test_summary \
        'PASS' \
        "$group" \
        "$group_pass_count checks. Detailed PASS output is retained in $STATIC_OUTPUT_DIR."
}

run_contract_migration_gate() {
    # Canonical contract/migration coverage is executed through run_pytest_capture;
    # semantic equivalent of: pytest -q tests/contracts tests/migrations
    run_pytest_capture \
        'Contract & Migration Safety' \
        -q \
        --tb=short \
        tests/contracts \
        tests/migrations \
        -m 'contract or migration'
}

run_e2e_gate() {
    # Welcome release-evidence semantic equivalent: pytest -q tests/e2e -m e2e
    run_pytest_capture \
        'End-to-End Tests' \
        -q \
        --tb=short \
        --junitxml="$TEST_OUTPUT_DIR/e2e.xml" \
        tests/e2e \
        -m e2e
}

render_test_taxonomy_summary() {
    python scripts/ci_admission.py test-summary \
        --junit "$TEST_OUTPUT_DIR/release-suite.xml" \
        --junit "$TEST_OUTPUT_DIR/e2e.xml"
}

run_static() {
    run_static_group 'Foundation & Governance' \
        'Source Hygiene' 'bash scripts/verify_source_hygiene.sh' \
        'Release Surface Coverage' 'python scripts/verify_release_surface_coverage.py' \
        'Release Governance' 'python scripts/verify_release_governance.py' \
        'Environment Contract' 'python scripts/verify_environment_contract.py' \
        'Engineering Standard' 'python scripts/verify_engineering_standard.py' \
        'Definition Registry' 'python scripts/verify_definition_registry.py' \
        'Domain Namespace Architecture' 'python scripts/verify_domain_namespace_architecture.py' \
        'Application Package Architecture' 'python scripts/verify_application_package_architecture.py' \
        'Welcome Final Lock' 'python scripts/verify_welcome_final_lock.py' \
        'Python Syntax' 'python scripts/verify_python_syntax.py' \
        'Template Dependencies' 'python scripts/verify_template_dependencies.py'

    run_static_group 'Domain & Capability Contracts' \
        'Single PDF Engine' 'python scripts/verify_single_pdf_engine.py' \
        'Analytics PDF Publication' 'python scripts/verify_analytics_pdf_publication.py' \
        'Report Generation Contract' 'python scripts/verify_report_generation_contract.py' \
        'Report Runtime Imports' 'python scripts/verify_report_runtime_imports.py' \
        'Report Job Standard' 'python scripts/verify_report_job_standard.py' \
        'Report Storage Resilience' 'python scripts/verify_report_storage_resilience.py' \
        'Tabular Export Standard' 'python scripts/verify_tabular_export_standard.py' \
        'Object Storage Analytics' 'python scripts/verify_object_storage_analytics.py' \
        'Inventory Final Lock' 'python scripts/verify_inventory_final_lock.py' \
        'Object Storage Inventory Final Lock' 'python scripts/verify_object_storage_inventory_final_lock.py' \
        'Governance Final Lock' 'python scripts/verify_governance_final_lock.py' \
        'Kubernetes Operations Final Lock' 'python scripts/verify_kubernetes_operations_final_lock.py' \
        'Node Inventory Standard' 'python scripts/verify_node_inventory_standard.py' \
        'Namespace Inventory Standard' 'python scripts/verify_namespace_inventory_standard.py' \
        'Configuration Inventory Standard' 'python scripts/verify_configuration_inventory_standard.py' \
        'ConfigMap Management Standard' 'python scripts/verify_configmap_management_standard.py' \
        'Secret Management Standard' 'python scripts/verify_secret_management_standard.py' \
        'Operational Delivery Policy' 'python scripts/verify_operational_delivery_policy.py' \
        'Operational Feedback Coverage' 'python scripts/verify_operational_feedback_coverage.py' \
        'Access Ownership' 'python scripts/verify_access_ownership.py' \
        'Access Final Lock' 'python scripts/verify_access_final_lock.py' \
        'Activity Audit Final Lock' 'python scripts/verify_activity_audit_final_lock.py' \
        'Identity Provider Architecture' 'python scripts/verify_identity_provider_architecture.py' \
        'Authentication Surface Final Lock' 'python scripts/verify_authentication_surface_final_lock.py' \
        'Settings Final Lock' 'python scripts/verify_settings_final_lock.py' \
        'Intelligence Baseline Lock' 'python scripts/verify_intelligence_baseline_lock.py' \
        'Automation Control' 'python scripts/verify_automation_control.py' \
        'TLS Certificate Governance' 'python scripts/verify_tls_certificate_governance_standard.py' \
        'Workload Inventory Standard' 'python scripts/verify_workload_inventory_standard.py' \
        'Pod Inventory Standard' 'python scripts/verify_pod_inventory_standard.py' \
        'Service Inventory Standard' 'python scripts/verify_service_inventory_standard.py' \
        'Ingress Inventory Standard' 'python scripts/verify_ingress_inventory_standard.py' \
        'Storage Inventory Standard' 'python scripts/verify_storage_inventory_standard.py' \
        'Core Workspace Cleanup' 'python scripts/verify_core_workspace_legacy_cleanup.py' \
        'Core Workspace Code Health' 'python scripts/verify_core_workspace_code_health.py' \
        'Dark Mode Standard' 'python scripts/verify_dark_mode_standard.py' \
        'Core Workspace UI Lock' 'python scripts/verify_core_workspace_ui_lock.py' \
        'Core Kubernetes Final Lock' 'python scripts/verify_core_kubernetes_final_lock.py' \
        'Platform Operations Final Lock' 'python scripts/verify_platform_operations_final_lock.py' \
        'Job Progress Final Lock' 'python scripts/verify_job_progress_final_lock.py' \
        'Data Lifecycle Final Lock' 'python scripts/verify_data_lifecycle_final_lock.py' \
        'Notification Center Final Lock' 'python scripts/verify_notification_center_final_lock.py' \
        'Notification Activity Center' 'python scripts/verify_notification_activity_center.py' \
        'Notification Surface Style' 'python scripts/verify_notification_surface_style.py' \
        'Integration Provider Foundation' 'python scripts/verify_integration_provider_foundation.py' \
        'Integration Domain Navigation' 'python scripts/verify_integration_domain_navigation.py' \
        'MinIO Object Storage Provider' 'python scripts/verify_minio_object_storage_provider.py' \
        'Metrics Source Consumer Profiles' 'python scripts/verify_metrics_source_consumer_profiles.py' \
        'Alertmanager Consumer Profiles' 'python scripts/verify_alertmanager_consumer_profiles.py' \
        'Integrations Final Lock' 'python scripts/verify_integrations_final_lock.py' \
        'Notification Channels' 'python scripts/verify_notification_channels.py' \
        'Provider Frontpage Consistency' 'python scripts/verify_provider_frontpage_consistency.py' \
        'Hero Component Standard' 'python scripts/verify_hero_component_standard.py' \
        'Filter Layout Standard' 'python scripts/verify_filter_layout_standard.py' \
        'Title Case Standard' 'python scripts/verify_title_case_standard.py' \
        'Integrations Title Case' 'python scripts/verify_integrations_title_case.py' \
        'Operational Dashboard Standard' 'python scripts/verify_operational_dashboard_standard.py' \
        'Operational Data Semantics' 'python scripts/verify_operational_data_semantics.py' \
        'Analytics Compact Label Standard' 'python scripts/verify_analytics_compact_label_standard.py' \
        'Analytics Final Lock' 'python scripts/verify_analytics_final_lock.py' \
        'Sidebar Navigation Standard' 'python scripts/verify_sidebar_navigation_standard.py' \
        'Application Shell Standard' 'python scripts/verify_application_shell_standard.py' \
        'JavaScript Syntax' 'python scripts/verify_javascript_syntax.py' \
        'Snapshot Context Bar Standard' 'python scripts/verify_snapshot_context_bar_standard.py' \
        'Pre-release Semantic Lint' 'python scripts/verify_pre_release_lint_cleanup.py' \
        'Pre-release Type Safety' 'python scripts/verify_pre_release_type_safety.py'

    run_static_group 'Engineering Quality' \
        'Ruff Check' 'python -m ruff check app migrations tests scripts' \
        'Ruff Format' 'python -m ruff format --check app migrations tests scripts' \
        'DjLint' 'python -m djlint app/templates --check' \
        'Pyright' 'python -m pyright --project pyrightconfig.json' \
        'Architecture Boundaries' 'python scripts/verify_architecture_boundaries.py' \
        'Internal Import Symbols' 'python scripts/verify_internal_import_symbols.py' \
        'Import Cycles' 'python scripts/verify_import_cycles.py' \
        'Module Reachability' 'python scripts/verify_module_reachability.py' \
        'Celery Topology' 'python scripts/verify_celery_topology.py' \
        'Code Health' 'python scripts/verify_code_health.py' \
        'Code Health Baseline Integrity' 'python scripts/verify_code_health_baseline_integrity.py' \
        'Migration Graph' 'python scripts/verify_migration_graph.py' \
        'Runtime Test Source Paths' 'python scripts/verify_test_source_paths.py' \
        'Test Taxonomy' 'python scripts/verify_test_taxonomy.py' \
        'Test Domain Architecture' 'python scripts/verify_test_domain_architecture.py' \
        'Feature Test Coverage' 'python scripts/verify_feature_test_coverage.py' \
        'UI Reuse' 'python scripts/verify_ui_reuse.py' \
        'UI Style' 'python scripts/verify_ui_style.py'

    run_contract_migration_gate
}

run_tests() {
    python scripts/verify_test_prerequisites.py

    run_pytest_capture \
        'Functional Tests' \
        -q \
        --tb=short \
        --junitxml="$TEST_OUTPUT_DIR/release-suite.xml" \
        -m 'not debug and not e2e'

    run_pytest_capture \
        'Domain Characterization Tests' \
        -q \
        --tb=short \
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

    run_e2e_gate
    render_test_taxonomy_summary
}

run_frontend() {
    npm ci --no-audit --no-fund
    npm run check-format
    npm run build-frontend
    npm run verify-frontend
}

run_smoke() {
    printf 'KAORI CI — Integration Smoke\n'
    python scripts/verify_python_syntax.py
    python scripts/verify_architecture_boundaries.py
    python scripts/verify_internal_import_symbols.py
    python scripts/verify_migration_graph.py
    run_pytest_capture \
        'Integration Smoke Tests' \
        -q \
        --tb=short \
        tests/contracts/release/test_kaori_delivery_governance_contract.py \
        tests/contracts/release/test_progressive_ci_admission_contract.py \
        tests/contracts/release/test_ci_output_readability_contract.py
    run_e2e_gate
    record_test_result \
        'PASS' \
        'Integration Smoke' \
        'Fresh syntax, architecture, import, migration, release-contract, progressive-CI, readability, and E2E checks passed.'
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
    --smoke)
        run_smoke
        ;;
    --all)
        run_static
        run_tests
        run_frontend
        ;;
    *)
        printf 'Usage: %s [--static|--tests|--frontend|--smoke|--all]\n' "$0" >&2
        exit 2
        ;;
esac