#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

phase="${1:---all}"
TEST_OUTPUT_DIR="tmp/ci-artifacts/test-output"
STATIC_OUTPUT_DIR="tmp/ci-artifacts/static-output"
RELEASE_SURFACE_COVERAGE_LOG=""

status_icon() {
    case "$1" in
        PASS) printf '✅' ;;
        FAIL) printf '❌' ;;
        SKIP|REUSED|FALLBACK) printf '⚠️' ;;
        *) printf '•' ;;
    esac
}

append_test_summary() {
    local status="$1"
    local label="$2"
    local detail="$3"

    if [[ -z "${GITHUB_STEP_SUMMARY:-}" ]]; then
        return 0
    fi

    {
        printf -- '- **%s %s**\n' "$(status_icon "$status")" "$label"
        printf '  - %s\n' "$detail"
    } >>"$GITHUB_STEP_SUMMARY"
}

record_test_result() {
    local status="$1"
    local label="$2"
    local detail="$3"

    printf '\n%s %s · %s\n' "$(status_icon "$status")" "$label" "$detail"
    append_test_summary "$status" "$label" "$detail"
}

pytest_result_line() {
    local log_file="$1"
    grep -E '(^|[[:space:]])([0-9]+ (passed|failed|error|errors|skipped|deselected)|no tests ran)' "$log_file" \
        | tail -n 1 \
        | sed -E 's/^[[:space:]]+//'
}

filter_pytest_progress() {
    sed -E '/^[.FEsxX]+[[:space:]]+\[[[:space:]]*[0-9]+%\]$/d'
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

    printf '❌ First actionable failure — %s\n' "$first_failure" >&2
    printf '📦 Diagnostic excerpt — bounded; full pytest output is retained at %s\n' "$log_file" >&2

    awk '
        /={3,} FAILURES ={3,}/ {capture=1}
        /={3,} ERRORS ={3,}/ {capture=1}
        capture {print; lines++}
        lines >= 60 {exit}
    ' "$log_file" >&2

    printf '%s\n' '--- short test summary info / final output ---' >&2
    tail -n 80 "$log_file" | filter_pytest_progress >&2
}

# Expose setup/build cost without changing selected tests, captured pytest logs,
# or exit-code handling. Each invocation remains within its owning gate.
run_timed_setup() {
    local label="$1"
    shift
    local started elapsed status=0
    started="$(date +%s)"
    printf '⏳ %s\n' "$label"
    "$@" || status=$?
    elapsed=$(( $(date +%s) - started ))
    if [[ "$status" -ne 0 ]]; then
        printf '❌ %s · exit %d · ⏱ %dm %02ds\n' "$label" "$status" $((elapsed / 60)) $((elapsed % 60)) >&2
        return "$status"
    fi
    printf '✅ %s · ⏱ %dm %02ds\n' "$label" $((elapsed / 60)) $((elapsed % 60))
}

run_pytest_capture() {
    local label="$1"
    shift
    local slug log_file result_line status started elapsed=0 test_pid heartbeat_pid pytest_display
    status=0

    mkdir -p "$TEST_OUTPUT_DIR"
    slug="$(printf '%s' "$label" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9_-')"
    log_file="$(mktemp "$TEST_OUTPUT_DIR/${slug}.XXXXXX.log")"
    started="$(date +%s)"
    if [[ "${KAORI_CI_LIVE_LOG:-0}" == '1' ]]; then
        printf -v pytest_display '%q ' pytest "$@"
        printf '⏳ %s · %s · output captured in %s\n' "$label" "$pytest_display" "$log_file"
        pytest "$@" >"$log_file" 2>&1 &
        test_pid=$!
        (
            while kill -0 "$test_pid" >/dev/null 2>&1; do
                sleep 60
                if kill -0 "$test_pid" >/dev/null 2>&1; then
                    elapsed=$(( $(date +%s) - started ))
                    printf '⏳ %s still running · ⏱ %dm %02ds · final pytest counts pending\n' \
                        "$label" $((elapsed / 60)) $((elapsed % 60))
                fi
            done
        ) &
        heartbeat_pid=$!
        wait "$test_pid" || status=$?
        kill "$heartbeat_pid" >/dev/null 2>&1 || true
        wait "$heartbeat_pid" >/dev/null 2>&1 || true
    else
        printf '⏳ %s\n' "$label"
        pytest "$@" >"$log_file" 2>&1 || status=$?
    fi

    if (( status == 0 )); then
        elapsed=$(( $(date +%s) - started ))
        result_line="$(pytest_result_line "$log_file" || true)"
        [[ -n "$result_line" ]] || result_line='Pytest completed successfully.'
        record_test_result 'PASS' "$label" "$result_line · ⏱ $(printf '%dm %02ds' $((elapsed / 60)) $((elapsed % 60)))"
        return 0
    fi

    elapsed=$(( $(date +%s) - started ))
    result_line="$(pytest_result_line "$log_file" || true)"
    [[ -n "$result_line" ]] || result_line="Pytest exited with status $status."
    record_test_result 'FAIL' "$label" "$result_line · ⏱ $(printf '%dm %02ds' $((elapsed / 60)) $((elapsed % 60)))" >&2
    print_pytest_failure_excerpt "$log_file"
    printf '➡️ Repair the first actionable failure above, collect remaining findings, then rerun this gate.\n' >&2
    return "$status"
}

