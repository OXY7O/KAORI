#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PROJECT="${COMPOSE_PROJECT_NAME:-kaori-release-runtime}"
COMPOSE=(docker compose --project-name "$PROJECT" --file .github/ci/compose.yml)
mkdir -p tmp/ci-artifacts/zap
chmod 0777 tmp/ci-artifacts/zap

"${COMPOSE[@]}" --profile dast run --rm --no-deps zap \
  zap-full-scan.py \
  -t http://runtime:5000/ \
  -m 5 \
  -I \
  -r release-full.html \
  -J release-full.json

printf 'PASS — KAORI ZAP Full Scan\n'
