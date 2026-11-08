#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

IMAGE_REF="${1:?Usage: run-runtime-validation.sh <image-ref>}"
PROJECT="${COMPOSE_PROJECT_NAME:-kaori-runtime-local}"
COMPOSE=(docker compose --project-name "$PROJECT" --file .github/ci/compose.yml)

export KAORI_RUNTIME_IMAGE="$IMAGE_REF"
export KAORI_RUNTIME_APP_VERSION="${KAORI_RUNTIME_APP_VERSION:-$(awk -F= '$1 == "APP_VERSION" {print $2; exit}' .env.production.example | tr -d '[:space:]')}"
export KAORI_RUNTIME_BUILD_SHA="${KAORI_RUNTIME_BUILD_SHA:-${GITHUB_SHA:-local-validation}}"
export KAORI_RUNTIME_BUILD_DATE="${KAORI_RUNTIME_BUILD_DATE:-$(date -u +'%Y-%m-%dT%H:%M:%SZ')}"
export CI_UID="${CI_UID:-$(id -u)}"
export CI_GID="${CI_GID:-$(id -g)}"
export KAORI_CI_TOOLCHAIN_IMAGE="${KAORI_CI_TOOLCHAIN_IMAGE:-kaori-ci-toolchain:local}"

cleanup() {
  "${COMPOSE[@]}" --profile dast down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

mkdir -p tmp/ci-artifacts/runtime tmp/ci-artifacts/zap
chmod 0777 tmp/ci-artifacts/runtime tmp/ci-artifacts/zap

printf '⏳ Runtime/DAST · starting isolated PostgreSQL, Redis and CI service\n'
"${COMPOSE[@]}" up -d postgres redis ci
printf '✅ Runtime dependencies started\n'
printf '⏳ Runtime/DAST · applying candidate database migration\n'
"${COMPOSE[@]}" run --rm runtime flask --app run:app db upgrade
printf '✅ Candidate database migration PASS\n'
printf '⏳ Runtime/DAST · starting web and Reports worker\n'
"${COMPOSE[@]}" up -d runtime runtime-reports-worker
printf '⏳ Runtime/DAST · waiting for web readiness (max 60 attempts)\n'

ready=0
for attempt in $(seq 1 60); do
  if ! "${COMPOSE[@]}" ps --status running runtime | grep -q runtime; then
    "${COMPOSE[@]}" logs --no-color runtime > tmp/ci-artifacts/runtime/runtime.log || true
    printf 'KAORI runtime container exited before readiness\n' >&2
    exit 1
  fi

  if "${COMPOSE[@]}" exec -T ci python - <<'PY' >/dev/null 2>&1
import requests
response = requests.get('http://runtime:5000/', timeout=3, allow_redirects=False)
raise SystemExit(0 if response.status_code < 500 else 1)
PY
  then
    ready=1
    break
  fi
  if (( attempt % 10 == 0 )); then
    printf '⏳ Runtime/DAST · web readiness pending (%s/60 probes)\n' "$attempt"
  fi
  sleep 2
done

if [[ "$ready" != "1" ]]; then
  "${COMPOSE[@]}" logs --no-color runtime > tmp/ci-artifacts/runtime/runtime.log || true
  printf 'KAORI runtime did not become HTTP-ready within 120 seconds\n' >&2
  exit 1
fi

printf '✅ Runtime web readiness PASS\n'
printf '⏳ Runtime/DAST · waiting for Reports worker readiness (max 30 attempts)\n'
worker_ready=0
for attempt in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T ci python scripts/verify_reports_worker_runtime.py --timeout 1 > tmp/ci-artifacts/runtime/reports-worker-probe.log 2>&1; then
    worker_ready=1
    break
  fi
  if (( attempt % 10 == 0 )); then
    printf '⏳ Runtime/DAST · Reports worker readiness pending (%s/30 probes)\n' "$attempt"
  fi
  sleep 2
done
if [[ "$worker_ready" != "1" ]]; then
  "${COMPOSE[@]}" logs --no-color runtime-reports-worker > tmp/ci-artifacts/runtime/reports-worker.log 2>&1 || true
  "${COMPOSE[@]}" ps --all > tmp/ci-artifacts/runtime/reports-worker-containers.log 2>&1 || true
  printf 'KAORI production Reports worker failed 30 readiness probes; inspect retained worker, probe, and container diagnostics.\n' >&2
  exit 1
fi
printf '✅ Runtime Reports worker readiness PASS\n'
printf '⏳ Runtime/DAST · retaining runtime and worker diagnostics\n'
"${COMPOSE[@]}" logs --no-color runtime > tmp/ci-artifacts/runtime/runtime.log
"${COMPOSE[@]}" logs --no-color runtime-reports-worker > tmp/ci-artifacts/runtime/reports-worker.log
printf '⏳ Runtime/DAST · verifying final internal HTTP response\n'
"${COMPOSE[@]}" exec -T ci python - <<'PY'
import requests
response = requests.get('http://runtime:5000/', timeout=10, allow_redirects=False)
if response.status_code >= 500:
    raise SystemExit(f'Unexpected KAORI root response: HTTP {response.status_code}')
print(f'PASS — KAORI Runtime HTTP {response.status_code}')
PY
printf '⏳ Runtime/DAST · verifying Reports worker contract\n'
"${COMPOSE[@]}" exec -T ci python scripts/verify_reports_worker_runtime.py --timeout 2
printf '✅ Runtime Reports worker contract PASS\n'

# Keep DAST inside this lifecycle so the target runtime still exists when ZAP starts.
printf '⏳ Runtime/DAST · starting ZAP baseline scan (live scanner output follows)\n'
bash .github/ci/run-zap-baseline.sh
printf '✅ Runtime baseline DAST PASS\n'

printf 'PASS — KAORI Production Runtime and Baseline DAST\n'