run_command_capture() {
    local group="$1"
    local label="$2"
    shift 2
    local slug log_file status first_failure started command_display

    # Display the actual canonical verifier command rather than an unquoted
    # bash -lc wrapper. The wrapper remains the executable implementation.
    if [[ "$#" -eq 3 && "$1" == bash && "$2" == -lc ]]; then
        command_display="$3"
    else
        printf -v command_display '%q ' "$@"
    fi

    mkdir -p "$STATIC_OUTPUT_DIR"
    slug="$(printf '%s-%s' "$group" "$label" | tr '[:upper:] /&' '[:lower:]----' | tr -cd 'a-z0-9_-')"
    log_file="$(mktemp "$STATIC_OUTPUT_DIR/${slug}.XXXXXX.log")"
    started="$(date +%s)"
    if [[ "${KAORI_CI_LIVE_LOG:-0}" == '1' ]]; then
        printf '⏳ %s — %s · %s\n' "$group" "$label" "$command_display"
        printf '%s — %s\n' "$group" "$label" > "$STATIC_OUTPUT_DIR/active-verifier.txt"
    else
        printf '⏳ %s — %s\n' "$group" "$label"
    fi

    if "$@" >"$log_file" 2>&1; then
        # Retain verified release-surface evidence for the Domain & Capability
        # Contracts rollup; avoid printing it under Foundation & Governance.
        if [[ "$label" == 'Release Surface Coverage' ]]; then
            RELEASE_SURFACE_COVERAGE_LOG="$log_file"
        fi
        # Every executed verifier is published as evidence; the complete raw
        # output remains in its existing, separately uploaded diagnostic log.
        local report_elapsed=$(( $(date +%s) - started ))
        printf "| %s | %s | \`%s\` | PASS | %dm %02ds | \`%s\` |\n" \
            "$group" "$label" "$command_display" $((report_elapsed / 60)) $((report_elapsed % 60)) \
            "$(basename "$log_file")" >> "$STATIC_OUTPUT_DIR/verification-report.md"
        # In CI only, show a bounded subset of standardized PASS evidence in
        # the expanded live step; never print an unbounded raw verifier log.
        # Unmatched formats stay available in the existing diagnostic artifact.
        if [[ "${KAORI_CI_LIVE_LOG:-0}" == '1' ]]; then
            printf '📊 Verified output sample (up to 6 PASS lines, each max 200 chars):\n'
            awk '
                # Only fixed-format identity and numeric code-health metrics.
                # Never echo arbitrary raw PASS content into public CI logs.
                /^PASS — KAORI [A-Za-z ]+$/ || /^[[:space:]]+PASS — [0-9]+ modules and [0-9]+ functions / || /^[[:space:]]+PASS — [0-9]+ broad exception handlers / || /^[[:space:]]+[0-9]+ checks passed/ {
                    printf "  %s\n", substr($0, 1, 200)
                    shown++
                    if (shown >= 6) exit
                }
                END {
                    if (shown == 0) print "  No standardized PASS detail; consult raw verifier log."
                }
            ' "$log_file"
            printf '📦 Full diagnostic log: %s\n' "$log_file"
            : > "$STATIC_OUTPUT_DIR/active-verifier.txt"
        fi
        # Preserve the existing Engineering Quality timing and Pyright stats.
        if [[ "$group" == 'Engineering Quality' ]]; then
            local elapsed=$(( $(date +%s) - started ))
            printf '✅ %s — %s · ⏱ %dm %02ds\n' "$group" "$label" $((elapsed / 60)) $((elapsed % 60))
            if [[ "$label" == 'Pyright' ]]; then
                # Expose supported analysis-phase stats only after Pyright passes.
                # Retain the full raw result in the existing static diagnostic file.
                printf '📊 Pyright analysis stats · last 24 lines (bounded)\n'
                tail -n 24 "$log_file"
            fi
        else
            local elapsed=$(( $(date +%s) - started ))
            printf '✅ %s — %s · ⏱ %dm %02ds\n' "$group" "$label" $((elapsed / 60)) $((elapsed % 60))
        fi
        return 0
    else
        status=$?
    fi

    first_failure="$(grep -m1 -E '^(FAIL|FAILED|ERROR|E[[:space:]]|[A-Z][0-9]{3}[[:space:]])' "$log_file" || true)"
    [[ -n "$first_failure" ]] || first_failure="Command exited with status $status."
    local report_elapsed=$(( $(date +%s) - started ))
    printf "| %s | %s | \`%s\` | FAIL (exit %d) | %dm %02ds | \`%s\` |\n" \
        "$group" "$label" "$command_display" "$status" $((report_elapsed / 60)) $((report_elapsed % 60)) \
        "$(basename "$log_file")" >> "$STATIC_OUTPUT_DIR/verification-report.md"
    printf '❌ %s\n' "$label" >&2
    printf '❌ First actionable failure — %s\n' "$first_failure" >&2
    printf '⏱ %dm %02ds\n' $((($(date +%s) - started) / 60)) $((($(date +%s) - started) % 60)) >&2
    printf '📦 Diagnostic excerpt — bounded; full output retained at %s\n' "$log_file" >&2
    tail -n 60 "$log_file" >&2
    printf '➡️ Repair %s, collect remaining findings, then rerun %s.\n' "$label" "$group" >&2
    if [[ "${KAORI_CI_LIVE_LOG:-0}" == '1' ]]; then
        : > "$STATIC_OUTPUT_DIR/active-verifier.txt"
    fi
    return "$status"
}

