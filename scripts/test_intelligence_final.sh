#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== KAORI Intelligence final lock =="
python scripts/verify_intelligence_final_lock.py
python scripts/verify_intelligence_baseline_lock.py

echo
echo "== Intelligence contract suite =="
pytest -q \
  tests/contracts/intelligence \
  tests/contracts/design/test_intelligence_typography_hierarchy_full_audit_20260823_contract.py

echo
echo "== Optional formatting/lint checks =="
if python -c 'import ruff' >/dev/null 2>&1; then
  python -m ruff format --check \
    scripts/verify_intelligence_final_lock.py \
    tests/contracts/intelligence
  python -m ruff check \
    scripts/verify_intelligence_final_lock.py \
    tests/contracts/intelligence
else
  echo "SKIP: ruff is not installed in this environment."
fi

if command -v djlint >/dev/null 2>&1; then
  djlint app/templates/intelligence --check
else
  echo "SKIP: djlint is not installed in this environment."
fi

echo
echo "PASS — Intelligence is ready to leave behind."
