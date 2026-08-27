#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ARTIFACT_DIR="$ROOT/tmp/ci-artifacts/security"
mkdir -p "$ARTIFACT_DIR"

printf '[KAORI CI] workflow lint\n'
actionlint .github/workflows/*.yml

printf '[KAORI CI] workflow security lint\n'
zizmor --persona=regular --min-severity=medium .github/workflows

printf '[KAORI CI] shell lint\n'
shellcheck .github/ci/*.sh scripts/*.sh

printf '[KAORI CI] Dockerfile lint\n'
hadolint --failure-threshold error Dockerfile .github/ci/Dockerfile

printf '[KAORI CI] secret scan\n'
gitleaks git \
  --no-banner \
  --redact \
  --report-format json \
  --report-path "$ARTIFACT_DIR/gitleaks.json" \
  .

printf '[KAORI CI] Python SAST\n'
bandit -r app scripts -q -ll -f json -o "$ARTIFACT_DIR/bandit.json"

printf '[KAORI CI] Semgrep community SAST\n'
semgrep scan \
  --config .github/ci/semgrep.yml \
  --error \
  --metrics=off \
  --exclude node_modules \
  --exclude app/static/vendor \
  --json \
  --json-output "$ARTIFACT_DIR/semgrep.json" \
  app scripts frontend

printf '[KAORI CI] Python dependency audit\n'
pip-audit -r requirements/base.txt --format=json --output="$ARTIFACT_DIR/pip-audit-base.json"
pip-audit -r requirements/dev.txt --format=json --output="$ARTIFACT_DIR/pip-audit-dev.json"

printf '[KAORI CI] Node dependency audit\n'
npm audit --audit-level=high --json > "$ARTIFACT_DIR/npm-audit.json"

printf 'PASS — KAORI Free-Plan Static Security\n'
