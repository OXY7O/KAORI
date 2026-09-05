#!/usr/bin/env bash
set -Eeuo pipefail

: "${GITHUB_RUNNER_URL:?Set GITHUB_RUNNER_URL for the disposable target repository or organization}"
: "${GITHUB_RUNNER_TOKEN:?Set GITHUB_RUNNER_TOKEN at runtime; never commit it}"

name="${GITHUB_RUNNER_NAME:-kaori-demo-runner}"
labels="${GITHUB_RUNNER_LABELS:-kaori-demo,linux,x64}"

printf '== KAORI Example · Runner Registration ==\n'
printf 'Target: %s\n' "$GITHUB_RUNNER_URL"
printf 'Name:   %s\n' "$name"
printf 'Labels: %s\n' "$labels"

./config.sh --unattended --ephemeral \
  --url "$GITHUB_RUNNER_URL" \
  --token "$GITHUB_RUNNER_TOKEN" \
  --name "$name" \
  --labels "$labels" \
  --work _work

printf 'PASS — Disposable runner registered; token value was not printed.\n'
exec ./run.sh
