#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PROJECT="${COMPOSE_PROJECT_NAME:-kaori-runtime-local}"
COMPOSE=(docker compose --project-name "$PROJECT" --file .github/ci/compose.yml)
mkdir -p tmp/ci-artifacts/zap
chmod 0777 tmp/ci-artifacts/zap

"${COMPOSE[@]}" --profile dast run --rm --no-deps zap \
  zap-baseline.py \
  -t http://runtime:5000/ \
  -m 2 \
  -I \
  -r baseline.html \
  -J baseline.json

printf 'PASS — KAORI ZAP Baseline\n'
