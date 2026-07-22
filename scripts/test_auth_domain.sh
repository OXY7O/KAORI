#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python -m compileall -q app tests
ruff check \
  app/auth \
  app/users/identity.py \
  app/users/forms.py \
  tests/auth \
  tests/contracts/auth
pytest -q tests/auth -m functional
pytest -q tests/contracts -m contract
