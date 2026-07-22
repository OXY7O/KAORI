#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> [1/5] Verifying committed vendor assets"
node ./scripts/verify_frontend_assets.mjs

echo "==> [2/5] Compiling Python sources"
python -m compileall -q app tests

echo "==> [3/5] Running frontend lint checks"
ruff check \
  tests/frontend \
  tests/contracts/frontend

echo "==> [4/5] Running offline asset functional tests"
pytest -q tests/frontend -m functional

echo "==> [5/5] Running frontend locality contracts"
pytest -q tests/contracts/frontend -m contract

echo "==> Offline frontend asset gate passed"
