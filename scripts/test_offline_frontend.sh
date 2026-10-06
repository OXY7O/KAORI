#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> [1/6] Verifying committed vendor assets"
npm run verify-vendor-assets

echo "==> [2/6] Compiling Python sources"
python -m compileall -q app tests

echo "==> [3/6] Running frontend lint checks"
ruff check \
  tests/frontend \
  tests/contracts/frontend

echo "==> [4/6] Running offline asset functional tests"
pytest -q tests/frontend -m functional

echo "==> [5/6] Running frontend locality contracts"
pytest -q tests/contracts/frontend -m contract

echo "==> [6/6] Verifying CSS build output"
npm run verify-css

echo "==> Offline frontend asset gate passed"
