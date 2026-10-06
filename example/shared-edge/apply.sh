#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EDGE_ROOT="${EDGE_ROOT:-/opt/shared-edge}"
EDGE_ENV_FILE="${EDGE_ENV_FILE:-$EDGE_ROOT/config/edge.env}"

fail() {
  printf '❌ Standalone edge apply failed · %s\n' "$*" >&2
  exit 1
}

bash "$SCRIPT_DIR/prepare.sh"

set -a
# shellcheck source=/dev/null
source "$EDGE_ENV_FILE"
set +a
EDGE_SITES_DIR="${EDGE_SITES_DIR:-$EDGE_ROOT/config/sites}"

site_count="$(find "$EDGE_SITES_DIR" -maxdepth 1 -type f -name '*.env' | wc -l | tr -d ' ')"
(( site_count > 0 )) || fail 'no active site registrations exist; publish an application first'

compose=(
  docker compose
  --env-file "$EDGE_ENV_FILE"
  --project-directory "$SCRIPT_DIR"
  -f "$SCRIPT_DIR/compose.yml"
)

"${compose[@]}" pull nginx certbot >/dev/null
"${compose[@]}" up -d --pull never nginx certbot

bash "$SCRIPT_DIR/verify.sh" --wait-seconds 360 --renewal-dry-run

printf '✅ Standalone public edge apply PASS\n'
