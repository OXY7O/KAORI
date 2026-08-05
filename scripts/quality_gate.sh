#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

phase="${1:---all}"

run_static() {
    bash scripts/verify_source_hygiene.sh
    python scripts/verify_python_syntax.py
    python scripts/verify_single_pdf_engine.py
    python scripts/verify_analytics_pdf_publication.py
    python scripts/verify_report_generation_contract.py
    python scripts/verify_report_runtime_imports.py
    python scripts/verify_report_job_standard.py
    python scripts/verify_report_storage_resilience.py
    python scripts/verify_tabular_export_standard.py
    python scripts/verify_node_inventory_standard.py
    python scripts/verify_namespace_inventory_standard.py
    python scripts/verify_workload_inventory_standard.py
    python scripts/verify_pod_inventory_standard.py
    python scripts/verify_dark_mode_standard.py
    python scripts/verify_hero_component_standard.py
    python scripts/verify_operational_dashboard_standard.py
    python scripts/verify_sidebar_navigation_standard.py
    python scripts/verify_snapshot_context_bar_standard.py
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
    python scripts/verify_migration_graph.py
    python scripts/verify_test_taxonomy.py
    python scripts/verify_feature_test_coverage.py
    python scripts/verify_ui_reuse.py
    python scripts/verify_ui_style.py
    pytest -q tests/contracts tests/migrations -m 'contract or migration'
}

run_tests() {
    pytest -q -m 'not debug'

    # Domain characterization tests are explicit release gates. This protects
    # them from environment-level PYTEST_ADDOPTS or marker filtering that may
    # otherwise deselect unmarked behavioral tests.
    pytest -q tests/analytics tests/inventory tests/kubernetes -m functional
    pytest -q \
        tests/analytics/test_alerts_characterization.py \
        tests/analytics/test_alerts_source_fallback_characterization.py
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
