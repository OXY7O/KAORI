#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PROJECT="${COMPOSE_PROJECT_NAME:-kaori-runtime-local}"
COMPOSE=(docker compose --project-name "$PROJECT" --file .github/ci/compose.yml)
ZAP_IMAGE="${KAORI_ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:2.17.0}"
ZAP_PULL_ATTEMPTS="${KAORI_ZAP_PULL_ATTEMPTS:-5}"
ZAP_PULL_BASE_DELAY_SECONDS="${KAORI_ZAP_PULL_BASE_DELAY_SECONDS:-5}"
export KAORI_ZAP_IMAGE="$ZAP_IMAGE"

mkdir -p tmp/ci-artifacts/zap
chmod 0777 tmp/ci-artifacts/zap

if ! docker image inspect "$ZAP_IMAGE" >/dev/null 2>&1; then
  pulled=0
  for attempt in $(seq 1 "$ZAP_PULL_ATTEMPTS"); do
    printf 'Pulling ZAP image (%s/%s): %s\n' "$attempt" "$ZAP_PULL_ATTEMPTS" "$ZAP_IMAGE"
    if docker pull "$ZAP_IMAGE"; then
      pulled=1
      break
    fi

    if [[ "$attempt" -ge "$ZAP_PULL_ATTEMPTS" ]]; then
      break
    fi

    delay_seconds=$((ZAP_PULL_BASE_DELAY_SECONDS * attempt))
    printf 'ZAP image pull failed; retrying in %ss\n' "$delay_seconds" >&2
    sleep "$delay_seconds"
  done

  if [[ "$pulled" != "1" ]]; then
    printf 'Unable to pull ZAP image after %s attempts: %s\n' "$ZAP_PULL_ATTEMPTS" "$ZAP_IMAGE" >&2
    exit 1
  fi
else
  printf 'Reusing cached ZAP image: %s\n' "$ZAP_IMAGE"
fi

"${COMPOSE[@]}" --profile dast run --rm --no-deps --pull never zap \
  zap-baseline.py \
  -t http://runtime:5000/ \
  -m 2 \
  -I \
  -r baseline.html \
  -J baseline.json

printf 'PASS — KAORI ZAP Baseline\n'
