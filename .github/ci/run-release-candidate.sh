#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

IMAGE_REF="${1:?Usage: run-release-candidate.sh <image@digest> <version>}"
VERSION="${2:?release version required}"
PROJECT="${COMPOSE_PROJECT_NAME:-kaori-release-runtime}"
COMPOSE=(docker compose --project-name "$PROJECT" --file .github/ci/compose.yml)

export KAORI_RUNTIME_IMAGE="$IMAGE_REF"
export KAORI_RUNTIME_APP_VERSION="$VERSION"
export KAORI_RUNTIME_BUILD_SHA="$(docker image inspect "$IMAGE_REF" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' 2>/dev/null || true)"
export KAORI_RUNTIME_BUILD_DATE="$(docker image inspect "$IMAGE_REF" --format '{{ index .Config.Labels "org.opencontainers.image.created" }}' 2>/dev/null || true)"
if [[ -z "$KAORI_RUNTIME_BUILD_SHA" || -z "$KAORI_RUNTIME_BUILD_DATE" ]]; then
  docker pull "$IMAGE_REF" >/dev/null
  export KAORI_RUNTIME_BUILD_SHA="$(docker image inspect "$IMAGE_REF" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
  export KAORI_RUNTIME_BUILD_DATE="$(docker image inspect "$IMAGE_REF" --format '{{ index .Config.Labels "org.opencontainers.image.created" }}')"
fi
export CI_UID="${CI_UID:-$(id -u)}"
export CI_GID="${CI_GID:-$(id -g)}"
export KAORI_CI_TOOLCHAIN_IMAGE="${KAORI_CI_TOOLCHAIN_IMAGE:-kaori-ci-toolchain:local}"

cleanup() {
  "${COMPOSE[@]}" --profile dast down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

mkdir -p tmp/ci-artifacts/release tmp/ci-artifacts/zap
chmod 0777 tmp/ci-artifacts/release tmp/ci-artifacts/zap

printf '[KAORI Release] fresh database migration\n'
"${COMPOSE[@]}" up -d postgres redis ci
"${COMPOSE[@]}" run --rm runtime alembic upgrade head

printf '[KAORI Release] exact candidate runtime and Reports worker\n'
"${COMPOSE[@]}" up -d runtime runtime-reports-worker
ready=0
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T ci python - <<'PY' >/dev/null 2>&1
import requests
response = requests.get('http://runtime:5000/', timeout=3, allow_redirects=False)
raise SystemExit(0 if response.status_code < 500 else 1)
PY
  then
    ready=1
    break
  fi
  sleep 2
done
[[ "$ready" == "1" ]] || {
  "${COMPOSE[@]}" logs --no-color runtime > tmp/ci-artifacts/release/runtime.log || true
  printf 'Release candidate failed HTTP readiness\n' >&2
  exit 1
}

worker_ready=0
for _ in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T ci python scripts/verify_reports_worker_runtime.py --timeout 1 >/dev/null 2>&1; then
    worker_ready=1
    break
  fi
  sleep 2
done
[[ "$worker_ready" == "1" ]] || {
  "${COMPOSE[@]}" logs --no-color runtime-reports-worker > tmp/ci-artifacts/release/reports-worker.log || true
  printf 'Release candidate Reports worker failed readiness\n' >&2
  exit 1
}

"${COMPOSE[@]}" logs --no-color runtime > tmp/ci-artifacts/release/runtime.log
"${COMPOSE[@]}" logs --no-color runtime-reports-worker > tmp/ci-artifacts/release/reports-worker.log
"${COMPOSE[@]}" exec -T ci python scripts/verify_reports_worker_runtime.py --timeout 2

printf '[KAORI Release] previous release upgrade path\n'
previous_tag="$(git tag --list 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | grep -vx "v$VERSION" | head -n1 || true)"
if [[ -z "$previous_tag" ]]; then
  printf 'No previous strict SemVer tag exists; release upgrade-path evidence is unavailable\n' >&2
  exit 1
fi

upgrade_project="${PROJECT}-upgrade"
upgrade_compose=(docker compose --project-name "$upgrade_project" --file .github/ci/compose.yml)
worktree="$(mktemp -d)"
previous_image="kaori:previous-${previous_tag#v}"
cleanup_upgrade() {
  "${upgrade_compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  git worktree remove --force "$worktree" >/dev/null 2>&1 || true
  rm -rf "$worktree"
  docker image rm "$previous_image" >/dev/null 2>&1 || true
}
trap 'cleanup_upgrade; cleanup' EXIT

git worktree add --detach "$worktree" "$previous_tag"
docker build --target production --tag "$previous_image" "$worktree"

# Previous release receives its own version/build evidence so ProductionConfig has a complete contract.
export KAORI_RUNTIME_IMAGE="$previous_image"
export KAORI_RUNTIME_APP_VERSION="${previous_tag#v}"
export KAORI_RUNTIME_BUILD_SHA="$(git rev-list -n1 "$previous_tag")"
export KAORI_RUNTIME_BUILD_DATE="$(git show -s --format=%cI "$previous_tag")"
"${upgrade_compose[@]}" up -d postgres redis
"${upgrade_compose[@]}" run --rm runtime alembic upgrade head

export KAORI_RUNTIME_IMAGE="$IMAGE_REF"
export KAORI_RUNTIME_APP_VERSION="$VERSION"
export KAORI_RUNTIME_BUILD_SHA="$(docker image inspect "$IMAGE_REF" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
export KAORI_RUNTIME_BUILD_DATE="$(docker image inspect "$IMAGE_REF" --format '{{ index .Config.Labels "org.opencontainers.image.created" }}')"
"${upgrade_compose[@]}" run --rm runtime alembic upgrade head

printf '[KAORI Release] full active DAST\n'
bash .github/ci/run-zap-full.sh

printf 'PASS — KAORI Release Candidate %s\n' "$VERSION"