run_static_group() {
    local group="$1"
    shift
    local group_pass_count=0
    local group_started
    group_started="$(date +%s)"

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

    if [[ "$group" == 'Domain & Capability Contracts' ]]; then
        # Reuse the registered evidence from the already successful Foundation
        # verifier. This is a capability inventory, not additional PASS checks.
        if [[ -z "$RELEASE_SURFACE_COVERAGE_LOG" || ! -f "$RELEASE_SURFACE_COVERAGE_LOG" ]] || \
           ! grep -q '^  EVIDENCE REGISTERED ONLY' "$RELEASE_SURFACE_COVERAGE_LOG" || \
           ! grep -q '^  REGISTERED —' "$RELEASE_SURFACE_COVERAGE_LOG"; then
            printf '❌ Domain capability evidence missing from Release Surface Coverage output\n' >&2
            return 1
        fi
        printf '📋 %s — Registered capability evidence (not per-capability test PASS)\n' "$group"
        sed -n '/^  EVIDENCE REGISTERED ONLY/,$p' "$RELEASE_SURFACE_COVERAGE_LOG"
    fi

    local elapsed=$(( $(date +%s) - group_started ))
    printf '✅ %s · %s checks · ⏱ %dm %02ds\n' "$group" "$group_pass_count" $((elapsed / 60)) $((elapsed % 60))
    append_test_summary \
        'PASS' \
        "$group" \
        "$group_pass_count checks · $(printf '%dm %02ds' $((elapsed / 60)) $((elapsed % 60))). Detailed output is retained in $STATIC_OUTPUT_DIR."
}

run_contract_migration_gate() {
    run_pytest_capture \
        'Contract & Migration Safety' \
        -q \
        --tb=short \
        --junitxml="$TEST_OUTPUT_DIR/contract-migration.xml" \
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
    mkdir -p "$STATIC_OUTPUT_DIR"
    {
        printf '### Static & Governance — executed verifier inventory\n\n'
        printf 'Each row below is an **executed** verifier, not a count of individual unit tests.\n'
        printf 'Registered capability evidence is a separate source-ownership inventory, not a test PASS.\n\n'
        printf '| Group | Check | Command | Outcome | Duration | Raw log in static evidence artifact |\n'
        printf '| --- | --- | --- | --- | --- | --- |\n'
    } > "$STATIC_OUTPUT_DIR/verification-report.md"

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
        'Pyright' 'python -m pyright --project pyrightconfig.json --stats' \
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
    {
        printf "\n**Contract & Migration Safety:** PASS — executed pytest selector \`tests/contracts tests/migrations -m \"contract or migration\"\`; JUnit evidence: \`contract-migration.xml\`.\n"
        printf '\n#### Registered capability ownership (not executed tests)\n\n'
        printf "\`\`\`text\n"
        # The registry output has already been validated and replayed in the
        # Domain & Capability Contracts log. This is a second presentation
        # of existing evidence, never an additional verifier invocation.
        sed -n '/^  EVIDENCE REGISTERED ONLY/,$p' "$RELEASE_SURFACE_COVERAGE_LOG"
        printf "\`\`\`\n"
    } >> "$STATIC_OUTPUT_DIR/verification-report.md"
}

run_tests() {
    python scripts/verify_test_prerequisites.py
    run_timed_setup 'Functional npm dependencies' npm ci --no-audit --no-fund
    run_timed_setup 'Functional CSS build' npm run build-css

    run_pytest_capture \
        'Functional Tests' \
        -q \
        --tb=short \
        --durations=15 \
        --junitxml="$TEST_OUTPUT_DIR/release-suite.xml" \
        -m 'not debug and not e2e and not contract and not migration'

    run_e2e_gate
    render_test_taxonomy_summary
}

run_frontend() {
    run_timed_setup 'Frontend npm dependencies' npm ci --no-audit --no-fund
    run_timed_setup 'Frontend format check' npm run check-format
    run_timed_setup 'Frontend asset build' npm run build-frontend
    run_timed_setup 'Frontend asset verification' npm run verify-frontend
}

run_smoke() {
    printf '⏳ Integration Smoke\n'
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