#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export KAORI_VPS_COMPOSE="${KAORI_SERVER_COMPOSE:-$SCRIPT_DIR/compose.server.yml}"
exec bash "$SCRIPT_DIR/.deploy-runtime.sh" "$@"
