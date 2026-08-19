#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v pytest >/dev/null 2>&1; then
    PYTEST=(pytest)
else
    PYTEST=(python -m pytest)
fi

echo "KAORI Alert Evidence modal width verification"
echo "============================================"

"${PYTEST[@]}" -q \
    tests/contracts/analytics/test_alerts_anomalies_workspace_standard_contract.py \
    tests/contracts/analytics/test_workload_workspace_pagination_recommendation_redesign_contract.py \
    tests/contracts/analytics/test_workload_expandable_row_htmx_contract.py \
    tests/contracts/analytics/test_analytics_visual_role_system_contract.py

echo
echo "PASS: Alert Evidence investigation width and shared modal regressions verified."
