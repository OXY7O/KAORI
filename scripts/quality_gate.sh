#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

phase="${1:---all}"

run_static() {
    python -m compileall -q app migrations tests scripts
    python -m ruff check app migrations tests scripts
    python scripts/verify_architecture_boundaries.py
    python scripts/verify_migration_graph.py
    bash scripts/verify_source_hygiene.sh
    pytest -q tests/contracts tests/migrations -m 'contract or migration'
}

run_tests() {
    pytest -q -m 'not debug'

    # Domain characterization tests are explicit release gates. This protects
    # them from environment-level PYTEST_ADDOPTS or marker filtering that may
    # otherwise deselect unmarked behavioral tests.
    pytest -q \
      tests/analytics/test_alerts_characterization.py \
      tests/analytics/test_alerts_source_fallback_characterization.py
}

run_frontend() {
    npm ci --no-audit --no-fund
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
